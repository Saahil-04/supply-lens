from app.analysis.direct import get_direct_dependencies
from app.analysis.dependencies import resolve_dependency_path
from app.analysis.graph import DependencyGraph
from app.analysis.projects import (
    NpmProject,
    ProjectDependency,
)


def associate_project_dependencies(
    project: NpmProject,
    graph: DependencyGraph,
) -> list[str]:
    direct_dependencies = get_direct_dependencies(
        project.manifest_data
    )

    package_paths = set(graph.nodes.keys())
    unresolved: list[str] = []

    for dependency_name, dependency_type in direct_dependencies.items():
        dependency_path = resolve_dependency_path(
            "",
            dependency_name,
            package_paths,
        )

        if dependency_path is None:
            unresolved.append(dependency_name)
            continue

        project.dependencies.append(
            ProjectDependency(
                dependency_path=dependency_path,
                dependency_type=dependency_type,
            )
        )

    return unresolved