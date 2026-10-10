"""Small GitHub REST API client; repository analysis lives in the service layer."""
from __future__ import annotations

import base64
import binascii
import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

load_dotenv()

GITHUB_API_URL = os.getenv("GITHUB_API_URL", "https://api.github.com")


class GitHubClient:
    def __init__(self) -> None:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = os.getenv("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.client = httpx.AsyncClient(
            base_url=GITHUB_API_URL.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(20.0, connect=10.0),
        )

    @staticmethod
    def parse_repository_url(url: str) -> tuple[str, str]:
        """Accept only a GitHub repository URL, not arbitrary URLs or subpages."""
        if not isinstance(url, str) or not url.strip():
            raise ValueError("repository_url must be a GitHub repository URL")
        parsed = urlparse(url.strip())
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"github.com", "www.github.com"}:
            raise ValueError("Invalid GitHub repository URL; expected https://github.com/owner/repo")
        if parsed.query or parsed.fragment:
            raise ValueError("Use the repository URL without query parameters or fragments")
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) != 2:
            raise ValueError("Invalid GitHub repository URL; expected https://github.com/owner/repo")
        owner, repository = parts
        if repository.endswith(".git"):
            repository = repository[:-4]
        if not owner or not repository or not re.fullmatch(r"[A-Za-z0-9_.-]+", owner) or not re.fullmatch(r"[A-Za-z0-9_.-]+", repository):
            raise ValueError("Invalid GitHub owner or repository name")
        return owner, repository

    async def get_repository(self, url: str) -> dict[str, Any]:
        owner, repository = self.parse_repository_url(url)
        response = await self.client.get(f"/repos/{owner}/{repository}")
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or not isinstance(data.get("owner"), dict):
            raise ValueError("GitHub returned unexpected repository metadata")
        return data

    async def get_latest_commit_sha(self, owner: str, repository: str, branch: str) -> str:
        response = await self.client.get(f"/repos/{owner}/{repository}/commits/{branch}")
        response.raise_for_status()
        data = response.json()
        sha = data.get("sha") if isinstance(data, dict) else None
        if not isinstance(sha, str) or not sha:
            raise ValueError("GitHub returned no commit SHA for the default branch")
        return sha

    async def get_repository_tree(self, owner: str, repository: str, commit_sha: str) -> list[dict[str, Any]]:
        response = await self.client.get(
            f"/repos/{owner}/{repository}/git/trees/{commit_sha}",
            params={"recursive": "1"},
        )
        response.raise_for_status()
        data = response.json()
        if data.get("truncated"):
            raise ValueError("Repository tree is too large to analyze safely; analyze a smaller repository snapshot")
        tree = data.get("tree")
        if not isinstance(tree, list):
            raise ValueError("GitHub returned an invalid repository tree")
        return tree

    async def get_file_content(self, owner: str, repository: str, blob_sha: str) -> str:
        response = await self.client.get(f"/repos/{owner}/{repository}/git/blobs/{blob_sha}")
        response.raise_for_status()
        data = response.json()
        if data.get("encoding") != "base64" or not isinstance(data.get("content"), str):
            raise ValueError("GitHub returned an unsupported blob encoding")
        # GitHub's blob API may include whitespace/newlines in its Base64 text.
        # Strip whitespace before strict validation so formatting does not make a
        # valid blob fail, while still rejecting genuinely malformed Base64.
        encoded_content = re.sub(r"\s+", "", data["content"])
        try:
            content = base64.b64decode(encoded_content, validate=True)
            return content.decode("utf-8")
        except (binascii.Error, UnicodeDecodeError) as exc:
            raise ValueError("GitHub returned a blob that is not valid UTF-8/base64 text") from exc

    async def close(self) -> None:
        await self.client.aclose()
