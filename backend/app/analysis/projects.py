from dataclasses import dataclass,field
from fnmatch import fnmatchcase
from typing import Any
 

@dataclass
class ProjectDependency:
    dependency_path:str
    dependency_type:str
    
@dataclass
class NpmProject:
    root_path: str
    manifest: dict[str, str]
    manifest_data: dict[str,Any]
    lockfile: dict[str, str] | None
    package_name: str | None
    package_version: str | None
    is_workspace_root: bool
    workspace_patterns:list[str]
    workspace_members:list[str]
    dependencies: list[ProjectDependency] = field(
        default_factory = list
    )

@dataclass
class OrphanedLockfile:
    path: str
    reason: str


def get_parent_directory(path: str) -> str:
    if "/" not in path:
        return ""

    return path.rsplit("/", maxsplit=1)[0]

def extract_workspace_patterns(
    package_data:dict[str,Any],
) -> list[str]:
    workspaces = package_data.get("workspaces")
    
    if isinstance(workspaces,list):
        return [
            pattern 
            for pattern in workspaces
            if isinstance(pattern,str)
        ]
        
    if isinstance(workspaces,dict):
        packages = workspaces.get("packages")
        
        if isinstance(packages,list):
            return [
                pattern
                for pattern in packages
                if isinstance(pattern,str)
            ]    
            
    return []

def _segments(path: str) -> list[str]:
    return [segment for segment in path.split("/") if segment and segment != "."]


def _glob_segments(pattern: list[str], path: list[str]) -> bool:
    """Match a directory against a workspace glob, segment by segment.

    ``*``/``?``/``[]`` match within one segment; ``**`` matches any number of segments.
    The match is anchored at both ends, unlike ``PurePath.match`` (right-anchored), which
    wrongly treated ``apps/x/packages/foo`` as a member of ``packages/*``.
    """
    if not pattern:
        return not path
    head, rest = pattern[0], pattern[1:]
    if head == "**":
        return any(_glob_segments(rest, path[skip:]) for skip in range(len(path) + 1))
    return bool(path) and fnmatchcase(path[0], head) and _glob_segments(rest, path[1:])


def workspace_directory_matches(relative_directory: str, patterns: list[str]) -> bool:
    """True when the directory is selected by the patterns (``!negations`` applied last)."""
    target = _segments(relative_directory)
    included = False
    for raw in patterns:
        negated = raw.startswith("!")
        pattern = _segments(raw[1:] if negated else raw)
        if not pattern or not _glob_segments(pattern, target):
            continue
        if negated:
            return False
        included = True
    return included


def resolve_workspace_members(
    workspace_root:NpmProject,
    manifest_paths:list[str],
) -> list[str]:
    members: list[str] = []

    root = workspace_root.root_path

    for manifest_path in manifest_paths:
        if manifest_path == workspace_root.manifest["path"]:
            continue

        if root:
            prefix = f"{root}/"
            if not manifest_path.startswith(prefix):
                continue

            relative_path = manifest_path[len(prefix):]
        else:
            relative_path = manifest_path

        relative_directory = relative_path.rsplit("/", 1)[0] if "/" in relative_path else ""
        if relative_directory and workspace_directory_matches(relative_directory, workspace_root.workspace_patterns):
            members.append(manifest_path)
    return sorted(members)

def build_npm_projects(
    dependency_files: dict[str, list[dict[str, str]]],
    manifest_contents: dict[str, dict[str, Any]],
) -> tuple[list[NpmProject], list[OrphanedLockfile]]:
    manifests = dependency_files["manifests"]
    lockfiles = dependency_files["lockfiles"]

    # npm-shrinkwrap.json takes precedence over package-lock.json in the same directory.
    # The manifest's ``packageManager`` field ("pnpm@9.1.0") is the strongest signal of which
    # lockfile is authoritative when several exist; otherwise prefer lockfiles this analyzer
    # can resolve (npm, pnpm) over yarn.
    default_priority = {"npm-shrinkwrap.json": 0, "package-lock.json": 1, "pnpm-lock.yaml": 2, "yarn.lock": 3}
    manager_files = {
        "npm": ("npm-shrinkwrap.json", "package-lock.json"),
        "pnpm": ("pnpm-lock.yaml",),
        "yarn": ("yarn.lock",),
    }
    manifest_by_directory = {get_parent_directory(m["path"]): manifest_contents.get(m["path"], {}) for m in manifests}

    def lockfile_rank(item: dict[str, str]) -> tuple[int, int]:
        name = item["path"].rsplit("/", 1)[-1]
        declared = manifest_by_directory.get(get_parent_directory(item["path"]), {}).get("packageManager")
        manager = declared.split("@", 1)[0] if isinstance(declared, str) else None
        preferred = 0 if name in manager_files.get(manager, ()) else 1
        return preferred, default_priority.get(name, 99)

    lockfiles_by_directory: dict[str, dict[str, str]] = {}
    for lockfile in sorted(lockfiles, key=lambda item: (get_parent_directory(item["path"]), lockfile_rank(item))):
        directory = get_parent_directory(lockfile["path"])
        lockfiles_by_directory.setdefault(directory, lockfile)

    projects: list[NpmProject] = []

    for manifest in manifests:
        path = manifest["path"]
        directory = get_parent_directory(path)
        package_data = manifest_contents.get(path, {})

        workspace_patterns = extract_workspace_patterns(
            package_data
        )

        projects.append(
            NpmProject(
                root_path=directory,
                manifest=manifest,
                manifest_data=package_data,
                lockfile=lockfiles_by_directory.get(
                    directory
                ),
                package_name=package_data.get("name"),
                package_version=package_data.get("version"),
                is_workspace_root=bool(
                    workspace_patterns
                ),
                workspace_patterns=workspace_patterns,
                workspace_members=[],
            )
        )

    manifest_paths = [
        manifest["path"]
        for manifest in manifests
    ]

    for project in projects:
        if not project.is_workspace_root:
            continue

        project.workspace_members = (
            resolve_workspace_members(
                project,
                manifest_paths,
            )
        )

    manifest_directories = {
        get_parent_directory(manifest["path"])
        for manifest in manifests
    }

    orphaned_lockfiles: list[OrphanedLockfile] = []

    for lockfile in lockfiles:
        directory = get_parent_directory(
            lockfile["path"]
        )

        if directory not in manifest_directories:
            orphaned_lockfiles.append(
                OrphanedLockfile(
                    path=lockfile["path"],
                    reason=(
                        "No package.json found "
                        "in the same directory"
                    ),
                )
            )

    return projects, orphaned_lockfiles