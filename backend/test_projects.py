from app.analysis.projects import (
    build_npm_projects,
)


def manifest(path: str, name: str) -> dict[str, str]:
    return {
        "path": path,
        "sha": f"{name}-sha",
    }
    

def lockfile(path: str, name: str) -> dict[str, str]:
    return {
        "path": path,
        "sha": f"{name}-lock-sha",
    }    
    
def test_single_project():
    dependency_files = {
        "manifests": [
            manifest(
                "backend/package.json",
                "backend",
            ),
        ],
        "lockfiles": [
            lockfile(
                "backend/package-lock.json",
                "backend",
            ),
        ],
    }

    manifest_contents = {
        "backend/package.json": {
            "name": "backend",
            "version": "1.0.0",
        },
    }

    projects, orphaned = build_npm_projects(
        dependency_files,
        manifest_contents,
    )

    assert len(projects) == 1
    assert orphaned == []

    project = projects[0]

    assert project.root_path == "backend"
    assert project.lockfile is not None
    assert (
        project.lockfile["path"]
        == "backend/package-lock.json"
    )

def test_multiple_independent_projects():
    dependency_files = {
        "manifests": [
            manifest(
                "backend/package.json",
                "backend",
            ),
            manifest(
                "frontend/package.json",
                "frontend",
            ),
        ],
        "lockfiles": [
            lockfile(
                "backend/package-lock.json",
                "backend",
            ),
            lockfile(
                "frontend/package-lock.json",
                "frontend",
            ),
        ],
    }

    manifest_contents = {
        "backend/package.json": {
            "name": "backend",
        },
        "frontend/package.json": {
            "name": "frontend",
        },
    }

    projects, orphaned = build_npm_projects(
        dependency_files,
        manifest_contents,
    )

    assert len(projects) == 2
    assert orphaned == []

    projects_by_path = {
        project.root_path: project
        for project in projects
    }

    assert (
        projects_by_path["backend"].lockfile["path"]
        == "backend/package-lock.json"
    )

    assert (
        projects_by_path["frontend"].lockfile["path"]
        == "frontend/package-lock.json"
    )


def test_workspace_projects_share_lockfile():
    dependency_files = {
        "manifests": [
            manifest(
                "package.json",
                "root",
            ),
            manifest(
                "packages/api/package.json",
                "api",
            ),
            manifest(
                "packages/web/package.json",
                "web",
            ),
        ],
        "lockfiles": [
            lockfile(
                "package-lock.json",
                "root",
            ),
        ],
    }

    manifest_contents = {
        "package.json": {
            "name": "root",
            "workspaces": [
                "packages/*",
            ],
        },
        "packages/api/package.json": {
            "name": "api",
        },
        "packages/web/package.json": {
            "name": "web",
        },
    }

    projects, orphaned = build_npm_projects(
        dependency_files,
        manifest_contents,
    )

    assert len(projects) == 3
    assert orphaned == []

    root_project = next(
        project
        for project in projects
        if project.root_path == ""
    )

    assert root_project.is_workspace_root is True
    assert root_project.workspace_patterns == [
        "packages/*",
    ]

    assert root_project.workspace_members == [
        "packages/api/package.json",
        "packages/web/package.json",
    ]

    assert (
        root_project.lockfile["path"]
        == "package-lock.json"
    )

    api_project = next(
        project
        for project in projects
        if project.root_path == "packages/api"
    )

    web_project = next(
        project
        for project in projects
        if project.root_path == "packages/web"
    )

    assert api_project.lockfile is None
    assert web_project.lockfile is None


def test_orphaned_lockfile():
    dependency_files = {
        "manifests": [
            manifest(
                "backend/package.json",
                "backend",
            ),
        ],
        "lockfiles": [
            lockfile(
                "backend/package-lock.json",
                "backend",
            ),
            lockfile(
                "orphan/package-lock.json",
                "orphan",
            ),
        ],
    }

    manifest_contents = {
        "backend/package.json": {
            "name": "backend",
        },
    }

    projects, orphaned = build_npm_projects(
        dependency_files,
        manifest_contents,
    )

    assert len(projects) == 1
    assert projects[0].root_path == "backend"

    assert len(orphaned) == 1
    assert (
        orphaned[0].path
        == "orphan/package-lock.json"
    )
    assert (
        orphaned[0].reason
        == "No package.json found in the same directory"
    )


def test_workspace_members_are_resolved():
    dependency_files = {
        "manifests": [
            manifest(
                "package.json",
                "root",
            ),
            manifest(
                "packages/api/package.json",
                "api",
            ),
            manifest(
                "packages/web/package.json",
                "web",
            ),
            manifest(
                "tools/test/package.json",
                "test",
            ),
        ],
        "lockfiles": [
            lockfile(
                "package-lock.json",
                "root",
            ),
        ],
    }

    manifest_contents = {
        "package.json": {
            "name": "root",
            "workspaces": [
                "packages/*",
            ],
        },
        "packages/api/package.json": {
            "name": "api",
        },
        "packages/web/package.json": {
            "name": "web",
        },
        "tools/test/package.json": {
            "name": "test",
        },
    }

    projects, orphaned = build_npm_projects(
        dependency_files,
        manifest_contents,
    )

    assert orphaned == []

    root_project = next(
        project
        for project in projects
        if project.root_path == ""
    )

    assert root_project.workspace_members == [
        "packages/api/package.json",
        "packages/web/package.json",
    ]


if __name__ == "__main__":
    test_single_project()
    test_multiple_independent_projects()
    test_workspace_projects_share_lockfile()
    test_orphaned_lockfile()
    test_workspace_members_are_resolved()

    print("All project tests passed.")    