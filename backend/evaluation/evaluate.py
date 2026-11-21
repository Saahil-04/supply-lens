"""Pure helpers for the evaluation: flatten results, summarize, sample, score. No network."""
from __future__ import annotations

import csv
import math
import random
from collections import Counter
from typing import Any

FINDING_COLUMNS = ["repo", "commit", "advisory", "package", "version", "severity", "cvss_score", "is_direct", "is_dev",
                   "reachability", "confidence", "via", "evidence_files", "package_path", "lockfile", "priority", "baseline_priority"]
DOWNGRADED = ("not_imported", "tests_or_tooling_only", "dev_only")


def flatten(result: dict[str, Any], repo: str) -> list[dict[str, Any]]:
    rows = []
    for v in result.get("vulnerabilities", []):
        reach = v.get("reachability") or {}
        rows.append({
            "repo": repo, "commit": (result.get("repository") or {}).get("commit_sha", "")[:10], "advisory": v.get("id"),
            "package": v.get("package_name"), "version": v.get("installed_version"), "severity": v.get("severity"),
            "cvss_score": v.get("cvss_score"), "is_direct": bool(v.get("is_direct")), "is_dev": bool(v.get("is_dev")),
            "reachability": reach.get("status", "unknown"), "confidence": reach.get("confidence", "none"),
            "via": reach.get("via") or "", "evidence_files": ";".join(reach.get("files", [])),
            "package_path": v.get("package_path"), "lockfile": v.get("lockfile"), "priority": v.get("priority"), "baseline_priority": v.get("baseline_priority"),
        })
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Headline numbers for the report. P1 = 'Fix now'."""
    total = len(rows)
    if not total:
        return {"findings": 0}
    reach = Counter(r["reachability"] for r in rows)
    base_p1 = sum(1 for r in rows if r["baseline_priority"] == 1)
    ctx_p1 = sum(1 for r in rows if r["priority"] == 1)
    downgraded = sum(1 for r in rows if r["priority"] is not None and r["baseline_priority"] is not None and r["priority"] > r["baseline_priority"])
    known = total - reach.get("unknown", 0)
    return {
        "findings": total,
        "unique_advisories": len({r["advisory"] for r in rows}),
        "direct_pct": round(100 * sum(r["is_direct"] for r in rows) / total, 1),
        "transitive_pct": round(100 * sum(not r["is_direct"] for r in rows) / total, 1),
        "dev_pct": round(100 * sum(r["is_dev"] for r in rows) / total, 1),
        "reachability_counts": dict(reach),
        "reachability_known_pct": round(100 * known / total, 1),
        "baseline_p1": base_p1, "context_p1": ctx_p1,
        "p1_reduction_pct": round(100 * (base_p1 - ctx_p1) / base_p1, 1) if base_p1 else None,
        "downgraded_findings": downgraded,
        "downgraded_pct": round(100 * downgraded / total, 1),
    }


def sample_for_validation(rows: list[dict[str, Any]], per_status: int = 10, seed: int = 7) -> list[dict[str, Any]]:
    """Stratified random sample (up to ``per_status`` per reachability status) for manual labelling."""
    rng = random.Random(seed)
    sample: list[dict[str, Any]] = []
    for status in ("imported", "transitive_of_imported", "tests_or_tooling_only", "not_imported", "dev_only"):
        pool = [r for r in rows if r["reachability"] == status]
        sample.extend(rng.sample(pool, min(per_status, len(pool))))
    return [{**r, "manual_label": ""} for r in sample]


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a proportion; honest about small samples."""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (round(max(0.0, centre - margin), 3), round(min(1.0, centre + margin), 3))


def score_validation(labelled: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare the tool's claim with the manual label.

    manual_label values: ``used`` (the package really is used by shipped code),
    ``not_used`` (it is not), ``unsure`` (excluded). The tool's claim is 'used' for
    imported/transitive_of_imported and 'not used' for the downgraded statuses.
    """
    out: dict[str, Any] = {}
    for group, claim_used in (("claims_used", True), ("claims_not_used", False)):
        statuses = ("imported", "transitive_of_imported") if claim_used else DOWNGRADED
        rows = [r for r in labelled if r["reachability"] in statuses and r.get("manual_label") in ("used", "not_used")]
        correct = sum(1 for r in rows if (r["manual_label"] == "used") == claim_used)
        out[group] = {"n": len(rows), "correct": correct, "precision": round(correct / len(rows), 3) if rows else None,
                      "ci95": wilson(correct, len(rows))}
    wrong_downgrades = [r for r in labelled if r["reachability"] in DOWNGRADED and r.get("manual_label") == "used"]
    out["dangerous_errors"] = {"count": len(wrong_downgrades), "description": "downgraded by the tool, but actually used (false sense of safety)",
                               "examples": [f"{r['repo']}: {r['package']}" for r in wrong_downgrades[:10]]}
    out["unsure_excluded"] = sum(1 for r in labelled if r.get("manual_label") == "unsure")
    return out


def write_csv(path: str, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: str) -> list[dict[str, Any]]:
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))
