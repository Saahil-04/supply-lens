"""pnpm lockfile parsing into SupplyLens' normalized dependency graph.

Supported formats (each verified against real lockfiles in ``tests/fixtures``):

* **5.x**  (pnpm 6/7)  - keys ``/name/1.2.3`` and ``/name/1.2.3_peer@1``; ``specifiers`` block.
* **6.0**  (pnpm 8)    - keys ``/name@1.2.3`` and ``/name@1.2.3(peer@1)``; deps inside ``packages``.
* **7-9**  (pnpm 9/10) - keys ``name@1.2.3(peer@1)``; ``packages`` (metadata) + ``snapshots`` (edges).

Single-project lockfiles written by pnpm <= 8 have *no* ``importers`` section: the root
project's dependencies sit at the top level. That layout is normalized into
``importers["."]`` so direct dependencies resolve for them too.

Versions newer than 9 are attempted but validated: if the reference resolution rate is
poor we refuse (a wrong graph is worse than an explicit error); otherwise we warn.
"""
from __future__ import annotations

import posixpath
import re
from collections import deque
from dataclasses import dataclass
from typing import Any, Iterable

import yaml

from app.analysis.dependencies import (
    SOURCE_FILE, SOURCE_GIT, SOURCE_REGISTRY, DependencyNode, classify_source,
)
from app.analysis.graph import DependencyEdge, DependencyGraph, DependencyType, add_edge
from app.errors import Diagnostic, LockfileError

MIN_SUPPORTED_MAJOR = 5
MAX_TESTED_MAJOR = 9
IMPORTER_SECTIONS = (
    ("dependencies", DependencyType.NORMAL, "prod"),
    ("devDependencies", DependencyType.NORMAL, "dev"),
    ("optionalDependencies", DependencyType.OPTIONAL, "optional"),
)
_PEER_SPLIT = re.compile(r"[_(]")
_SEMVER_HEAD = re.compile(r"^v?\d+(\.\d+){0,2}")


# --------------------------------------------------------------------------- helpers
def _lockfile_major(raw_version: Any) -> int:
    match = re.match(r"^\s*(\d+)", str(raw_version)) if raw_version is not None else None
    if not match:
        raise LockfileError(
            "LOCKFILE_VERSION_INVALID",
            f"Missing or unreadable pnpm lockfileVersion: {raw_version!r}.",
            hint="Regenerate the lockfile with `pnpm install --lockfile-only`.",
        )
    return int(match.group(1))


def _semantic_version(version: str) -> str:
    """Strip pnpm's peer-context suffix: ``1.0.0(react@18)`` or ``1.0.0_react@18`` -> ``1.0.0``."""
    return _PEER_SPLIT.split(version, maxsplit=1)[0]


def _identity_from_key(lock_key: str, major: int) -> tuple[str, str]:
    """Return (name, semantic version) parsed from a ``packages``/``snapshots`` key."""
    key = lock_key.lstrip("/")
    if major >= 6:
        # name@version(peer-context). A leading '@' belongs to a scope, so search from 1.
        separator = key.find("@", 1)
        if separator > 0:
            return key[:separator], _semantic_version(key[separator + 1:])
        # Early pnpm 7/8 builds labelled slash-style keys "6.0"; fall through for those.
    name, slash, version = key.rpartition("/")
    if slash and name and version:
        return name, _semantic_version(version)
    raise ValueError(f"Invalid pnpm package key: {lock_key}")


def _reference_text(value: Any) -> str | None:
    if isinstance(value, dict):
        value = value.get("version")
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    text = str(value).strip()
    return text or None


def _resolution_source(metadata: dict[str, Any], tarball: str | None, version: str) -> str:
    resolution = metadata.get("resolution")
    if isinstance(resolution, dict):
        if resolution.get("type") == "git" or "repo" in resolution:
            return SOURCE_GIT
        if resolution.get("type") == "directory" or "directory" in resolution:
            return SOURCE_FILE
    return classify_source(tarball, version)


@dataclass
class _Index:
    by_key: dict[str, str]                       # normalized key -> graph path
    by_name: dict[str, list[tuple[str, str]]]    # name -> [(semantic version, graph path)]


