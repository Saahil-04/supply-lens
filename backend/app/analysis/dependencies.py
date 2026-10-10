from dataclasses import dataclass, field
from typing import Any


@dataclass
class DependencyNode:
    name: str
    version: str | None
    path: str
    resolved: str | None = None
    integrity: str | None = None
    dependencies: dict[str, str] = field(default_factory=dict)
    optional_dependencies: dict[str, str] = field(default_factory=dict)
    peer_dependencies: dict[str, str] = field(default_factory=dict)
    peer_dependencies_meta: dict[str, dict[str, Any]] = field(default_factory=dict)
    dev: bool | None = None
    optional: bool | None = None
    dev_optional: bool | None = None
    is_link: bool = False


def parse_dependency_node(path: str, data: dict[str, Any]) -> DependencyNode:
    """Parse one npm lockfile package entry without guessing missing versions."""
    name = data.get("name")
    if not isinstance(name, str) or not name:
        name = path.rsplit("node_modules/", maxsplit=1)[-1]
    version = data.get("version")
    if version is not None and not isinstance(version, str):
        version = str(version)
    return DependencyNode(
        name=name,
        version=version,
        path=path,
        resolved=data.get("resolved") if isinstance(data.get("resolved"), str) else None,
        integrity=data.get("integrity") if isinstance(data.get("integrity"), str) else None,
        dependencies=data.get("dependencies", {}) if isinstance(data.get("dependencies", {}), dict) else {},
        optional_dependencies=data.get("optionalDependencies", {}) if isinstance(data.get("optionalDependencies", {}), dict) else {},
        peer_dependencies=data.get("peerDependencies", {}) if isinstance(data.get("peerDependencies", {}), dict) else {},
        peer_dependencies_meta=data.get("peerDependenciesMeta", {}) if isinstance(data.get("peerDependenciesMeta", {}), dict) else {},
        dev=data.get("dev") if isinstance(data.get("dev"), bool) else None,
        optional=data.get("optional") if isinstance(data.get("optional"), bool) else None,
        dev_optional=data.get("devOptional") if isinstance(data.get("devOptional"), bool) else None,
        is_link=data.get("link") is True,
    )


def resolve_dependency_path(package_path: str, dependency_name: str, package_paths: set[str]) -> str | None:
    """Resolve an npm dependency using Node's upward node_modules lookup pattern."""
    current_path = package_path
    while True:
        candidate = f"{current_path}/node_modules/{dependency_name}" if current_path else f"node_modules/{dependency_name}"
        if candidate in package_paths:
            return candidate
        if not current_path:
            break
        if "/node_modules/" in current_path:
            current_path = current_path.rsplit("/node_modules/", maxsplit=1)[0]
        else:
            current_path = ""
    return None
