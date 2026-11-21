from typing import Any


MANIFEST_FILES = {
    "package.json",
}

LOCK_FILES = {
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "pnpm-lock.yaml",
}


def discover_dependency_files(
    tree: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    manifests: list[str] = []
    lockfiles: list[str] = []

    for entry in tree:
        if entry.get("type") != "blob":
            continue

        path = entry.get("path", "")
        # Committed node_modules (and VCS metadata) contain third-party manifests that are
        # not projects of this repository; analyzing them would inflate projects and findings.
        segments = path.split("/")
        if "node_modules" in segments[:-1] or ".git" in segments[:-1]:
            continue
        filename = path.rsplit("/", maxsplit=1)[-1]
        sha = entry.get("sha")
        
        if not sha:
            continue
        
        file_info = {
            "path": path,
            "sha": sha,
        }
        if isinstance(entry.get("size"), int):
            file_info["size"] = entry["size"]

        if filename in MANIFEST_FILES:
            manifests.append(file_info)

        elif filename in LOCK_FILES:
            lockfiles.append(file_info)

    return {
        "manifests": sorted(
            manifests,
            key=lambda item: item["path"],
        ),
        "lockfiles": sorted(
            lockfiles,
            key=lambda item: item["path"],
        ),
    }