@dataclass
class _Resolved:
    path: str | None = None
    ambiguous: bool = False


def _resolve_reference(name: str, reference: str, index: _Index) -> _Resolved:
    """Find the lockfile entry a dependency reference points at.

    Handles every shape pnpm writes: a bare version (``1.2.0``), a peer-qualified version
    (``1.2.0(react@18)``), npm aliases (``strip-ansi@6.0.1`` / ``/strip-ansi/6.0.1``),
    and absolute keys (``/foo@1.0.0``).
    """
    ref = reference.strip()
    bare = ref.lstrip("/")
    for candidate in (bare, f"{name}@{bare}", f"{name}/{bare}"):
        path = index.by_key.get(candidate)
        if path:
            return _Resolved(path)

    # Fallback: match by (name, semantic version), e.g. a reference that omits peer context.
    target_name, version = name, bare
    at = bare.find("@", 1)
    if at > 0 and not _SEMVER_HEAD.match(bare):          # alias: real-name@version
        target_name, version = bare[:at], bare[at + 1:]
    elif "/" in bare and _SEMVER_HEAD.match(bare.rpartition("/")[2]):   # v5 alias: real-name/version
        target_name, _, version = bare.rpartition("/")
    semantic = _semantic_version(version)
    matches = sorted(path for sem, path in index.by_name.get(target_name, []) if sem == semantic)
    if not matches:
        return _Resolved()
    return _Resolved(matches[0], ambiguous=len(matches) > 1)


def _link_target(importer: str, reference: str) -> str:
    """Resolve ``link:../b`` relative to the importer's directory (both repo-relative)."""
    return posixpath.normpath(posixpath.join(importer or ".", reference[len("link:"):]))


def _collect_importers(lock: dict[str, Any]) -> dict[str, dict[str, Any]]:
    importers: dict[str, dict[str, Any]] = {}
    declared = lock.get("importers")
    if isinstance(declared, dict):
        importers.update({k: v for k, v in declared.items() if isinstance(k, str) and isinstance(v, dict)})
    # pnpm <= 8 without a workspace: the root project lives at the top level.
    if "." not in importers and any(isinstance(lock.get(section), dict) for section, _, _ in IMPORTER_SECTIONS):
        importers["."] = {section: lock[section] for section, _, _ in IMPORTER_SECTIONS if isinstance(lock.get(section), dict)}
    return importers


def _reach(adjacency: dict[str, list[tuple[str, DependencyType]]], roots: Iterable[str], *, skip_optional: bool) -> set[str]:
    seen: set[str] = set()
    pending = deque(roots)
    while pending:
        current = pending.popleft()
        if current in seen:
            continue
        seen.add(current)
        for target, edge_type in adjacency.get(current, ()):
            if skip_optional and edge_type == DependencyType.OPTIONAL:
                continue
            if target not in seen:
                pending.append(target)
    return seen


def _derive_scope_flags(graph: DependencyGraph, roots: dict[str, set[str]], legacy_dev: dict[str, bool | None]) -> None:
    """Compute dev/optional per package from importer reachability.

    pnpm 9 dropped the per-package ``dev``/``optional`` flags, so the only trustworthy source
    is "which importer sections can reach this package". A package is *dev* only when no
    production dependency reaches it, and *optional* only when it is reachable solely
    through optional edges.
    """
    adjacency: dict[str, list[tuple[str, DependencyType]]] = {}
    for edge in graph.edges:
        adjacency.setdefault(edge.source, []).append((edge.target, edge.dependency_type))
    prod = _reach(adjacency, roots["prod"] | roots["optional"], skip_optional=False)
    dev = _reach(adjacency, roots["dev"], skip_optional=False)
    required = _reach(adjacency, roots["prod"] | roots["dev"], skip_optional=True)
    reached = prod | dev
    for path, node in graph.nodes.items():
        if path in reached:
            node.dev = path in dev and path not in prod
            node.optional = path not in required
            node.dev_optional = False
        else:
            # Not reachable from any importer: fall back to what the lockfile recorded.
            node.dev = legacy_dev.get(path)
            node.optional = None
            node.dev_optional = None


