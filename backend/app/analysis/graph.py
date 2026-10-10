from dataclasses import dataclass, field
import posixpath
from enum import Enum
from typing import Any

from app.analysis.dependencies import DependencyNode, parse_dependency_node, resolve_dependency_path


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
    unresolved: list[dict[str, str]] = field(default_factory=list)


def add_edge(graph: DependencyGraph, source: str, target: str, dependency_type: DependencyType) -> None:
    if any(e.source == source and e.target == target and e.dependency_type == dependency_type for e in graph.edges):
        return
    graph.edges.append(DependencyEdge(source=source, target=target, dependency_type=dependency_type))
    graph.reverse_edges.setdefault(target, set()).add(source)


def _is_installed_package_path(path: str) -> bool:
    # package-lock v2/v3 also lists workspace source paths (e.g. packages/ui).
    # Those source entries are reached through their node_modules link aliases.
    return path.startswith("node_modules/") or "/node_modules/" in path


def build_dependency_graph(packages: dict[str, dict[str, Any]]) -> DependencyGraph:
    graph = DependencyGraph()
    package_paths = {path for path in packages if path and _is_installed_package_path(path)}

    for path in sorted(package_paths):
        data = packages.get(path)
        if not isinstance(data, dict):
            graph.unresolved.append({"from": path, "dependency": "<invalid package entry>"})
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
        node = parse_dependency_node(path, effective_data)
        if node.version is None:
            graph.unresolved.append({"from": path, "dependency": "<package entry has no resolved version>"})
            continue
        graph.nodes[path] = node

    available_paths = set(graph.nodes)
    for path, node in graph.nodes.items():
        dependency_groups = (
            (set(node.dependencies) - set(node.optional_dependencies), DependencyType.NORMAL),
            (set(node.optional_dependencies), DependencyType.OPTIONAL),
            (set(node.peer_dependencies), DependencyType.PEER),
        )
        for dependency_names, dependency_type in dependency_groups:
            for dependency_name in sorted(dependency_names):
                dependency_path = resolve_dependency_path(path, dependency_name, available_paths)
                if dependency_path:
                    add_edge(graph, path, dependency_path, dependency_type)
                elif dependency_type == DependencyType.NORMAL:
                    # Missing optional dependencies are permitted; peer dependencies can be
                    # intentionally omitted (notably optional peers). Do not call those
                    # graph failures without installation context.
                    graph.unresolved.append({
                        "from": path,
                        "dependency": dependency_name,
                        "dependency_type": dependency_type.value,
                    })
    return graph
