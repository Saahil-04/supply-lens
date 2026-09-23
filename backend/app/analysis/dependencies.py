from dataclasses import dataclass, field
from typing import Any


@dataclass
class DependencyNode:
    name: str
    version: str
    path: str
    resolved: str | None = None
    integrity: str | None = None

    dependencies: dict[str, str] = field(default_factory=dict)
    optional_dependencies: dict[str, str] = field(
        default_factory=dict
    )
    peer_dependencies: dict[str, str] = field(default_factory=dict)
    peer_dependencies_meta: dict[str, dict] = field(
        default_factory=dict
    )
    

def parse_dependency_node(
    path: str,
    data: dict[str, Any],
) -> DependencyNode:
    name = path.rsplit("node_modules/", maxsplit=1)[-1]

    return DependencyNode(
        name=name,
        version=data["version"],
        path=path,
        resolved=data.get("resolved"),
        integrity=data.get("integrity"),
        optional_dependencies=data.get(
        "optionalDependencies",
        {},
        ),    
        dependencies=data.get("dependencies", {}),
        peer_dependencies=data.get(
            "peerDependencies",
            {},
        ),
        peer_dependencies_meta=data.get(
            "peerDependenciesMeta",
            {},
        ),
    )
    
def resolve_dependency_path(
    package_path: str,
    dependency_name: str,
    package_paths: set[str],
) -> str | None:
    current_path = package_path

    while True:
        candidate = (
            f"{current_path}/node_modules/{dependency_name}"
            if current_path
            else f"node_modules/{dependency_name}"
        )

        if candidate in package_paths:
            return candidate

        if not current_path:
            break

        if "/node_modules/" in current_path:
            current_path = current_path.rsplit(
                "/node_modules/",
                maxsplit=1,
            )[0]
        else:
            current_path = ""

    return None        