# --------------------------------------------------------------------------- graph
def build_pnpm_dependency_graph(lockfile_data: dict[str, Any]) -> DependencyGraph:
    if not isinstance(lockfile_data, dict):
        raise LockfileError("LOCKFILE_INVALID", "pnpm lockfile must contain a YAML mapping")
    raw_version = lockfile_data.get("lockfileVersion")
    major = _lockfile_major(raw_version)
    if major < MIN_SUPPORTED_MAJOR:
        raise LockfileError(
            "LOCKFILE_VERSION_UNSUPPORTED",
            f"Unsupported pnpm lockfileVersion {raw_version!r}; supported formats are v5, v6 and v7-v9.",
            hint="Upgrade pnpm and regenerate the lockfile (`pnpm install --lockfile-only`).",
        )

    package_data = lockfile_data.get("packages") or {}
    snapshots = lockfile_data.get("snapshots") or {}
    if not isinstance(package_data, dict) or not isinstance(snapshots, dict):
        raise LockfileError("LOCKFILE_INVALID", "pnpm lockfile packages/snapshots sections must be mappings")

    graph = DependencyGraph()
    modern = major >= 7
    if major > MAX_TESTED_MAJOR:
        graph.diagnostics.append(Diagnostic(
            "LOCKFILE_VERSION_UNTESTED", "warning",
            f"pnpm lockfileVersion {raw_version!r} is newer than the versions this analyzer was validated against (5-9); "
            "it was parsed with the v9 rules and may be incomplete.",
        ))
    if modern and package_data and not snapshots:
        graph.diagnostics.append(Diagnostic(
            "PNPM_SNAPSHOTS_MISSING", "warning",
            "The lockfile lists packages but has no 'snapshots' section, so transitive dependency edges are unavailable.",
            hint="Regenerate the lockfile with a current pnpm (`pnpm install --lockfile-only`).",
        ))

    index = _Index(by_key={}, by_name={})
    legacy_dev: dict[str, bool | None] = {}
    skipped_keys = 0

    # Modern lockfiles: `snapshots` keys are the installed instances (with peer context) and
    # `packages` keys are shared metadata WITHOUT peer context. Taking the union would add a
    # phantom duplicate node per peer-qualified package, so instances come from snapshots and
    # metadata is looked up by the peer-stripped key. Packages that have no snapshot are kept.
    if modern and snapshots:
        covered = {str(k).split("(", 1)[0] for k in snapshots}
        lock_keys = sorted(set(snapshots) | {k for k in package_data if str(k).split("(", 1)[0] not in covered}, key=str)
    else:
        lock_keys = sorted(set(package_data) | set(snapshots), key=str)

    for lock_key in lock_keys:
        if not isinstance(lock_key, str):
            graph.unresolved.append({"from": "<lockfile>", "dependency": "<invalid package key>", "reason": "package key is not a string"})
            continue
        metadata = package_data.get(lock_key) or (package_data.get(lock_key.split("(", 1)[0]) if modern else None) or {}
        snapshot = (snapshots.get(lock_key) or {}) if modern else metadata
        if not isinstance(metadata, dict) or not isinstance(snapshot, dict):
            graph.unresolved.append({"from": lock_key, "dependency": "<invalid package metadata>", "reason": "entry is not a mapping"})
            continue
        try:
            name, version = _identity_from_key(lock_key, major)
        except ValueError as exc:
            graph.unresolved.append({"from": lock_key, "dependency": str(exc), "reason": "unrecognized package key format"})
            continue
        # Registry keys carry name+version; git/tarball packages carry them as fields instead.
        if isinstance(metadata.get("name"), str) and metadata["name"]:
            name = metadata["name"]
        if isinstance(metadata.get("version"), str) and metadata["version"]:
            version = metadata["version"]
        if not version:
            skipped_keys += 1
            graph.unresolved.append({"from": lock_key, "dependency": f"Missing version in pnpm package key: {lock_key}", "reason": "no version"})
            continue

        resolution = metadata.get("resolution") if isinstance(metadata.get("resolution"), dict) else {}
        tarball = resolution.get("tarball") if isinstance(resolution.get("tarball"), str) else None
        path = "pnpm/" + lock_key.lstrip("/")
        dependencies = snapshot.get("dependencies") if isinstance(snapshot.get("dependencies"), dict) else {}
        optional = snapshot.get("optionalDependencies") if isinstance(snapshot.get("optionalDependencies"), dict) else {}
        peers = metadata.get("peerDependencies") if isinstance(metadata.get("peerDependencies"), dict) else {}
        peers_meta = metadata.get("peerDependenciesMeta") if isinstance(metadata.get("peerDependenciesMeta"), dict) else {}
        graph.nodes[path] = DependencyNode(
            name=name, version=version, path=path,
            resolved=tarball,
            integrity=resolution.get("integrity") if isinstance(resolution.get("integrity"), str) else None,
            dependencies=dependencies, optional_dependencies=optional,
            peer_dependencies=peers, peer_dependencies_meta=peers_meta,
            source=_resolution_source(metadata, tarball, version),
        )
        if isinstance(metadata.get("dev"), bool):
            legacy_dev[path] = metadata["dev"]
        index.by_key[lock_key.lstrip("/")] = path
        index.by_name.setdefault(name, []).append((version, path))

    ambiguous = 0
    attempted = 0
    resolved_count = 0

    # Package -> package edges.
    for path, node in graph.nodes.items():
        groups = (
            ({k: v for k, v in node.dependencies.items() if k not in node.optional_dependencies}, DependencyType.NORMAL),
            (node.optional_dependencies, DependencyType.OPTIONAL),
        )
        for dependencies, edge_type in groups:
            for dependency_name, reference in sorted(dependencies.items()):
                text = _reference_text(reference)
                attempted += 1
                if text is None or text.startswith("link:"):
                    # Links out of the lockfile (workspace/injected) are not package instances.
                    resolved_count += 1
                    continue
                found = _resolve_reference(dependency_name, text, index)
                if found.path:
                    resolved_count += 1
                    ambiguous += found.ambiguous
                    kind = DependencyType.PEER if dependency_name in node.peer_dependencies and edge_type == DependencyType.NORMAL else edge_type
                    if found.path != path:
                        add_edge(graph, path, found.path, kind)
                elif edge_type == DependencyType.NORMAL:
                    graph.unresolved.append({
                        "from": path, "dependency": dependency_name, "dependency_type": edge_type.value,
                        "reason": f"reference {text!r} does not match any package in the lockfile",
                    })

    # Importers (workspace projects): direct dependencies per project directory.
    roots: dict[str, set[str]] = {"prod": set(), "dev": set(), "optional": set()}
    importers = _collect_importers(lockfile_data)
    for importer_path, importer in importers.items():
        direct: dict[str, str] = {}
        links: dict[str, str] = {}
        for section, edge_type, role in IMPORTER_SECTIONS:
            values = importer.get(section)
            if not isinstance(values, dict):
                continue
            for dependency_name, reference in values.items():
                text = _reference_text(reference)
                attempted += 1
                if text is None:
                    graph.unresolved.append({"from": importer_path or ".", "dependency": str(dependency_name), "dependency_type": edge_type.value, "reason": "no resolved version recorded"})
                    continue
                if text.startswith("link:"):
                    resolved_count += 1
                    links[dependency_name] = _link_target(importer_path, text)
                    continue
                found = _resolve_reference(dependency_name, text, index)
                if found.path:
                    resolved_count += 1
                    ambiguous += found.ambiguous
                    direct[dependency_name] = found.path
                    roots[role].add(found.path)
                elif edge_type == DependencyType.NORMAL:
                    graph.unresolved.append({
                        "from": importer_path or ".", "dependency": dependency_name, "dependency_type": edge_type.value,
                        "reason": f"reference {text!r} does not match any package in the lockfile",
                    })
        graph.importer_dependencies[importer_path] = direct
        if links:
            graph.workspace_links[importer_path] = links

    if importers:
        _derive_scope_flags(graph, roots, legacy_dev)
    else:
        for path, node in graph.nodes.items():
            node.dev = legacy_dev.get(path)

    if ambiguous:
        graph.diagnostics.append(Diagnostic(
            "PNPM_AMBIGUOUS_REFERENCE", "info",
            f"{ambiguous} dependency reference(s) matched several peer-context variants of the same version; "
            "the first variant was used (the package name and version are identical, only peer context differs).",
        ))
    if major > MAX_TESTED_MAJOR and attempted and resolved_count / attempted < 0.5:
        raise LockfileError(
            "LOCKFILE_FORMAT_MISMATCH",
            f"pnpm lockfileVersion {raw_version!r} could not be interpreted: only {resolved_count} of {attempted} "
            "dependency references matched a package entry, so the format has probably changed.",
            hint="This analyzer was validated against pnpm lockfile v5-v9. Please report the pnpm version used.",
        )
    return graph


