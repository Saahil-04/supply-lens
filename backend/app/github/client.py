"""Small GitHub REST API client; repository analysis lives in the service layer.

Every upstream failure is converted into an :class:`~app.errors.AnalysisError` with a stable
``code`` so the frontend can tell "repo not found" from "rate limited" from "GitHub is down".
"""
from __future__ import annotations

import asyncio
import base64
import binascii
import os
import random
import re
import time
from collections import OrderedDict
from typing import Any
from urllib.parse import quote, urlparse

import httpx
from dotenv import load_dotenv

from app.errors import AnalysisError, Diagnostic

load_dotenv()

GITHUB_API_URL = os.getenv("GITHUB_API_URL", "https://api.github.com")
MAX_ATTEMPTS = 3
MAX_RATE_LIMIT_WAIT = 20.0         # never block a request longer than this waiting for a reset
MAX_BLOB_BYTES = 50 * 1024 * 1024
MAX_TREE_REQUESTS = 400            # budget for the truncated-tree fallback walk
TREE_CONCURRENCY = 8
# Directories that never hold project manifests worth analysing; skipped by the fallback walk.
SKIPPED_DIRECTORIES = frozenset({"node_modules", ".git", "dist", "build", ".next", ".nuxt", "out", "coverage", ".cache", ".turbo", ".yarn", ".pnpm-store", "vendor", "target"})


class _BlobCache:
    """Git blobs are content-addressed (immutable per SHA), so caching them is always safe."""

    def __init__(self, max_chars: int = 64 * 1024 * 1024) -> None:
        self.max_chars = max_chars
        self._size = 0
        self._items: OrderedDict[tuple[str, str], str] = OrderedDict()

    def get(self, key: tuple[str, str]) -> str | None:
        value = self._items.get(key)
        if value is not None:
            self._items.move_to_end(key)
        return value

    def put(self, key: tuple[str, str], value: str) -> None:
        if len(value) > self.max_chars // 4 or key in self._items:
            return
        self._items[key] = value
        self._size += len(value)
        while self._size > self.max_chars and self._items:
            _, evicted = self._items.popitem(last=False)
            self._size -= len(evicted)


_BLOB_CACHE = _BlobCache()


