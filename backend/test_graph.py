import json
from pathlib import Path

from app.analysis.graph import build_dependency_graph
from app.analysis.projects import NpmProject
from app.analysis.relationships import associate_project_dependencies
from app.analysis.impact import (
    find_affected_packages,
    find_dependency_paths,
    analyze_impact,
)
from app.analysis.direct import get_direct_dependencies


LOCKFILE = Path(
    "temp-npm-test/saransh-backend-package-lock.json"
)

MANIFEST = Path(
    "temp-npm-test/saransh-backend-package.json"
)

TARGET = "node_modules/rxjs"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def build_test_project(
    manifest_data: dict,
) -> NpmProject:
    return NpmProject(
        root_path="backend",
        manifest={
            "path": "backend/package.json",
            "sha": "test",
        },
        manifest_data=manifest_data,
        lockfile={
            "path": "backend/package-lock.json",
            "sha": "test",
        },
        package_name=manifest_data.get("name"),
        package_version=manifest_data.get("version"),
        is_workspace_root=False,
        workspace_patterns=[],
        workspace_members=[],
    )


def validate_optional_edges(graph) -> None:
    expected_optional_pairs = {
        (
            "node_modules/chokidar",
            "node_modules/fsevents",
        ),
        (
            "node_modules/cli-table3",
            "node_modules/@colors/colors",
        ),
        (
            "node_modules/jackspeak",
            "node_modules/@pkgjs/parseargs",
        ),
        (
            "node_modules/jest-haste-map",
            "node_modules/fsevents",
        ),
        (
            "node_modules/jsonfile",
            "node_modules/graceful-fs",
        ),
    }

    optional_edges = [
        edge
        for edge in graph.edges
        if edge.dependency_type.value == "optional"
    ]

    actual_optional_pairs = {
        (edge.source, edge.target)
        for edge in optional_edges
    }

    assert len(optional_edges) == 5
    assert actual_optional_pairs == expected_optional_pairs

    print("Optional edges: PASS")


def validate_peer_edges(graph) -> None:
    peer_edges = [
        edge
        for edge in graph.edges
        if edge.dependency_type.value == "peer"
    ]

    missing_targets = [
        edge
        for edge in peer_edges
        if edge.target not in graph.nodes
    ]

    assert len(missing_targets) == 0

    print(
        f"Peer edges: PASS ({len(peer_edges)})"
    )


def validate_project_dependencies(
    project: NpmProject,
    graph,
) -> None:
    unresolved = associate_project_dependencies(
        project,
        graph,
    )

    assert unresolved == []

    direct_dependencies = get_direct_dependencies(
        project.manifest_data
    )

    assert len(project.dependencies) == len(
        direct_dependencies
    )

    print(
        "Direct dependencies: PASS "
        f"({len(project.dependencies)})"
    )


def validate_impact(
    graph,
    project: NpmProject,
) -> None:
    assert TARGET in graph.nodes

    affected = find_affected_packages(
        graph,
        TARGET,
    )

    assert TARGET in affected

    dependency_paths = find_dependency_paths(
        graph,
        TARGET,
    )

    assert TARGET in dependency_paths

    result = analyze_impact(
        graph,
        project,
        TARGET,
    )

    assert result.target_name == "rxjs"
    assert result.target_version == "7.8.1"

    print("Impact analysis: PASS")
    print(
        f"  Target: rxjs@7.8.1"
    )
    print(
        f"  Affected packages: {len(affected)}"
    )
    print(
        f"  Project impacts: {len(result.affected_projects)}"
    )


def main() -> None:
    lockfile = load_json(LOCKFILE)
    manifest_data = load_json(MANIFEST)

    print("Building dependency graph...")

    graph = build_dependency_graph(
        lockfile["packages"]
    )

    print(
        f"Graph: {len(graph.nodes)} nodes, "
        f"{len(graph.edges)} edges"
    )

    print(
        f"Unresolved graph dependencies: "
        f"{len(graph.unresolved)}"
    )

    assert graph.unresolved == []

    print()

    validate_optional_edges(graph)
    validate_peer_edges(graph)

    print()

    project = build_test_project(
        manifest_data
    )

    validate_project_dependencies(
        project,
        graph,
    )

    print()

    print(
        f"Project: {project.root_path}"
    )
    print(
        f"Development dependencies: "
        f"{sum(1 for dependency in project.dependencies if dependency.dependency_type == 'development')}"
    )
    print(
        f"Development dependencies: "
        f"{sum(1 for dependency in project.dependencies if dependency.dependency_type == 'development')}"
    )

    print()

    validate_impact(
        graph,
        project,
    )

    print()
    print("All graph tests passed.")


if __name__ == "__main__":
    main()