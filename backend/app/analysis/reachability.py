"""Package-level reachability: does the project's own code actually use the vulnerable package?

Scope and honesty
-----------------
This is *package-level* reachability, not function-level. For each finding we decide whether
the vulnerable package (or a direct dependency that pulls it in) is imported by the project's
source files. It cannot tell whether the vulnerable *function* is called, and it uses regular
expressions rather than a JavaScript parser, so dynamic requires (``require(variable)``) and
usage through configuration files are invisible. Because of that:

* a package is only reported ``not_imported`` when EVERY source file of the owning project was
  scanned; if the file budget truncated the scan the status is ``unknown``;
* every status carries a ``confidence`` and the evidence (files) it is based on.

Statuses (most to least reachable)
    imported                  a direct dependency imported by production code
    transitive_of_imported    a transitive package whose parent dependency is imported by production code
    tests_or_tooling_only     only used by test/config/script files or npm scripts
    dev_only                  a development dependency (never ships)
    not_imported              all source scanned; nothing imports it
    unknown                   not enough information to say (no source, truncated scan, no graph)
"""
from __future__ import annotations

import asyncio
import os
import re
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from app.analysis.graph import DependencyGraph
from app.errors import Diagnostic

SOURCE_EXTENSIONS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts", ".vue", ".svelte")
EXCLUDED_SEGMENTS = frozenset({"node_modules", "dist", "build", ".next", ".nuxt", "out", "coverage", "vendor", ".turbo", ".git", "storybook-static"})
MAX_FILE_BYTES = 400 * 1024
FETCH_CONCURRENCY = 10
EXAMPLES_PER_CLASS = 5
DEFAULT_MAX_FILES = int(os.getenv("REACHABILITY_MAX_FILES", "600"))

PRODUCTION, TEST, TOOLING = "production", "test", "tooling"
_CLASS_RANK = {PRODUCTION: 0, TOOLING: 1, TEST: 2}
_TEST_DIRS = frozenset({"test", "tests", "__tests__", "__mocks__", "spec", "specs", "e2e", "cypress", "fixtures", "__fixtures__", "stories", "playwright"})
_TOOLING_DIRS = frozenset({"scripts", "tools", "tooling", "bin", "config", ".storybook", ".github"})
_TEST_FILE = re.compile(r"\.(test|spec|stories|story|e2e|cy)\.[^/]+$", re.I)
_TOOLING_FILE = re.compile(r"(^|/)(\.?[\w-]*\.config(\.[\w-]+)?\.(c|m)?[jt]s|\.[\w-]+rc\.(c|m)?js|gulpfile[\w.]*|gruntfile[\w.]*|jest\.setup[\w.]*|setup-?tests?[\w.]*)$", re.I)

STATUS_RANK = {"imported": 0, "transitive_of_imported": 1, "tests_or_tooling_only": 2, "dev_only": 3, "not_imported": 4, "unknown": 5}
DOWNGRADED = frozenset({"not_imported", "tests_or_tooling_only", "dev_only"})
TIER_BY_SEVERITY = {"CRITICAL": 1, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "UNKNOWN": 2}
PRIORITY_LABELS = {1: "Fix now", 2: "Fix soon", 3: "Plan", 4: "Monitor"}


# --------------------------------------------------------------------------- parsing
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_LINE_COMMENT = re.compile(r"(?m)(^|[\s;{}()])//[^\n]*")
# `import type ... from "x"` / `export type ... from "x"` are erased by the compiler: no runtime load.
_TYPE_ONLY = re.compile(r"""\b(?:import|export)\s+type\b[^;'"]*?\bfrom\s*['"][^'"\n]+['"]""", re.S)
_STATIC = re.compile(r"""(?:\bfrom|\bimport)\s*['"]([^'"\n]+)['"]""")
_CALL = re.compile(r"""\b(?:require|require\.resolve|import)\s*\(\s*['"]([^'"\n]+)['"]\s*\)""")
_PACKAGE = re.compile(r"^(@[a-z0-9][a-z0-9._~-]*/[a-z0-9][a-z0-9._~-]*|[a-z0-9][a-z0-9._~-]*)(?:/.*)?$", re.I)


def package_name(specifier: str) -> str | None:
    """``lodash/fp`` -> ``lodash``; ``@scope/pkg/sub`` -> ``@scope/pkg``; relative/alias paths -> None."""
    if not specifier or specifier.startswith((".", "/", "#", "~", "@/", "node:", "http:", "https:", "data:")):
        return None
    match = _PACKAGE.match(specifier)
    return match.group(1) if match else None


