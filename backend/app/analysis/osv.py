"""OSV batch querying and normalization for resolved npm package instances.

Design goals, in order: never report a wrong finding, never silently drop a real one, and
always say what could not be checked. Transient upstream failures are retried; anything that
still fails is reported through :class:`ScanReport` instead of aborting the whole scan.
"""
from __future__ import annotations

import asyncio
import math
import random
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.analysis import semver
from app.errors import Diagnostic

OSV_API_URL = "https://api.osv.dev/v1/querybatch"
OSV_VULN_URL = "https://api.osv.dev/v1/vulns"
BATCH_SIZE = 500                 # OSV accepts up to 1000 queries per batch
QUERY_CONCURRENCY = 4
DETAIL_CONCURRENCY = 16
MAX_ATTEMPTS = 4
RETRY_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
MAX_PAGES_PER_PACKAGE = 20
SEVERITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "UNKNOWN": 4}


class OSVClient:
    backoff_base = 0.5

    def __init__(self, timeout: float = 30.0, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=10.0),
            limits=httpx.Limits(max_connections=32, max_keepalive_connections=16),
            transport=transport,
        )

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Retry transient failures (network, 408/429/5xx) with exponential backoff + jitter."""
        last_exc: Exception | None = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                response = await self.client.request(method, url, **kwargs)
                if response.status_code not in RETRY_STATUSES:
                    response.raise_for_status()
                    return response
                last_exc = httpx.HTTPStatusError(f"OSV returned {response.status_code}", request=response.request, response=response)
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else None
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc, delay = exc, None
            if attempt == MAX_ATTEMPTS - 1:
                break
            wait = min(delay if delay is not None else self.backoff_base * (2 ** attempt), 10.0)
            await asyncio.sleep(wait + random.uniform(0, self.backoff_base / 2))
        assert last_exc is not None
        raise last_exc

    async def query_batch(self, queries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        response = await self._request("POST", OSV_API_URL, json={"queries": queries})
        payload = response.json()
        results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(results, list) or len(results) != len(queries):
            raise ValueError("OSV returned a malformed batch response")
        return results

    async def get_vulnerability(self, vulnerability_id: str) -> dict[str, Any]:
        """Fetch the full advisory; querybatch rows contain IDs, not advisory details."""
        response = await self._request("GET", f"{OSV_VULN_URL}/{vulnerability_id}")
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("id") != vulnerability_id:
            raise ValueError(f"OSV returned a malformed advisory record for {vulnerability_id}")
        return payload

    async def close(self) -> None:
        await self.client.aclose()


@dataclass
class ScanReport:
    """What the scan did and could not do; the service turns this into frontend diagnostics."""
    packages_queried: int = 0
    packages_skipped: int = 0
    failed_queries: int = 0
    failed_advisories: list[str] = field(default_factory=list)
    withdrawn_advisories: list[str] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return self.failed_queries == 0 and not self.failed_advisories


class _AdvisoryCache:
    """Advisories are immutable per (id, modified) revision, so caching them is always safe."""

    def __init__(self, limit: int = 4000) -> None:
        self.limit = limit
        self._items: OrderedDict[tuple[str, str], dict[str, Any]] = OrderedDict()

    def get(self, key: tuple[str, str]) -> dict[str, Any] | None:
        value = self._items.get(key)
        if value is not None:
            self._items.move_to_end(key)
        return value

    def put(self, key: tuple[str, str], value: dict[str, Any]) -> None:
        self._items[key] = value
        self._items.move_to_end(key)
        while len(self._items) > self.limit:
            self._items.popitem(last=False)


_ADVISORY_CACHE = _AdvisoryCache()


# --------------------------------------------------------------------------- fixed versions
def _range_intervals(events: list[Any]) -> list[tuple[str, str | None]]:
    """Turn OSV range events into (introduced, fixed|None) intervals, ordered by version."""
    def key(event: dict[str, Any]) -> tuple:
        point = event.get("introduced") or event.get("fixed") or event.get("last_affected") or "0"
        parsed = semver.sort_key(point if point != "0" else "0.0.0")
        return (0, parsed) if parsed is not None else (1, ())
    ordered = sorted((e for e in events if isinstance(e, dict)), key=key)
    intervals: list[tuple[str, str | None]] = []
    start: str | None = None
    for event in ordered:
        if "introduced" in event and isinstance(event["introduced"], str):
            start = event["introduced"]
        elif start is not None and isinstance(event.get("fixed"), str):
            intervals.append((start, event["fixed"]))
            start = None
        elif start is not None and isinstance(event.get("last_affected"), str):
            intervals.append((start, None))      # affected through a version; no fix exists
            start = None
    if start is not None:
        intervals.append((start, None))
    return intervals


def _in_interval(installed: str, introduced: str, fixed: str | None) -> bool | None:
    low = "0.0.0" if introduced == "0" else introduced
    after_low = semver.compare(installed, low)
    if after_low is None:
        return None
    if after_low < 0:
        return False
    if fixed is None:
        return True
    before_fix = semver.compare(installed, fixed)
    return None if before_fix is None else before_fix < 0


def _fixed_versions(vulnerability: dict[str, Any], name: str | None = None, installed: str | None = None) -> list[str]:
    """Versions that fix this advisory *for the installed release line*.

    An advisory often lists a fix per maintained branch (``1.2.3`` and ``2.0.1``). Recommending
    ``1.2.3`` to someone on 2.0.0 would be a downgrade, so when the installed version is known
    only the interval containing it is used. If it cannot be placed (unparsable version), fall
    back to every fix newer than it, then to every listed fix, never to an older one first.
    """
    in_range: set[str] = set()
    newer: set[str] = set()
    every: set[str] = set()
    affected_list = vulnerability.get("affected")
    for affected in affected_list if isinstance(affected_list, list) else []:
        if not isinstance(affected, dict):
            continue
        package = affected.get("package")
        if isinstance(package, dict):
            if name and isinstance(package.get("name"), str) and package["name"] != name:
                continue
            ecosystem = package.get("ecosystem")
            if isinstance(ecosystem, str) and ecosystem.lower() != "npm":
                continue
        ranges = affected.get("ranges")
        for version_range in ranges if isinstance(ranges, list) else []:
            if not isinstance(version_range, dict) or version_range.get("type") == "GIT":
                continue
            events = version_range.get("events")
            for introduced, fixed in _range_intervals(events if isinstance(events, list) else []):
                if fixed is None:
                    if installed and _in_interval(installed, introduced, None):
                        return []        # installed release is affected and no fix exists
                    continue
                every.add(fixed)
                if installed:
                    placed = _in_interval(installed, introduced, fixed)
                    if placed:
                        in_range.add(fixed)
                    cmp = semver.compare(fixed, installed)
                    if cmp is not None and cmp > 0:
                        newer.add(fixed)
    if not installed:
        chosen = every
    elif in_range:
        chosen = in_range
    elif newer:
        chosen = newer
    else:
        # Every listed fix is older than the installed version. Recommending any of them
        # would be a downgrade, unless the comparison itself was impossible (unparsable version).
        chosen = every if any(semver.compare(fixed, installed) is None for fixed in every) else set()
    return semver.sorted_versions(sorted(chosen))


# --------------------------------------------------------------------------- severity
_CVSS3_WEIGHTS = {
    "AV": {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2},
    "AC": {"L": 0.77, "H": 0.44},
    "UI": {"N": 0.85, "R": 0.62},
    "CIA": {"H": 0.56, "L": 0.22, "N": 0.0},
}


def _roundup(value: float) -> float:
    scaled = round(value * 100000)
    return scaled / 100000.0 if scaled % 10000 == 0 else (math.floor(scaled / 10000) + 1) / 10.0


def cvss3_base_score(vector: str) -> float | None:
    """CVSS v3.0/v3.1 base score from a vector string (FIRST specification, section 7)."""
    if not isinstance(vector, str) or not vector.startswith(("CVSS:3.0/", "CVSS:3.1/")):
        return None
    metrics = dict(part.split(":", 1) for part in vector.split("/")[1:] if ":" in part)
    try:
        scope_changed = metrics["S"] == "C"
        privileges = {"N": 0.85, "L": 0.68 if scope_changed else 0.62, "H": 0.5 if scope_changed else 0.27}[metrics["PR"]]
        exploitability = 8.22 * _CVSS3_WEIGHTS["AV"][metrics["AV"]] * _CVSS3_WEIGHTS["AC"][metrics["AC"]] * privileges * _CVSS3_WEIGHTS["UI"][metrics["UI"]]
        iss = 1 - (1 - _CVSS3_WEIGHTS["CIA"][metrics["C"]]) * (1 - _CVSS3_WEIGHTS["CIA"][metrics["I"]]) * (1 - _CVSS3_WEIGHTS["CIA"][metrics["A"]])
    except KeyError:
        return None
    impact = 7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15 if scope_changed else 6.42 * iss
    if impact <= 0:
        return 0.0
    total = 1.08 * (impact + exploitability) if scope_changed else impact + exploitability
    return _roundup(min(total, 10.0))


def _label(score: float) -> str:
    return "CRITICAL" if score >= 9 else "HIGH" if score >= 7 else "MEDIUM" if score >= 4 else "LOW"


def _severity(vulnerability: dict[str, Any]) -> tuple[str, float | None, str | None]:
    """Return (label, numeric score, CVSS vector).

    The advisory's own label (GitHub/NVD curated) wins; a numeric score is computed from any
    CVSS v3 vector so the UI can still sort by it. CVSS v4 vectors are not scored here and
    fall back to UNKNOWN rather than a guessed number.
    """
    scores: list[float] = []
    vector: str | None = None
    for item in vulnerability.get("severity", []) if isinstance(vulnerability.get("severity"), list) else []:
        raw = item.get("score") if isinstance(item, dict) else None
        score: float | None = None
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            score = float(raw)
        elif isinstance(raw, str):
            try:
                score = float(raw)
            except ValueError:
                score = cvss3_base_score(raw)
                if score is None:
                    match = re.search(r"(?:^|/)([0-9]+\.[0-9]+)$", raw)
                    score = float(match.group(1)) if match else None
                if vector is None and raw.startswith("CVSS:"):
                    vector = raw
        if score is not None and 0 <= score <= 10:
            scores.append(score)
    best = max(scores) if scores else None

    database_specific = vulnerability.get("database_specific", {})
    declared = database_specific.get("severity") if isinstance(database_specific, dict) else None
    if isinstance(declared, str) and declared.upper() in {"CRITICAL", "HIGH", "MEDIUM", "MODERATE", "LOW"}:
        normalized = "MEDIUM" if declared.upper() == "MODERATE" else declared.upper()
        return normalized, best, vector
    if best is None:
        return "UNKNOWN", None, vector
    return _label(best), best, vector


def normalize_vulnerability(vulnerability: dict[str, Any], package: dict[str, Any]) -> dict[str, Any]:
    severity, cvss_score, vector = _severity(vulnerability)
    identifier = vulnerability.get("id")
    # OSV "MAL-" records are malicious-package reports: never "low", whatever the score says.
    is_malware = isinstance(identifier, str) and identifier.startswith("MAL-")
    if is_malware and severity in ("UNKNOWN", "LOW", "MEDIUM"):
        severity = "CRITICAL"
    database_specific = vulnerability.get("database_specific", {})
    cwe_ids = database_specific.get("cwe_ids") if isinstance(database_specific, dict) else None
    return {
        "id": identifier,
        "aliases": vulnerability.get("aliases", []) if isinstance(vulnerability.get("aliases", []), list) else [],
        "summary": vulnerability.get("summary") or "No summary provided by OSV",
        "details": vulnerability.get("details"),
        "severity": severity,
        "cvss_score": cvss_score,
        "cvss_vector": vector,
        "cwe_ids": [c for c in cwe_ids if isinstance(c, str)] if isinstance(cwe_ids, list) else [],
        "is_malware": is_malware,
        "package_id": package["id"],
        "package_name": package["name"],
        "installed_version": package["version"],
        "package_path": package["path"],
        "lockfile": package["lockfile"],
        "fixed_versions": _fixed_versions(vulnerability, package["name"], package["version"]),
        "references": [r.get("url") for r in vulnerability.get("references", []) if isinstance(r, dict) and isinstance(r.get("url"), str)] if isinstance(vulnerability.get("references", []), list) else [],
        "modified": vulnerability.get("modified"),
        "published": vulnerability.get("published"),
    }


# --------------------------------------------------------------------------- scanning
def is_scannable(package: dict[str, Any]) -> bool:
    """Only registry packages can be matched by name@version; workspace/git/file sources cannot."""
    return (
        isinstance(package.get("name"), str) and bool(package["name"])
        and isinstance(package.get("version"), str) and bool(package["version"])
        and package.get("source", "registry") == "registry"
        and not package.get("is_link")
    )


async def scan_packages(
    packages: list[dict[str, Any]],
    client: OSVClient | None = None,
    report: ScanReport | None = None,
) -> list[dict[str, Any]]:
    """Query exact npm versions, fetch each unique full advisory once, then map to instances.

    OSV querybatch deliberately returns vulnerability identifiers and modified timestamps,
    not complete advisory records. Failures are retried; whatever still fails is recorded on
    ``report`` (so callers can mark coverage partial) instead of discarding every finding.
    A total outage (every lookup failed) raises, because there is nothing trustworthy to return.
    """
    owns_client = client is None
    osv = client or OSVClient()
    report = report if report is not None else ScanReport()
    eligible = [p for p in packages if is_scannable(p)]
    report.packages_skipped = len(packages) - len(eligible)
    query_keys = sorted({(p["name"], p["version"]) for p in eligible})
    report.packages_queried = len(query_keys)
    ids_by_key: dict[tuple[str, str], list[str]] = {}
    modified_by_id: dict[str, str | None] = {}
    try:
        chunks = [query_keys[start:start + BATCH_SIZE] for start in range(0, len(query_keys), BATCH_SIZE)]
        gate = asyncio.Semaphore(QUERY_CONCURRENCY)
        last_error: Exception | None = None
        failed_chunks = 0

        def query_for(key: tuple[str, str]) -> dict[str, Any]:
            return {"package": {"name": key[0], "ecosystem": "npm"}, "version": key[1]}

        async def run_chunk(chunk: list[tuple[str, str]]) -> None:
            nonlocal last_error, failed_chunks
            async with gate:
                try:
                    rows = await osv.query_batch([query_for(key) for key in chunk])
                    for key, row in zip(chunk, rows):
                        vulns = list(row.get("vulns", [])) if isinstance(row, dict) and isinstance(row.get("vulns"), list) else []
                        token = row.get("next_page_token") if isinstance(row, dict) else None
                        pages = 0
                        while isinstance(token, str) and token and pages < MAX_PAGES_PER_PACKAGE:
                            pages += 1
                            follow = await osv.query_batch([{**query_for(key), "page_token": token}])
                            nxt = follow[0] if follow else {}
                            vulns.extend(nxt.get("vulns", []) if isinstance(nxt, dict) and isinstance(nxt.get("vulns"), list) else [])
                            token = nxt.get("next_page_token") if isinstance(nxt, dict) else None
                        ids = []
                        for vuln in vulns:
                            if isinstance(vuln, dict) and isinstance(vuln.get("id"), str) and vuln["id"]:
                                ids.append(vuln["id"])
                                modified_by_id.setdefault(vuln["id"], vuln.get("modified") if isinstance(vuln.get("modified"), str) else None)
                        # Preserve order while deduplicating any repeated ID in a batch row.
                        ids_by_key[key] = list(dict.fromkeys(ids))
                except Exception as exc:                      # noqa: BLE001 - recorded, not swallowed
                    last_error = exc
                    failed_chunks += 1
                    report.failed_queries += len(chunk)

        await asyncio.gather(*(run_chunk(chunk) for chunk in chunks))
        if chunks and failed_chunks == len(chunks) and last_error is not None:
            raise last_error
        if report.failed_queries:
            report.diagnostics.append(Diagnostic(
                "OSV_QUERY_FAILED", "error",
                f"OSV could not be queried for {report.failed_queries} of {len(query_keys)} package versions after retries; "
                "those packages are not assessed (no findings does NOT mean they are safe).",
                hint="Retry the analysis in a few minutes.",
            ))

        unique_ids = sorted({vuln_id for ids in ids_by_key.values() for vuln_id in ids})
        detail_gate = asyncio.Semaphore(DETAIL_CONCURRENCY)
        use_cache = owns_client

        async def fetch_detail(vulnerability_id: str) -> tuple[str, dict[str, Any]]:
            cache_key = (vulnerability_id, modified_by_id.get(vulnerability_id) or "")
            if use_cache and cache_key[1]:
                cached = _ADVISORY_CACHE.get(cache_key)
                if cached is not None:
                    return vulnerability_id, cached
            async with detail_gate:
                try:
                    detail = await osv.get_vulnerability(vulnerability_id)
                except Exception:                              # noqa: BLE001
                    # Keep the finding (OSV *did* match this version) with what the batch row
                    # gave us, and say that the enrichment is missing.
                    report.failed_advisories.append(vulnerability_id)
                    return vulnerability_id, {"id": vulnerability_id, "modified": modified_by_id.get(vulnerability_id), "_stub": True}
            if use_cache and cache_key[1]:
                _ADVISORY_CACHE.put(cache_key, detail)
            return vulnerability_id, detail

        details_by_id = dict(await asyncio.gather(*(fetch_detail(i) for i in unique_ids)))
        if report.failed_advisories:
            sample = ", ".join(sorted(report.failed_advisories)[:5])
            report.diagnostics.append(Diagnostic(
                "OSV_ADVISORY_DETAIL_FAILED", "warning",
                f"Full details could not be fetched for {len(report.failed_advisories)} advisory record(s) ({sample}"
                f"{', ...' if len(report.failed_advisories) > 5 else ''}). The findings are included, but severity, "
                "fixed versions and references may be missing for them.",
                hint="Retry the analysis to fill in the missing details.",
            ))

        normalized: dict[tuple[str, str, str], dict[str, Any]] = {}
        for package in eligible:
            key = (package["name"], package["version"])
            for vulnerability_id in ids_by_key.get(key, []):
                vulnerability = details_by_id[vulnerability_id]
                if vulnerability.get("withdrawn"):
                    # OSV marks retracted advisories with "withdrawn"; reporting them is a false positive.
                    if vulnerability_id not in report.withdrawn_advisories:
                        report.withdrawn_advisories.append(vulnerability_id)
                    continue
                item = normalize_vulnerability(vulnerability, package)
                if vulnerability.get("_stub"):
                    item["details_unavailable"] = True
                normalized[(package["id"], vulnerability_id, package["version"])] = item
        return sorted(
            normalized.values(),
            key=lambda v: (SEVERITY_RANK.get(v["severity"], 4), -(v.get("cvss_score") or 0), v["package_name"], str(v["id"])),
        )
    finally:
        if owns_client:
            await osv.close()
