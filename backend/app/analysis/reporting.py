from collections import defaultdict

from app.analysis.graph import DependencyGraph
from app.analysis.impact import ProjectImpact


def format_project_impact(
    impacts: list[ProjectImpact],
    graph: DependencyGraph,
) -> str:
    if not impacts:
        return "No impact found."

    grouped: dict[str, dict[str, list[ProjectImpact]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for impact in impacts:
        grouped[impact.project_path][impact.dependency_type].append(
            impact
        )

    lines = ["Impact Analysis"]

    for project_path, dependency_groups in grouped.items():
        lines.append("")
        lines.append(f"Project: {project_path}")

        for dependency_type in ("production", "development"):
            group = dependency_groups.get(dependency_type)

            if not group:
                continue

            lines.append("")
            lines.append(f"{dependency_type.capitalize()}:")

            for impact in group:
                display_path = list(reversed(impact.path))

                for index, node_path in enumerate(display_path):
                    node = graph.nodes[node_path]
                    name = f"{node.name}@{node.version}"

                    prefix = "    " * index

                    if index == 0:
                        lines.append(f"├── {name}")
                    else:
                        lines.append(f"{prefix}└── {name}")

    return "\n".join(lines)