def extract_imports(source: str) -> set[str]:
    """Package names a source file loads at runtime (regex based; see module docstring)."""
    text = _BLOCK_COMMENT.sub(" ", source)
    text = _LINE_COMMENT.sub(r"\1", text)
    text = _TYPE_ONLY.sub(" ", text)
    names: set[str] = set()
    for pattern in (_STATIC, _CALL):
        for specifier in pattern.findall(text):
            name = package_name(specifier.strip())
            if name:
                names.add(name)
    return names


def classify_file(path: str) -> str:
    lowered = path.lower()
    segments = lowered.split("/")
    if _TEST_FILE.search(lowered) or any(s in _TEST_DIRS for s in segments[:-1]):
        return TEST
    if _TOOLING_FILE.search(lowered) or any(s in _TOOLING_DIRS for s in segments[:-1]):
        return TOOLING
    return PRODUCTION


def script_tokens(manifest: dict[str, Any]) -> set[str]:
    """Words used in npm ``scripts`` (a dependency run via ``next dev`` is used, even if never imported)."""
    scripts = manifest.get("scripts") if isinstance(manifest, dict) else None
    tokens: set[str] = set()
    if isinstance(scripts, dict):
        for command in scripts.values():
            if isinstance(command, str):
                tokens.update(re.findall(r"@?[\w.-]+(?:/[\w.-]+)?", command))
    return tokens


# --------------------------------------------------------------------------- file selection
@dataclass
class ProjectUsage:
    imports: dict[str, dict[str, list[str]]] = field(default_factory=dict)   # package -> class -> files
    files_total: int = 0
    files_scanned: int = 0
    files_failed: int = 0
    non_production_scanned: int = 0

    @property
    def production_done(self) -> bool:
        """True when every production file was read. Files are scanned production-first, so having read a
        test or tooling file means the production files of this project were all read (barring failures)."""
        return self.files_failed == 0 and (self.complete or self.non_production_scanned > 0)

    @property
    def complete(self) -> bool:
        return self.files_total > 0 and self.files_scanned == self.files_total


def owning_root(path: str, roots_longest_first: list[str]) -> str | None:
    for root in roots_longest_first:
        if root == "" or path == root or path.startswith(root + "/"):
            return root
    return None