class GitHubClient:
    backoff_base = 0.6

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self.authenticated = False
        token = os.getenv("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
            self.authenticated = True
        self.client = httpx.AsyncClient(
            base_url=GITHUB_API_URL.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(20.0, connect=10.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            transport=transport,
        )
        # Notes produced while fetching (e.g. the tree had to be walked directory by directory).
        self.diagnostics: list[Diagnostic] = []

    @staticmethod
    def parse_repository_url(url: str) -> tuple[str, str]:
        """Accept only a GitHub repository URL, not arbitrary URLs or subpages."""
        hint = "Use a URL like https://github.com/owner/repo"
        if not isinstance(url, str) or not url.strip():
            raise AnalysisError("INVALID_REPOSITORY_URL", "repository_url must be a GitHub repository URL", hint=hint)
        parsed = urlparse(url.strip())
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"github.com", "www.github.com"}:
            raise AnalysisError("INVALID_REPOSITORY_URL", "Invalid GitHub repository URL; expected https://github.com/owner/repo", hint=hint)
        if parsed.query or parsed.fragment:
            raise AnalysisError("INVALID_REPOSITORY_URL", "Use the repository URL without query parameters or fragments", hint=hint)
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) != 2:
            raise AnalysisError(
                "INVALID_REPOSITORY_URL", "Invalid GitHub repository URL; expected https://github.com/owner/repo",
                hint="Paste the repository's main page URL, not a branch, file, or issue link.",
            )
        owner, repository = parts
        if repository.endswith(".git"):
            repository = repository[:-4]
        if not owner or not repository or not re.fullmatch(r"[A-Za-z0-9_.-]+", owner) or not re.fullmatch(r"[A-Za-z0-9_.-]+", repository):
            raise AnalysisError("INVALID_REPOSITORY_URL", "Invalid GitHub owner or repository name", hint=hint)
        return owner, repository

    # ------------------------------------------------------------------ transport
    def _error_for(self, response: httpx.Response, what: str) -> AnalysisError:
        status = response.status_code
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset = response.headers.get("X-RateLimit-Reset")
        retry_after = response.headers.get("Retry-After")
        body = response.text[:300].lower() if status in (403, 429) else ""
        if status == 401:
            return AnalysisError(
                "GITHUB_AUTH_FAILED", "GitHub rejected the server's access token.", status_code=502,
                hint="The server operator must replace the GITHUB_TOKEN configured for this service.",
            )
        if status == 429 or (status == 403 and (remaining == "0" or retry_after or "rate limit" in body or "abuse" in body)):
            details: dict[str, Any] = {"authenticated": self.authenticated}
            if reset and reset.isdigit():
                details["reset_epoch"] = int(reset)
                details["retry_in_seconds"] = max(0, int(reset) - int(time.time()))
            elif retry_after and retry_after.isdigit():
                details["retry_in_seconds"] = int(retry_after)
            return AnalysisError(
                "GITHUB_RATE_LIMITED", "GitHub's API rate limit was reached.", status_code=429, retryable=True, details=details,
                hint=("Try again after the limit resets." if self.authenticated
                      else "The server has no GITHUB_TOKEN configured, which limits it to 60 requests/hour; set one to raise this to 5,000."),
            )
        if status == 403:
            return AnalysisError(
                "GITHUB_FORBIDDEN", f"GitHub denied access while reading {what}.", status_code=403,
                hint="The repository may be private, blocked, or require SAML SSO authorization for the server's token.",
            )
        if status == 404 and what == "repository":
            return AnalysisError(
                "REPOSITORY_NOT_FOUND", "Repository not found.", status_code=404,
                hint="Check the owner/name spelling. Private repositories can only be analyzed if the server's token can read them.",
            )
        if status == 404:
            return AnalysisError("GITHUB_RESOURCE_NOT_FOUND", f"GitHub could not find the {what}.", status_code=404,
                                 hint="The repository may have changed while the analysis was running; retry.", retryable=True)
        if status == 409:
            return AnalysisError("REPOSITORY_EMPTY", "The repository is empty (no commits).", status_code=422)
        if status == 451:
            return AnalysisError("REPOSITORY_UNAVAILABLE", "GitHub has made this repository unavailable for legal reasons.", status_code=422)
        if status >= 500:
            return AnalysisError("GITHUB_UNAVAILABLE", "GitHub is temporarily unavailable.", status_code=502, retryable=True, hint="Retry in a minute.")
        return AnalysisError("GITHUB_REQUEST_FAILED", f"GitHub returned HTTP {status} while reading {what}.", status_code=502)

    async def _get(self, path: str, what: str, **kwargs: Any) -> httpx.Response:
        """GET with retries for transient failures; raises AnalysisError otherwise."""
        error: AnalysisError | None = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                response = await self.client.get(path, **kwargs)
            except httpx.TimeoutException:
                error = AnalysisError("GITHUB_TIMEOUT", "Timed out while contacting GitHub.", status_code=504, retryable=True, hint="Retry the analysis.")
            except httpx.TransportError:
                error = AnalysisError("GITHUB_UNREACHABLE", "Could not connect to GitHub.", status_code=502, retryable=True, hint="Retry the analysis.")
            else:
                if response.status_code < 400:
                    return response
                error = self._error_for(response, what)
                if error.code == "GITHUB_RATE_LIMITED":
                    wait = error.details.get("retry_in_seconds")
                    if wait is None or wait > MAX_RATE_LIMIT_WAIT or attempt == MAX_ATTEMPTS - 1:
                        raise error
                    await asyncio.sleep(wait + 1)
                    continue
                if not (error.retryable and response.status_code >= 500):
                    raise error
            if attempt < MAX_ATTEMPTS - 1:
                await asyncio.sleep(self.backoff_base * (2 ** attempt) + random.uniform(0, self.backoff_base / 2))
        assert error is not None
        raise error

    # ------------------------------------------------------------------ API
    async def get_repository(self, url: str) -> dict[str, Any]:
        owner, repository = self.parse_repository_url(url)
        response = await self._get(f"/repos/{owner}/{repository}", "repository")
        data = response.json()
        if not isinstance(data, dict) or not isinstance(data.get("owner"), dict):
            raise AnalysisError("GITHUB_BAD_RESPONSE", "GitHub returned unexpected repository metadata", status_code=502, retryable=True)
        return data

    async def get_latest_commit_sha(self, owner: str, repository: str, branch: str) -> str:
        response = await self._get(f"/repos/{owner}/{repository}/commits/{quote(branch, safe='/')}", "default-branch commit")
        data = response.json()
        sha = data.get("sha") if isinstance(data, dict) else None
        if not isinstance(sha, str) or not sha:
            raise AnalysisError("GITHUB_BAD_RESPONSE", "GitHub returned no commit SHA for the default branch", status_code=502, retryable=True)
        return sha

    async def get_repository_tree(self, owner: str, repository: str, commit_sha: str) -> list[dict[str, Any]]:
        response = await self._get(f"/repos/{owner}/{repository}/git/trees/{commit_sha}", "repository tree", params={"recursive": "1"})
        data = response.json()
        if not isinstance(data, dict) or not isinstance(data.get("tree"), list):
            raise AnalysisError("GITHUB_BAD_RESPONSE", "GitHub returned an invalid repository tree", status_code=502, retryable=True)
        if data.get("truncated"):
            # Very large repositories exceed the recursive-tree limit (100k entries / 7 MB).
            # Walk directory by directory instead of refusing, skipping vendored/build folders.
            return await self._walk_tree(owner, repository, commit_sha)
        return data["tree"]

    async def _walk_tree(self, owner: str, repository: str, root_sha: str) -> list[dict[str, Any]]:
        gate = asyncio.Semaphore(TREE_CONCURRENCY)
        requests_made = 0
        entries: list[dict[str, Any]] = []
        skipped_directories = 0

        async def walk(tree_sha: str, prefix: str) -> None:
            nonlocal requests_made, skipped_directories
            requests_made += 1
            if requests_made > MAX_TREE_REQUESTS:
                raise AnalysisError(
                    "REPOSITORY_TOO_LARGE",
                    "This repository has too many directories to analyze within the request budget.", status_code=422,
                    hint="Analyze a smaller repository or a fork containing only the relevant projects.",
                )
            async with gate:
                response = await self._get(f"/repos/{owner}/{repository}/git/trees/{tree_sha}", "repository tree")
            payload = response.json()
            children = payload.get("tree") if isinstance(payload, dict) else None
            if not isinstance(children, list):
                raise AnalysisError("GITHUB_BAD_RESPONSE", "GitHub returned an invalid repository tree", status_code=502, retryable=True)
            subtrees = []
            for item in children:
                if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                    continue
                full = {**item, "path": f"{prefix}{item['path']}"}
                if item.get("type") == "tree":
                    if item["path"] in SKIPPED_DIRECTORIES:
                        skipped_directories += 1
                    elif isinstance(item.get("sha"), str):
                        subtrees.append(walk(item["sha"], f"{full['path']}/"))
                else:
                    entries.append(full)
            await asyncio.gather(*subtrees)

        await walk(root_sha, "")
        self.diagnostics.append(Diagnostic(
            "REPOSITORY_TREE_TRUNCATED", "info",
            f"The repository is too large for GitHub's single-call tree listing, so it was scanned directory by directory "
            f"({requests_made} requests; {skipped_directories} vendored/build folders such as node_modules were skipped).",
        ))
        return entries

    async def get_file_content(self, owner: str, repository: str, blob_sha: str) -> str:
        cache_key = (f"{owner}/{repository}".lower(), blob_sha)
        cached = _BLOB_CACHE.get(cache_key)
        if cached is not None:
            return cached
        response = await self._get(f"/repos/{owner}/{repository}/git/blobs/{blob_sha}", "file")
        data = response.json()
        if not isinstance(data, dict) or data.get("encoding") != "base64" or not isinstance(data.get("content"), str):
            raise ValueError("GitHub returned an unsupported blob encoding")
        if isinstance(data.get("size"), int) and data["size"] > MAX_BLOB_BYTES:
            raise ValueError(f"file is {data['size'] // (1024 * 1024)} MB, above the {MAX_BLOB_BYTES // (1024 * 1024)} MB limit")
        # GitHub's blob API may include whitespace/newlines in its Base64 text.
        # Strip whitespace before strict validation so formatting does not make a
        # valid blob fail, while still rejecting genuinely malformed Base64.
        encoded_content = re.sub(r"\s+", "", data["content"])
        try:
            content = base64.b64decode(encoded_content, validate=True).decode("utf-8-sig")
        except (binascii.Error, UnicodeDecodeError) as exc:
            raise ValueError("GitHub returned a blob that is not valid UTF-8/base64 text") from exc
        _BLOB_CACHE.put(cache_key, content)
        return content

    async def close(self) -> None:
        await self.client.aclose()
