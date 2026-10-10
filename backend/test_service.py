import asyncio
from unittest.mock import AsyncMock, patch

from app.analysis.service import analyze_repository_impact


REPOSITORY_URL = "https://github.com/example/repo"


def make_blob(path, sha):
    return {
        "path": path,
        "sha": sha,
        "type": "blob",
    }


def make_lockfile(packages):
    return {
        "name": "test-project",
        "lockfileVersion": 3,
        "packages": packages,
    }


async def run_test(
    manifests,
    lockfiles,
    target,
    expected_projects,
    expected_affected,
):
    client = AsyncMock()

    client.get_repository.return_value = {
        "owner": {"login": "example"},
        "name": "repo",
        "default_branch": "main",
    }

    client.get_latest_commit_sha.return_value = "commit123"

    client.get_repository_tree.return_value = [
        *[
            make_blob(path, f"manifest-{i}")
            for i, path in enumerate(manifests)
        ],
        *[
            make_blob(path, f"lock-{i}")
            for i, path in enumerate(lockfiles)
        ],
    ]

    contents = {}

    for i, (path, data) in enumerate(manifests.items()):
        contents[f"manifest-{i}"] = __import__("json").dumps(data)

    for i, (path, data) in enumerate(lockfiles.items()):
        contents[f"lock-{i}"] = __import__("json").dumps(data)

    async def get_file_content(owner, repository, sha):
        return contents[sha]

    client.get_file_content.side_effect = get_file_content

    with patch(
        "app.analysis.service.GitHubClient",
        return_value=client,
    ):
        result = await analyze_repository_impact(
            REPOSITORY_URL,
            target,
        )

    assert result.projects_analyzed == expected_projects
    assert len(result.affected_projects) == expected_affected

    await client.close()

    return result


def test_single_project():
    manifests = {
        "backend/package.json": {
            "name": "backend",
            "version": "1.0.0",
            "dependencies": {"rxjs": "^7.8.1"},
        }
    }

    lockfiles = {
        "backend/package-lock.json": make_lockfile({
            "": {
                "name": "backend",
                "version": "1.0.0",
                "dependencies": {"rxjs": "^7.8.1"},
            },
            "node_modules/rxjs": {
                "version": "7.8.1",
            },
        })
    }

    result = asyncio.run(
        run_test(
            manifests,
            lockfiles,
            "rxjs",
            expected_projects=1,
            expected_affected=1,
        )
    )

    assert result.target_name == "rxjs"
    assert result.target_version == "7.8.1"

    print("Single-project service test: PASS")


def test_multiple_independent_projects():
    manifests = {
        "backend/package.json": {
            "name": "backend",
            "dependencies": {"rxjs": "^7.8.1"},
        },
        "frontend/package.json": {
            "name": "frontend",
            "dependencies": {"rxjs": "^7.8.1"},
        },
    }

    lockfiles = {
        "backend/package-lock.json": make_lockfile({
            "": {"name": "backend"},
            "node_modules/rxjs": {"version": "7.8.1"},
        }),
        "frontend/package-lock.json": make_lockfile({
            "": {"name": "frontend"},
            "node_modules/rxjs": {"version": "7.8.1"},
        }),
    }

    result = asyncio.run(
        run_test(
            manifests,
            lockfiles,
            "rxjs",
            expected_projects=2,
            expected_affected=2,
        )
    )

    assert {
        impact.project_path
        for impact in result.affected_projects
    } == {"backend", "frontend"}

    print("Multiple-project service test: PASS")


def test_workspace_projects():
    manifests = {
        "package.json": {
            "name": "workspace",
            "private": True,
            "workspaces": ["packages/*"],
        },
        "packages/api/package.json": {
            "name": "api",
            "dependencies": {"rxjs": "^7.8.1"},
        },
        "packages/web/package.json": {
            "name": "web",
            "dependencies": {"rxjs": "^7.8.1"},
        },
    }

    lockfiles = {
        "package-lock.json": make_lockfile({
            "": {"name": "workspace"},
            "node_modules/rxjs": {"version": "7.8.1"},
        })
    }

    result = asyncio.run(
        run_test(
            manifests,
            lockfiles,
            "rxjs",
            expected_projects=3,
            expected_affected=2,
        )
    )

    assert {
        impact.project_path
        for impact in result.affected_projects
    } == {"packages/api", "packages/web"}

    print("Workspace service test: PASS")


if __name__ == "__main__":
    test_single_project()
    test_multiple_independent_projects()
    test_workspace_projects()

    print("\nAll service tests passed.")