# --------------------------------------------------------------------------- parsing
def _merge_yaml_mapping(target: dict[str, Any], incoming: dict[str, Any], *, path: str) -> None:
    """Merge mapping sections from pnpm's multi-document lockfile stream.

    pnpm can emit a preliminary document containing package-manager/config
    dependencies followed by the main workspace lockfile. Both documents may
    define ``importers``, ``packages`` and ``snapshots``. Those sections must
    be merged recursively by key; replacing them loses data, while rejecting
    every duplicate top-level key rejects valid pnpm lockfiles.

    Conflicting scalar leaves are still rejected so malformed or genuinely
    inconsistent lockfiles cannot silently overwrite earlier values.
    """
    for key, value in incoming.items():
        child_path = f"{path}.{key}" if path else str(key)
        if key not in target:
            target[key] = value
            continue

        existing = target[key]
        if isinstance(existing, dict) and isinstance(value, dict):
            _merge_yaml_mapping(existing, value, path=child_path)
        elif existing == value:
            continue
        elif child_path == "lockfileVersion":
            # Documents of one stream may disagree on the format revision; keep the newer.
            if str(value) > str(existing):
                target[key] = value
        else:
            raise ValueError(
                f"Invalid pnpm YAML lockfile: conflicting value at {child_path!r} "
                "across YAML documents"
            )


