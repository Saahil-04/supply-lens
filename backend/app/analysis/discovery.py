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
) -> dict[str, list[dict[str, str]]]:
    manifests: list[str] = []
    lockfiles: list[str] = []

    for entry in tree:
        if entry.get("type") != "blob":
            continue

        path = entry.get("path", "")
        filename = path.rsplit("/", maxsplit=1)[-1]
        sha = entry.get("sha")
        
        if not sha:
            continue
        
        file_info = {
            "path": path,
            "sha": sha,
        }        

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