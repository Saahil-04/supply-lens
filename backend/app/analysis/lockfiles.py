"""One entry point that turns any supported lockfile into a graph plus diagnostics.

Never raises for bad input: a lockfile that cannot be analyzed comes back with
``graph=None`` and an ``error`` diagnostic that tells the frontend what is wrong and
what the user can do about it. CPU-heavy parsing runs in a worker thread so large
lockfiles do not freeze the event loop for other requests.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field

from app.analysis.graph import DependencyGraph, build_dependency_graph
from app.analysis.npm import normalize_npm_lockfile
from app.analysis.pnpm import build_pnpm_dependency_graph, parse_pnpm_lockfile
from app.errors import Diagnostic, LockfileError

NPM_LOCKFILES = frozenset({"package-lock.json", "npm-shrinkwrap.json"})
PNPM_LOCKFILES = frozenset({"pnpm-lock.yaml"})
SUPPORTED_LOCKFILES = NPM_LOCKFILES | PNPM_LOCKFILES
MAX_LOCKFILE_BYTES = 50 * 1024 * 1024


@dataclass
class LockfileLoad:
    path: str
    format: str  # npm | pnpm | yarn | unknown
    graph: DependencyGraph | None = None
    lockfile_version: str | None = None
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.graph is not None


def lockfile_format(path: str) -> str:
    name = path.rsplit("/", 1)[-1]
    if name in NPM_LOCKFILES:
        return "npm"
    if name in PNPM_LOCKFILES:
        return "pnpm"
    if name == "yarn.lock":
        return "yarn"
    return "unknown"


def unsupported_lockfile_diagnostic(path: str) -> Diagnostic:
    fmt = lockfile_format(path)
    if fmt == "yarn":
        return Diagnostic(
            "LOCKFILE_YARN_UNSUPPORTED", "warning",
            f"{path} is a Yarn lockfile; Yarn is not supported yet, so its dependencies were not resolved.",
            path=path,
            hint="Commit a package-lock.json or pnpm-lock.yaml for full analysis (`npm install --package-lock-only`).",
        )
    name = path.rsplit("/", 1)[-1]
    return Diagnostic(
        "LOCKFILE_UNSUPPORTED", "warning",
        f"{path} was discovered but {name} is not supported for resolved dependency graph analysis yet.",
        path=path,
    )


def parse_lockfile(path: str, raw: str) -> LockfileLoad:
    fmt = lockfile_format(path)
    load = LockfileLoad(path=path, format=fmt)
    if fmt not in ("npm", "pnpm"):
        load.diagnostics.append(unsupported_lockfile_diagnostic(path))
        return load
    if len(raw) > MAX_LOCKFILE_BYTES:
        load.diagnostics.append(Diagnostic(
            "LOCKFILE_TOO_LARGE", "error",
            f"{path} is larger than {MAX_LOCKFILE_BYTES // (1024 * 1024)} MB and was skipped.", path=path,
        ))
        return load
    if not raw.strip():
        load.diagnostics.append(Diagnostic(
            "LOCKFILE_EMPTY_FILE", "error", f"{path} is empty.", path=path,
            hint="Regenerate it with your package manager and commit it.",
        ))
        return load
    try:
        if fmt == "pnpm":
            data = parse_pnpm_lockfile(raw)
            load.lockfile_version = str(data.get("lockfileVersion"))
            graph = build_pnpm_dependency_graph(data)
        else:
            data = json.loads(raw)
            packages, version, notes, problems = normalize_npm_lockfile(data)
            load.lockfile_version = None if version is None else str(version)
            load.diagnostics.extend(notes)
            graph = build_dependency_graph(packages)
            graph.unresolved.extend(problems)
    except json.JSONDecodeError as exc:
        load.diagnostics.append(Diagnostic(
            "LOCKFILE_PARSE_ERROR", "error",
            f"{path} is not valid JSON ({exc.msg} at line {exc.lineno}, column {exc.colno}).", path=path,
            hint="Merge-conflict markers are a common cause; regenerate the lockfile.",
        ))
        return load
    except LockfileError as exc:
        load.diagnostics.append(Diagnostic(exc.code, "error", f"Could not analyze lockfile {path}: {exc}", path=path, hint=exc.hint))
        return load
    except (ValueError, TypeError, KeyError, RecursionError) as exc:
        load.diagnostics.append(Diagnostic(
            "LOCKFILE_PARSE_ERROR", "error", f"Could not analyze lockfile {path}: {exc}", path=path,
        ))
        return load
    load.graph = graph
    load.diagnostics.extend(graph.diagnostics)
    for diagnostic in load.diagnostics:
        diagnostic.path = diagnostic.path or path
    return load


async def load_lockfile(path: str, raw: str) -> LockfileLoad:
    return await asyncio.to_thread(parse_lockfile, path, raw)