def select_source_files(
    tree: list[dict[str, Any]], target_roots: set[str], all_roots: list[str], max_files: int,
) -> tuple[list[tuple[str, dict[str, Any]]], dict[str, int]]:
    """Pick source files of the target projects, production code first, within a global budget.

    Returns ([(project_root, entry)], eligible_count_per_root). Files belong to the deepest
    project directory that contains them, so nested projects are not double counted.
    """
    roots = sorted(set(all_roots), key=len, reverse=True)
    eligible: list[tuple[int, str, str, dict[str, Any]]] = []
    totals: dict[str, int] = {}
    for entry in tree:
        path = entry.get("path") if isinstance(entry, dict) else None
        if not isinstance(path, str) or entry.get("type") != "blob" or not path.endswith(SOURCE_EXTENSIONS):
            continue
        if path.endswith((".d.ts", ".d.mts", ".d.cts", ".min.js")):
            continue
        segments = path.split("/")
        if any(segment in EXCLUDED_SEGMENTS for segment in segments[:-1]):
            continue
        if isinstance(entry.get("size"), int) and entry["size"] > MAX_FILE_BYTES:
            continue
        root = owning_root(path, roots)
        if root is None or root not in target_roots:
            continue
        totals[root] = totals.get(root, 0) + 1
        eligible.append((_CLASS_RANK[classify_file(path)], path, root, entry))
    # Fair share per project ("water-filling"): small projects are scanned completely, and the rest of the
    # budget is split evenly, so one large project cannot starve the others. Inside a project, production
    # files come first.
    by_root: dict[str, list[tuple[int, str, dict[str, Any]]]] = {}
    for rank, path, root, entry in eligible:
        by_root.setdefault(root, []).append((rank, path, entry))
    selected: list[tuple[str, dict[str, Any]]] = []
    remaining = max_files
    pending = sorted(by_root, key=lambda r: (len(by_root[r]), r))
    for index, root in enumerate(pending):
        share = max(0, remaining // (len(pending) - index))
        files = sorted(by_root[root], key=lambda item: (item[0], item[1]))[:share]
        selected.extend((root, entry) for _, _, entry in files)
        remaining -= len(files)
    return selected, totals


async def scan_sources(client: Any, owner: str, repository: str, selected: list[tuple[str, dict[str, Any]]],
                       totals: dict[str, int]) -> dict[str, ProjectUsage]:
    usage = {root: ProjectUsage(files_total=total) for root, total in totals.items()}
    gate = asyncio.Semaphore(FETCH_CONCURRENCY)

    async def one(root: str, entry: dict[str, Any]) -> None:
        async with gate:
            try:
                source = await client.get_file_content(owner, repository, entry["sha"])
            except Exception:                                     # noqa: BLE001 - counted, reported
                usage[root].files_failed += 1
                return
        names = await asyncio.to_thread(extract_imports, source)
        kind = classify_file(entry["path"])
        project = usage[root]
        project.files_scanned += 1
        if kind != PRODUCTION:
            project.non_production_scanned += 1
        for name in names:
            files = project.imports.setdefault(name, {}).setdefault(kind, [])
            if len(files) < EXAMPLES_PER_CLASS:
                files.append(entry["path"])

    await asyncio.gather(*(one(root, entry) for root, entry in selected))
    return usage


# --------------------------------------------------------------------------- assessment
def ancestor_paths(graph: DependencyGraph, target: str, budget: int = 50000) -> set[str]:
    """The package and everything that (transitively) depends on it."""
    seen = {target}
    queue = deque([target])
    while queue and budget:
        budget -= 1
        for parent in graph.reverse_edges.get(queue.popleft(), ()):
            if parent not in seen:
                seen.add(parent)
                queue.append(parent)
    return seen


def assess(owners: list[tuple[str, list[tuple[str, bool]]]], usage: dict[str, ProjectUsage],
           tokens_by_root: dict[str, set[str]], is_dev: bool | None) -> dict[str, Any]:
    """Decide the reachability status for one finding.

    ``owners`` lists, per project, the direct dependencies that are the vulnerable package itself
    (``True``) or one of its ancestors (``False``).
    """
    observed: list[tuple[str, str, str | None, list[str]]] = []      # (status, confidence, via, files)
    reasons: list[str] = []
    for root, dependencies in owners:
        project = usage.get(root)
        if project is None or project.files_scanned == 0:
            observed.append(("unknown", "none", None, []))
            reasons.append("no_source_files" if project is None else ("download_failed" if project.files_failed else "not_scanned_budget"))
            continue
        for name, is_target in dependencies:
            found = project.imports.get(name, {})
            production = found.get(PRODUCTION, [])
            other = found.get(TEST, []) + found.get(TOOLING, [])
            if production:
                observed.append(("imported" if is_target else "transitive_of_imported", "high" if is_target else "medium", name, production))
            elif other or name in tokens_by_root.get(root, set()):
                if project.production_done:
                    observed.append(("tests_or_tooling_only", "medium", name, other))
                else:                                           # production code may still use it in unread files
                    observed.append(("unknown", "none", None, []))
                    reasons.append("download_failed" if project.files_failed else "scan_incomplete")
            elif project.complete:
                observed.append(("not_imported", "medium", None, []))
            else:
                observed.append(("unknown", "none", None, []))
                reasons.append("download_failed" if project.files_failed else "scan_incomplete")
    reachable = [o for o in observed if o[0] in ("imported", "transitive_of_imported", "tests_or_tooling_only")]
    if reachable:
        status, confidence, via, files = min(reachable, key=lambda o: STATUS_RANK[o[0]])
    elif any(o[0] == "unknown" for o in observed) or not observed:
        status, confidence, via, files = "unknown", "none", None, []
    else:
        status, confidence, via, files = "not_imported", "medium", None, []
    # A dependency marked "dev" by the lockfile can still be bundled into shipped code (common in front-end
    # apps that list react/vue under devDependencies), so production evidence always wins over the dev flag.
    if is_dev and status not in ("imported", "transitive_of_imported"):
        status, confidence = "dev_only", "medium"        # a development dependency never ships
    result = {"status": status, "confidence": confidence, "via": via, "files": files[:EXAMPLES_PER_CLASS]}
    if status == "unknown":
        result["reason"] = reasons[0] if reasons else "no_direct_owner"
    return result


def prioritize(severity: str | None, is_malware: bool, status: str) -> dict[str, Any]:
    """Context-aware priority. P1 Fix now ... P4 Monitor. Also returns the severity-only baseline.

    Rule (a hypothesis the evaluation tests, not a fact): start from the severity tier
    (CRITICAL/HIGH=1, MEDIUM=2, LOW=3, UNKNOWN=2) and move one level down when the package is
    demonstrably not part of the shipped code path. Malware is always P1. Unknown reachability
    never lowers priority.
    """
    base = 1 if is_malware else TIER_BY_SEVERITY.get(str(severity or "UNKNOWN").upper(), 2)
    tier = base
    if not is_malware and status in DOWNGRADED:
        tier = min(4, base + 1)
    sev = str(severity or "UNKNOWN").upper()
    if tier == base:
        reason = "Malicious package." if is_malware else f"{sev} severity" + ("; reachability unknown, so priority is not lowered." if status == "unknown" else "; the code path is reachable.")
    else:
        why = {"not_imported": "no source file imports it", "tests_or_tooling_only": "it is only used by tests/tooling", "dev_only": "it is a development dependency"}[status]
        reason = f"{sev} severity, lowered one level because {why}."
    return {"priority": tier, "priority_label": PRIORITY_LABELS[tier], "priority_reason": reason,
            "baseline_priority": base, "baseline_label": PRIORITY_LABELS[base]}


def apply_priority_without_reachability(vulnerabilities: list[dict[str, Any]], note: str | None = None) -> None:
    for vuln in vulnerabilities:
        vuln["reachability"] = {"status": "unknown", "confidence": "none", "via": None, "files": [], **({"note": note} if note else {})}
        vuln.update(prioritize(vuln.get("severity"), bool(vuln.get("is_malware")), "unknown"))


async def run_reachability(
    client: Any, owner: str, repository: str, tree: list[dict[str, Any]],
    project_records: list[dict[str, Any]], project_graph_keys: dict[str, str], graphs: dict[str, DependencyGraph],
    manifests: dict[str, dict[str, Any]], vulnerabilities: list[dict[str, Any]], max_files: int = DEFAULT_MAX_FILES,
) -> tuple[dict[str, Any], list[Diagnostic]]:
    """Annotate every finding with ``reachability`` and ``priority``; return metadata + diagnostics."""
    diagnostics: list[Diagnostic] = []
    records = {record["path"]: record for record in project_records}
    owners_by_finding: list[list[tuple[str, list[tuple[str, bool]]]]] = []
    ancestor_cache: dict[tuple[str, str], set[str]] = {}
    target_roots: set[str] = set()
    for vuln in vulnerabilities:
        graph_key, path = vuln.get("lockfile"), vuln.get("package_path")
        graph = graphs.get(graph_key) if graph_key else None
        owners: list[tuple[str, list[tuple[str, bool]]]] = []
        if graph is not None and path in graph.nodes:
            ancestors = ancestor_cache.setdefault((graph_key, path), ancestor_paths(graph, path))
            for root, key in project_graph_keys.items():
                if key != graph_key or root not in records:
                    continue
                deps = [(d["name"], d["package_path"] == path) for d in records[root]["direct_dependencies"] if d.get("package_path") in ancestors]
                if deps:
                    owners.append((root, deps))
                    target_roots.add(root)
        owners_by_finding.append(owners)

    selected, totals = select_source_files(tree, target_roots, list(records), max_files)
    usage = await scan_sources(client, owner, repository, selected, totals) if selected else {}
    tokens = {root: script_tokens(manifests.get(root, {})) for root in target_roots}

    counts: dict[str, int] = {}
    unknown_reasons: dict[str, int] = {}
    for vuln, owners in zip(vulnerabilities, owners_by_finding):
        result = assess(owners, usage, tokens, vuln.get("is_dev"))
        vuln["reachability"] = result
        vuln.update(prioritize(vuln.get("severity"), bool(vuln.get("is_malware")), result["status"]))
        counts[result["status"]] = counts.get(result["status"], 0) + 1
        if result["status"] == "unknown":
            unknown_reasons[result["reason"]] = unknown_reasons.get(result["reason"], 0) + 1

    truncated = sorted(root or "(root)" for root, u in usage.items() if u.files_scanned + u.files_failed < u.files_total)
    failed = sum(u.files_failed for u in usage.values())
    no_source = sorted(root or "(root)" for root in target_roots if root not in totals)
    if truncated:
        diagnostics.append(Diagnostic(
            "REACHABILITY_TRUNCATED", "warning",
            f"Source scan stopped at the {max_files}-file budget for {len(truncated)} project(s); packages not found in the scanned "
            "files are reported as 'unknown' instead of 'not imported'.",
            details={"projects": truncated[:25], "max_files": max_files},
            hint="Raise REACHABILITY_MAX_FILES on the server (uses more GitHub API calls).",
        ))
    if failed:
        diagnostics.append(Diagnostic("REACHABILITY_FILES_FAILED", "warning",
                                      f"{failed} source file(s) could not be downloaded; affected projects are not treated as fully scanned.",
                                      hint="Retry the analysis."))
    if no_source:
        diagnostics.append(Diagnostic("REACHABILITY_NO_SOURCE", "info",
                                      f"No JavaScript/TypeScript source files were found for {len(no_source)} project(s) with findings; their reachability is 'unknown'.",
                                      details={"projects": no_source[:25]}))
    meta = {
        "enabled": True, "files_selected": len(selected), "files_scanned": sum(u.files_scanned for u in usage.values()),
        "files_failed": failed, "projects_scanned": len(usage), "projects_truncated": len(truncated), "max_files": max_files,
        "status_counts": counts, "unknown_reasons": unknown_reasons,
        "method": "package-level imports (regex); not function-level",
    }
    return meta, diagnostics
