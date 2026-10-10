"""OSV batch querying and normalization for resolved npm package instances."""
from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx

OSV_API_URL = "https://api.osv.dev/v1/querybatch"
OSV_VULN_URL = "https://api.osv.dev/v1/vulns"
BATCH_SIZE = 100
DETAIL_CONCURRENCY = 8


class OSVClient:
    def __init__(self, timeout: float = 20.0) -> None:
        self.client = httpx.AsyncClient(timeout=timeout)

    async def query_batch(self, queries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        response = await self.client.post(OSV_API_URL, json={"queries": queries})
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(results, list) or len(results) != len(queries):
            raise ValueError("OSV returned a malformed batch response")
        return results

    async def get_vulnerability(self, vulnerability_id: str) -> dict[str, Any]:
        """Fetch the full advisory; querybatch rows contain IDs, not advisory details."""
        response = await self.client.get(f"{OSV_VULN_URL}/{vulnerability_id}")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("id") != vulnerability_id:
            raise ValueError(f"OSV returned a malformed advisory record for {vulnerability_id}")
        return payload

    async def close(self) -> None:
        await self.client.aclose()


def _fixed_versions(vulnerability: dict[str, Any]) -> list[str]:
    versions: set[str] = set()
    for affected in vulnerability.get("affected", []) if isinstance(vulnerability.get("affected"), list) else []:
        for version in affected.get("versions", []) if isinstance(affected, dict) and isinstance(affected.get("versions"), list) else []:
            if isinstance(version, str):
                # Listed versions are affected, not fixed; do not recommend them as fixes.
                continue
        ranges = affected.get("ranges", []) if isinstance(affected, dict) else []
        for version_range in ranges if isinstance(ranges, list) else []:
            events = version_range.get("events", []) if isinstance(version_range, dict) else []
            for event in events if isinstance(events, list) else []:
                fixed = event.get("fixed") if isinstance(event, dict) else None
                if isinstance(fixed, str) and fixed:
                    versions.add(fixed)
    return sorted(versions)


def _severity(vulnerability: dict[str, Any]) -> tuple[str, float | None]:
    database_specific = vulnerability.get("database_specific", {})
    declared = database_specific.get("severity") if isinstance(database_specific, dict) else None
    if isinstance(declared, str) and declared.upper() in {"CRITICAL", "HIGH", "MEDIUM", "MODERATE", "LOW"}:
        normalized = "MEDIUM" if declared.upper() == "MODERATE" else declared.upper()
        return normalized, None
    scores: list[float] = []
    for item in vulnerability.get("severity", []) if isinstance(vulnerability.get("severity"), list) else []:
        raw = item.get("score") if isinstance(item, dict) else None
        if isinstance(raw, (int, float)):
            score = float(raw)
        elif isinstance(raw, str):
            try:
                score = float(raw)
            except ValueError:
                # OSV may supply a CVSS vector, not the numeric score itself.
                match = re.search(r"(?:^|/)([0-9]+\.[0-9]+)$", raw)
                if not match:
                    continue
                score = float(match.group(1))
        else:
            continue
        if 0 <= score <= 10:
            scores.append(score)
    if not scores:
        return "UNKNOWN", None
    score = max(scores)
    severity = "CRITICAL" if score >= 9 else "HIGH" if score >= 7 else "MEDIUM" if score >= 4 else "LOW"
    return severity, score


def normalize_vulnerability(vulnerability: dict[str, Any], package: dict[str, Any]) -> dict[str, Any]:
    severity, cvss_score = _severity(vulnerability)
    return {
        "id": vulnerability.get("id"),
        "aliases": vulnerability.get("aliases", []) if isinstance(vulnerability.get("aliases", []), list) else [],
        "summary": vulnerability.get("summary") or "No summary provided by OSV",
        "details": vulnerability.get("details"),
        "severity": severity,
        "cvss_score": cvss_score,
        "package_id": package["id"],
        "package_name": package["name"],
        "installed_version": package["version"],
        "package_path": package["path"],
        "lockfile": package["lockfile"],
        "fixed_versions": _fixed_versions(vulnerability),
        "references": [r.get("url") for r in vulnerability.get("references", []) if isinstance(r, dict) and isinstance(r.get("url"), str)] if isinstance(vulnerability.get("references", []), list) else [],
        "modified": vulnerability.get("modified"),
        "published": vulnerability.get("published"),
    }


async def scan_packages(packages: list[dict[str, Any]], client: OSVClient | None = None) -> list[dict[str, Any]]:
    """Query exact npm versions, fetch each unique full advisory once, then map to instances.

    OSV querybatch deliberately returns vulnerability identifiers and modified timestamps,
    not complete advisory records. A detail-fetch failure raises rather than silently
    presenting missing enrichment as a complete scan.
    """
    owns_client = client is None
    osv = client or OSVClient()
    eligible = [p for p in packages if isinstance(p.get("name"), str) and p["name"] and isinstance(p.get("version"), str) and p["version"]]
    query_keys = sorted({(p["name"], p["version"]) for p in eligible})
    ids_by_key: dict[tuple[str, str], list[str]] = {}
    try:
        for start in range(0, len(query_keys), BATCH_SIZE):
            chunk = query_keys[start:start + BATCH_SIZE]
            response_rows = await osv.query_batch([
                {"package": {"name": name, "ecosystem": "npm"}, "version": version}
                for name, version in chunk
            ])
            for key, row in zip(chunk, response_rows):
                vulns = row.get("vulns", []) if isinstance(row, dict) else []
                ids = [v.get("id") for v in vulns if isinstance(v, dict) and isinstance(v.get("id"), str) and v.get("id")] if isinstance(vulns, list) else []
                # Preserve order while deduplicating any repeated ID in a batch row.
                ids_by_key[key] = list(dict.fromkeys(ids))

        unique_ids = sorted({vuln_id for ids in ids_by_key.values() for vuln_id in ids})
        semaphore = asyncio.Semaphore(DETAIL_CONCURRENCY)

        async def fetch_detail(vulnerability_id: str) -> tuple[str, dict[str, Any]]:
            async with semaphore:
                try:
                    detail = await osv.get_vulnerability(vulnerability_id)
                except Exception as exc:
                    raise ValueError(f"OSV full-advisory lookup failed for {vulnerability_id}: {exc}") from exc
                return vulnerability_id, detail

        detail_pairs = await asyncio.gather(*(fetch_detail(vulnerability_id) for vulnerability_id in unique_ids))
        details_by_id = dict(detail_pairs)

        normalized: dict[tuple[str, str, str], dict[str, Any]] = {}
        for package in eligible:
            key = (package["name"], package["version"])
            for vulnerability_id in ids_by_key.get(key, []):
                vulnerability = details_by_id[vulnerability_id]
                item = normalize_vulnerability(vulnerability, package)
                normalized[(package["id"], vulnerability_id, package["version"])] = item
        return sorted(normalized.values(), key=lambda v: (v["severity"], v["package_name"], str(v["id"])))
    finally:
        if owns_client:
            await osv.close()