_ALIAS_HINT = re.compile(r"(?m)(?:^|[\s\[{,:-])[&*][A-Za-z0-9_]")
_YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)   # libyaml: ~10x faster on multi-MB lockfiles


def _reject_yaml_aliases(raw: str) -> None:
    """pnpm never writes YAML anchors/aliases; refusing them blocks 'billion laughs' payloads.

    Lockfiles come from arbitrary public repositories, so alias expansion is an
    availability risk. The cheap regex runs first; the event pass only runs on a hit.
    """
    if not _ALIAS_HINT.search(raw):
        return
    for event in yaml.parse(raw, Loader=_YAML_LOADER):
        if isinstance(event, yaml.AliasEvent):
            raise LockfileError(
                "LOCKFILE_UNSAFE_YAML",
                "The pnpm lockfile uses YAML anchors/aliases, which pnpm never writes; it was not expanded.",
                hint="Regenerate the lockfile with `pnpm install --lockfile-only`.",
            )


def parse_pnpm_lockfile(raw: str) -> dict[str, Any]:
    """Parse pnpm's YAML stream, merging sections across documents safely.

    Some pnpm-generated lockfiles contain a preliminary document and a main
    project document separated by ``---``. Duplicate mapping sections are
    merged recursively (including importer paths and package/snapshot keys).
    Conflicting leaf values are rejected rather than silently overwritten.
    """
    try:
        _reject_yaml_aliases(raw)
        documents = list(yaml.load_all(raw, Loader=_YAML_LOADER))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid pnpm YAML lockfile: {exc}") from exc

    merged: dict[str, Any] = {}
    for index, document in enumerate(documents, start=1):
        if document is None:
            continue
        if not isinstance(document, dict):
            raise ValueError(
                f"Invalid pnpm YAML lockfile: document {index} must contain a mapping"
            )
        _merge_yaml_mapping(merged, document, path="")

    if not merged:
        raise ValueError("pnpm lockfile must contain a YAML mapping")
    if "lockfileVersion" not in merged:
        raise ValueError("pnpm lockfile is missing lockfileVersion")
    return merged
