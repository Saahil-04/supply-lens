import json

from app.analysis.impact import (
    ImpactResult,
    ProjectImpact,
    RepositoryImpactResult,
    analyze_impact,
)
from app.analysis.graph import build_dependency_graph,DependencyGraph
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
) -> RepositoryImpactResult:
    client = GitHubClient()

    try:
        repository = await client.get_repository(repository_url)

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

        # 1. Load all manifests.
        manifest_contents = {}

        for manifest in dependency_files["manifests"]:
            content = await client.get_file_content(
                owner,
                repository_name,
                manifest["sha"],
            )

            manifest_contents[manifest["path"]] = json.loads(content)

        # 2. Discover projects and associate their lockfiles.
        projects, _ = build_npm_projects(
            dependency_files,
            manifest_contents,
        )

        # 3. Build one graph per unique lockfile.
        graphs: dict[str, DependencyGraph] = {}

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

            lockfile_data = json.loads(lockfile_content)

            graphs[lockfile_path] = build_dependency_graph(
                lockfile_data["packages"]
            )

        # 4. Map projects to their graphs.
        project_graphs = map_projects_to_graphs(
            projects,
            graphs,
        )

        # 5. Analyze the target in every project.
        all_impacts: list[ProjectImpact] = []
        target_name = ""
        target_version = ""
        projects_analyzed = 0

        for project in projects:
            graph = project_graphs.get(project.root_path)

            if graph is None:
                continue

            projects_analyzed += 1

            # Resolve this project's direct dependencies.
            project.dependencies.clear()

            associate_project_dependencies(
                project,
                graph,
            )

            # Resolve the target path against this graph.
            target_path = target

            if target_path not in graph.nodes:
                matching_paths = [
                    path
                    for path, node in graph.nodes.items()
                    if node.name == target
                ]

                if not matching_paths:
                    continue

                target_path = matching_paths[0]

            result: ImpactResult = analyze_impact(
                graph,
                project,
                target_path,
            )

            if result.target_name:
                target_name = result.target_name
                target_version = result.target_version

            all_impacts.extend(result.affected_projects)

        # 6. Return a repository-level result.
        return RepositoryImpactResult(
            target_name=target_name,
            target_version=target_version,
            affected_projects=all_impacts,
            projects_analyzed=projects_analyzed,
        )

    finally:
        await client.close()
        
def map_projects_to_graphs(
    projects: list[NpmProject],
    graphs: dict[str, DependencyGraph],
) -> dict[str, DependencyGraph]:
    project_graphs: dict[str, DependencyGraph] = {}

    # Projects with their own lockfile.
    for project in projects:
        if project.lockfile is None:
            continue

        lockfile_path = project.lockfile["path"]
        graph = graphs.get(lockfile_path)

        if graph is not None:
            project_graphs[project.root_path] = graph

    # Workspace members share their workspace root's graph.
    for root_project in projects:
        if not root_project.is_workspace_root:
            continue

        if root_project.lockfile is None:
            continue

        graph = graphs.get(root_project.lockfile["path"])

        if graph is None:
            continue

        for member_manifest_path in root_project.workspace_members:
            member_root = member_manifest_path.rsplit(
                "/",
                maxsplit=1,
            )[0]

            project_graphs[member_root] = graph

    return project_graphs