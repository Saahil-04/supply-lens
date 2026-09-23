import json

from app.analysis.impact import ImpactResult, analyze_impact
from app.analysis.graph import build_dependency_graph
from app.analysis.projects import NpmProject, build_npm_projects
from app.analysis.relationships import associate_project_dependencies
from app.github.client import GitHubClient
from app.analysis.discovery import discover_dependency_files


def analyze_project_impact(
    lockfile_data: dict,
    manifest_data: dict,
    project_path: str,
    target_path: str,
) -> ImpactResult:
    graph = build_dependency_graph(
        lockfile_data["packages"]
    )

    project = NpmProject(
        root_path=project_path,
        manifest={
            "path": f"{project_path}/package.json",
            "sha": "",
        },
        manifest_data=manifest_data,
        lockfile={
            "path": f"{project_path}/package-lock.json",
            "sha": "",
        },
        package_name=manifest_data.get("name"),
        package_version=manifest_data.get("version"),
        is_workspace_root=False,
        workspace_patterns=[],
        workspace_members=[],
    )

    associate_project_dependencies(
        project,
        graph,
    )

    return analyze_impact(
        graph,
        project,
        target_path,
    )


async def analyze_repository_impact(
    repository_url: str,
    target: str,
) -> ImpactResult:
    client = GitHubClient()

    try:
        repository = await client.get_repository(
            repository_url
        )

        owner = repository["owner"]["login"]
        repository_name = repository["name"]
        branch = repository["default_branch"]

        commit_sha = await client.get_latest_commit_sha(
            owner,
            repository_name,
            branch,
        )

        tree = await client.get_repository_tree(
            owner,
            repository_name,
            commit_sha,
        )

        dependency_files = discover_dependency_files(tree)

        manifest_contents = {}

        for manifest in dependency_files["manifests"]:
            content = await client.get_file_content(
                owner,
                repository_name,
                manifest["sha"],
            )

            manifest_contents[manifest["path"]] = json.loads(
                content
            )

        projects, _ = build_npm_projects(
            dependency_files,
            manifest_contents,
        )

        # One dependency graph per lockfile.
        graphs = {}

        for project in projects:
            if project.lockfile is None:
                continue

            lockfile_path = project.lockfile["path"]

            if lockfile_path in graphs:
                continue

            lockfile_content = await client.get_file_content(
                owner,
                repository_name,
                project.lockfile["sha"],
            )

            lockfile_data = json.loads(
                lockfile_content
            )

            graphs[lockfile_path] = build_dependency_graph(
                lockfile_data["packages"]
            )

        # Temporary verification for Step 1.
        for lockfile_path, graph in graphs.items():
            print(
                lockfile_path,
                len(graph.nodes),
                len(graph.edges),
            )

        raise ValueError(
            "Step 1 complete: graph construction verified"
        )

    finally:
        await client.close()