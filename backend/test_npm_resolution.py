import asyncio
import json
from pathlib import Path

from app.github.client import GitHubClient
from app.analysis.discovery import discover_dependency_files


REPOSITORY_URL = "https://github.com/Saahil-04/Saransh-AI"

TEMP_DIR = Path("temp-npm-test")


async def main():
    client = GitHubClient()

    try:
        owner, repository = client.parse_repository_url(REPOSITORY_URL)

        repo_data = await client.get_repository(REPOSITORY_URL)

        branch = repo_data["default_branch"]

        commit_sha = await client.get_latest_commit_sha(
            owner,
            repository,
            branch,
        )

        tree = await client.get_repository_tree(
            owner,
            repository,
            commit_sha,
        )

        dependency_files = discover_dependency_files(tree)

        TEMP_DIR.mkdir(exist_ok=True)

        for file in dependency_files["manifests"]:
            if file["path"] == "package.json":
                content = await client.get_file_content(
                    owner,
                    repository,
                    file["sha"],
                )

                (TEMP_DIR / "package.json").write_text(
                    content,
                    encoding="utf-8",
                )

        for file in dependency_files["lockfiles"]:
            if file["path"] == "package-lock.json":
                content = await client.get_file_content(
                    owner,
                    repository,
                    file["sha"],
                )

                (TEMP_DIR / "package-lock.json").write_text(
                    content,
                    encoding="utf-8",
                )

        print("Created temporary npm project:")
        print(TEMP_DIR.resolve())

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())