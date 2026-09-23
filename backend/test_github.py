import asyncio
import json
from pathlib import Path
from app.analysis.projects import (
    build_npm_projects,
    resolve_workspace_members,
    )
from app.github.client import GitHubClient
from app.analysis.discovery import discover_dependency_files

async def main():
    client = GitHubClient()
    try:
        repository = await client.get_repository(
            "https://github.com/Saahil-04/Saransh-AI"
        )
        
        owner,repo = client.parse_repository_url(
            "https://github.com/Saahil-04/Saransh-AI"
        )
        
        branch = repository["default_branch"]
        
        commit_sha = await client.get_latest_commit_sha(
            owner,repo,branch,
        )
        
        tree = await client.get_repository_tree(
            owner,repo,commit_sha,
        )
        
        print("Repository:",repository["full_name"])
        print("Default branch:",branch)
        print("Commit SHA:",commit_sha)
        print("Files Discovered:",len(tree))
        
        print("\nFirst 10 entries:")
        for entry in tree[:10]:
            print(entry["type"],entry["path"])
            
        dependency_files = discover_dependency_files(tree)
        
        print("\nReading manifest files:")

        for file in dependency_files["manifests"]:
            content = await client.get_file_content(
                owner,
                repo,
                file["sha"],
            )

            print(f"\n--- {file['path']} ---")
            print(content[:500])        
        
        print("\nDependency files:")
        print("\nManifests")
        for path in dependency_files["manifests"]:
            print(" ",path)    
        
        print("\nLockfiles")
        for path in dependency_files["lockfiles"]:
            print(" ",path)
            
        manifest_contents = {}
        backend_manifest_content = None

        for manifest in dependency_files["manifests"]:
            content = await client.get_file_content(
                owner,
                repo,
                manifest["sha"],
            )

            try:
                manifest_data = json.loads(content)
                manifest_contents[manifest["path"]] = manifest_data

                if manifest["path"] == "backend/package.json":
                    backend_manifest_content = content

            except json.JSONDecodeError:
                print(
                    f"Invalid JSON in {manifest['path']}"
                )
               
        projects, orphaned_lockfiles = build_npm_projects(
            dependency_files,
            manifest_contents,
        ) 
        
        manifest_paths =[
            manifest["path"]
            for manifest in dependency_files["manifests"]
        ]
        
        for project in projects:
            if project.is_workspace_root:
                project.workspace_members = (
                    resolve_workspace_members(
                        project,
                        manifest_paths,
                    )
                )
        
        print("\nNPM Projects:")

        for project in projects:
            print(f"\nProject: {project.root_path or '/'}")
            print(f"  Name: {project.package_name}")
            print(f"  Version: {project.package_version}")
            print(
                f"  Lockfile: "
                f"{project.lockfile['path'] if project.lockfile else 'None'}"
            )
            print(
                f"  Workspace root: "
                f"{project.is_workspace_root}"
            )
            print(f"  Workspace patterns: {project.workspace_patterns}")
            print(
                f" Workspace members: "
                f"{project.workspace_members}"
            )

        print("\nOrphaned Lockfiles:")

        for lockfile in orphaned_lockfiles:
            print(f"  {lockfile.path}")
            print(f"    Reason: {lockfile.reason}")       
            
        print("\nInspecting backend package-lock.json")

        backend_lockfile = next(
            file
            for file in dependency_files["lockfiles"]
            if file["path"] == "backend/package-lock.json"
        )

        lockfile_content = await client.get_file_content(
            owner,
            repo,
            backend_lockfile["sha"],
        )

        lockfile_data = json.loads(lockfile_content)
        
        Path("temp-npm-test").mkdir(exist_ok=True)

        Path(
            "temp-npm-test/saransh-backend-package-lock.json"
            ).write_text(
                lockfile_content,
                encoding="utf-8",
            )
            
        if backend_manifest_content is not None:    
            Path(
                    "temp-npm-test/saransh-backend-package.json"
                ).write_text(
                    backend_manifest_content,
                    encoding="utf-8",
                )

        print("\nLockfile version:")
        print(lockfile_data.get("lockfileVersion"))

        print("\nTop-level keys:")
        print(list(lockfile_data.keys()))

        packages = lockfile_data.get("packages", {})

        print("\nNumber of package entries:")
        print(len(packages))

        print("\nFirst 10 package entries:")

        for path, package in list(packages.items())[:10]:
            print(f"\nPath: {path}")
            print(f"Data: {package}")
                
    finally:
        await client.close()
        
if __name__ == "__main__":
    asyncio.run(main())
       
        