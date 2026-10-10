from dataclasses import dataclass,field
from typing import Any
from pathlib import PurePosixPath
 

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
            
        relative = PurePosixPath(relative_path)
                
        for pattern in workspace_root.workspace_patterns:
            pattern_path = PurePosixPath(pattern) / "package.json"
            
            if relative.match(str(pattern_path)):
                members.append(manifest_path)
                break
    return sorted(members)            

def build_npm_projects(
    dependency_files: dict[str, list[dict[str, str]]],
    manifest_contents: dict[str, dict[str, Any]],
) -> tuple[list[NpmProject], list[OrphanedLockfile]]:
    manifests = dependency_files["manifests"]
    lockfiles = dependency_files["lockfiles"]

    lockfiles_by_directory = {
        get_parent_directory(lockfile["path"]): lockfile
        for lockfile in lockfiles
    }

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