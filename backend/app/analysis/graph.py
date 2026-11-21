from dataclasses import dataclass, field
import posixpath
from enum import Enum
from typing import Any

from app.analysis.dependencies import DependencyNode, parse_dependency_node, resolve_dependency_path
from app.errors import Diagnostic


class DependencyType(str, Enum):
    NORMAL = "normal"
    OPTIONAL = "optional"
    PEER = "peer"


@dataclass
class DependencyEdge:
    source: str
    target: str
    dependency_type: DependencyType


@dataclass
class DependencyGraph:
    nodes: dict[str, DependencyNode] = field(default_factory=dict)
    edges: list[DependencyEdge] = field(default_factory=list)
    reverse_edges: dict[str, set[str]] = field(default_factory=dict)
    # Structural problems: a *required* dependency that has no entry in the lockfile, a
    # malformed entry, ... Each item is {"from": ..., "dependency": ..., "reason"?: ...}.
    unresolved: list[dict[str, str]] = field(default_factory=list)
    # pnpm importer path -> dependency name -> resolved graph node path.
    importer_dependencies: dict[str, dict[str, str]] = field(default_factory=dict)
    # pnpm importer path -> dependency name -> importer path it links to (workspace:* deps).
    workspace_links: dict[str, dict[str, str]] = field(default_factory=dict)
    # Non-fatal notes produced while building the graph (unsupported fields, ambiguity, ...).
    diagnostics: list[Diagnostic] = field(default_factory=list)
    _edge_keys: set[tuple[str, str, str]] = field(default_factory=set, repr=False)


def add_edge(graph: DependencyGraph, source: str, target: str, dependency_type: DependencyType) -> None:
    # O(1) duplicate check. The previous linear scan over ``graph.edges`` made graph
    # construction quadratic (6,000 packages took ~19 s; now milliseconds).
    key = (source, target, dependency_type.value)
    if key in graph._edge_keys:
        return
    graph._edge_keys.add(key)
    graph.edges.append(DependencyEdge(source=source, target=target, dependency_type=dependency_type))
    graph.reverse_edges.setdefault(target, set()).add(source)


def _is_installed_package_path(path: str) -> bool:
    # package-lock v2/v3 also lists workspace source paths (e.g. packages/ui).
    # Those source entries are reached through their node_modules link aliases.
    return path.startswith("node_modules/") or "/node_modules/" in path


def _resolution_bases(node: DependencyNode, link_target: str | None) -> list[str]:
    """Where to start Node's upward lookup for a package's dependencies.

    A workspace link such as ``node_modules/@ws/a`` points at ``packages/a``; Node resolves
    that package's imports from its *real* location first (``packages/a/node_modules``),
    then up through the repository root.
    """
    bases = []
    if link_target is not None:
        bases.append(link_target)
    bases.append(node.path)
    return bases


def build_dependency_graph(packages: dict[str, dict[str, Any]]) -> DependencyGraph:
    graph = DependencyGraph()
    package_paths = {path for path in packages if path and _is_installed_package_path(path)}
    link_targets: dict[str, str] = {}

    for path in sorted(package_paths):
        data = packages.get(path)
        if not isinstance(data, dict):
            graph.unresolved.append({"from": path, "dependency": "<invalid package entry>", "reason": "entry is not an object"})
            continue
        effective_data = data
        if data.get("link") is True and isinstance(data.get("resolved"), str):
            target_path = posixpath.normpath(data["resolved"])
            target_data = packages.get(target_path)
            if isinstance(target_data, dict):
                # Keep alias identity/path, but use the linked workspace's version and dependency declarations.
                effective_data = {**target_data, **{
                    "link": True,
                    "resolved": target_data.get("resolved"),
                    "integrity": target_data.get("integrity"),
                }}
                link_targets[path] = target_path
        node = parse_dependency_node(path, effective_data)
        if node.version is None:
            graph.unresolved.append({
                "from": path, "dependency": "<package entry has no resolved version>",
                "reason": "link target not found in lockfile" if data.get("link") is True else "no version in lockfile entry",
            })
            continue
        graph.nodes[path] = node

    available_paths = set(graph.nodes)
    # Nested installs under a workspace's real directory (packages/a/node_modules/x) are
    # valid resolution targets for that workspace, so keep them in the lookup set.
    lookup_paths = available_paths
    for path, node in graph.nodes.items():
        link_target = link_targets.get(path)
        bases = _resolution_bases(node, link_target)
        dependency_groups = (
            (set(node.dependencies) - set(node.optional_dependencies), DependencyType.NORMAL),
            (set(node.optional_dependencies), DependencyType.OPTIONAL),
            (set(node.peer_dependencies), DependencyType.PEER),
        )
        for dependency_names, dependency_type in dependency_groups:
            for dependency_name in sorted(dependency_names):
                dependency_path = None
                for base in bases:
                    dependency_path = resolve_dependency_path(base, dependency_name, lookup_paths)
                    if dependency_path:
                        break
                if dependency_path:
                    if dependency_path != path:
                        add_edge(graph, path, dependency_path, dependency_type)
                elif dependency_type == DependencyType.NORMAL:
                    # Missing optional dependencies are permitted; peer dependencies can be
                    # intentionally omitted (notably optional peers). Do not call those
                    # graph failures without installation context. Bundled dependencies live
                    # inside the parent's tarball and are never listed separately.
                    if dependency_name in node.bundled_dependencies:
                        continue
                    graph.unresolved.append({
                        "from": path,
                        "dependency": dependency_name,
                        "dependency_type": dependency_type.value,
                        "reason": "required dependency has no matching entry in the lockfile",
                    })
    return graph
