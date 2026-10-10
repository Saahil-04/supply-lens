from app.analysis.service import map_projects_to_graphs
from app.analysis.projects import NpmProject


def make_project(
    root_path,
    lockfile_path=None,
    workspace_members=None,
):
    return NpmProject(
        root_path=root_path,
        manifest={
            "path": f"{root_path}/package.json",
            "sha": "",
        },
        manifest_data={},
        lockfile=(
            {
                "path": lockfile_path,
                "sha": "",
            }
            if lockfile_path
            else None
        ),
        package_name=None,
        package_version=None,
        is_workspace_root=bool(workspace_members),
        workspace_patterns=[],
        workspace_members=workspace_members or [],
    )


def main():
    graph_a = object()
    graph_b = object()

    projects = [
        make_project(
            "backend",
            "backend/package-lock.json",
        ),
        make_project(
            "frontend",
            "frontend/package-lock.json",
        ),
        make_project(
            "",
            "package-lock.json",
            [
                "packages/api/package.json",
                "packages/web/package.json",
            ],
        ),
        make_project("packages/api"),
        make_project("packages/web"),
    ]

    graphs = {
        "backend/package-lock.json": graph_a,
        "frontend/package-lock.json": graph_b,
        "package-lock.json": object(),
    }

    mapping = map_projects_to_graphs(projects, graphs)

    assert mapping["backend"] is graph_a
    assert mapping["frontend"] is graph_b

    assert mapping["packages/api"] is graphs["package-lock.json"]
    assert mapping["packages/web"] is graphs["package-lock.json"]

    print("Project → graph mapping tests passed.")


if __name__ == "__main__":
    main()