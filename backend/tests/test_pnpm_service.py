import json
import unittest
from unittest.mock import AsyncMock, patch

from app.analysis import service as service_module


class PnpmServiceIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_pnpm_lockfile_flows_into_inventory_and_direct_dependencies(self):
        tree = [
            {"type": "blob", "path": "package.json", "sha": "manifest"},
            {"type": "blob", "path": "pnpm-lock.yaml", "sha": "lock"},
        ]
        manifest = {"name": "demo", "dependencies": {"foo": "^1.2.0"}}
        lockfile = """lockfileVersion: '9.0'
importers:
  .:
    dependencies:
      foo:
        specifier: ^1.2.0
        version: 1.2.0
packages:
  foo@1.2.0:
    resolution:
      integrity: sha512-foo
  bar@2.0.0:
    resolution:
      integrity: sha512-bar
snapshots:
  foo@1.2.0:
    dependencies:
      bar: 2.0.0
  bar@2.0.0: {}
"""
        fake_github = type("FakeGitHub", (), {
            "get_repository": AsyncMock(return_value={
                "owner": {"login": "acme"}, "name": "demo",
                "full_name": "acme/demo", "default_branch": "main",
            }),
            "get_latest_commit_sha": AsyncMock(return_value="abc123"),
            "get_repository_tree": AsyncMock(return_value=tree),
            "get_file_content": AsyncMock(side_effect=lambda owner, repo, sha: {
                "manifest": json.dumps(manifest), "lock": lockfile,
            }[sha]),
            "close": AsyncMock(),
        })()

        with (
            patch.object(service_module, "GitHubClient", return_value=fake_github),
            patch.object(service_module, "scan_packages", new=AsyncMock(return_value=[])),
        ):
            result = await service_module.analyze_repository("https://github.com/acme/demo")

        self.assertEqual(result["summary"]["total_packages"], 2)
        self.assertEqual(result["summary"]["dependency_edges"], 1)
        self.assertEqual(result["summary"]["projects_with_resolved_graph"], 1)
        self.assertEqual(result["analysis_metadata"]["vulnerability_analysis_status"], "complete")
        direct = result["projects"][0]["direct_dependencies"][0]
        self.assertEqual(direct["name"], "foo")
        self.assertEqual(direct["resolved_version"], "1.2.0")
        self.assertTrue(direct["resolved"])
        self.assertEqual(result["analysis_metadata"]["supported_package_manager"], "npm, pnpm")

    async def test_pnpm_workspace_importers_map_to_matching_manifests(self):
        tree = [
            {"type": "blob", "path": "package.json", "sha": "root-manifest"},
            {"type": "blob", "path": "packages/lib/package.json", "sha": "lib-manifest"},
            {"type": "blob", "path": "pnpm-lock.yaml", "sha": "lock"},
        ]
        manifests = {
            "root-manifest": {"name": "workspace-root", "devDependencies": {"root-tool": "^1.0.0"}},
            "lib-manifest": {"name": "@demo/lib", "dependencies": {"foo": "^1.2.0"}},
        }
        lockfile = """lockfileVersion: '9.0'
importers:
  .:
    devDependencies:
      root-tool:
        specifier: ^1.0.0
        version: 1.0.0
  packages/lib:
    dependencies:
      foo:
        specifier: ^1.2.0
        version: 1.2.0
packages:
  root-tool@1.0.0: {}
  foo@1.2.0: {}
snapshots:
  root-tool@1.0.0: {}
  foo@1.2.0: {}
"""
        fake_github = type("FakeGitHub", (), {
            "get_repository": AsyncMock(return_value={
                "owner": {"login": "acme"}, "name": "workspace",
                "full_name": "acme/workspace", "default_branch": "main",
            }),
            "get_latest_commit_sha": AsyncMock(return_value="abc123"),
            "get_repository_tree": AsyncMock(return_value=tree),
            "get_file_content": AsyncMock(side_effect=lambda owner, repo, sha: (
                json.dumps(manifests[sha]) if sha in manifests else lockfile
            )),
            "close": AsyncMock(),
        })()

        with (
            patch.object(service_module, "GitHubClient", return_value=fake_github),
            patch.object(service_module, "scan_packages", new=AsyncMock(return_value=[])),
        ):
            result = await service_module.analyze_repository("https://github.com/acme/workspace")

        self.assertEqual(result["summary"]["projects_with_resolved_graph"], 2)
        by_path = {project["path"]: project for project in result["projects"]}
        self.assertTrue(by_path[""]["has_resolved_graph"])
        self.assertTrue(by_path["packages/lib"]["has_resolved_graph"])
        lib_direct = by_path["packages/lib"]["direct_dependencies"][0]
        self.assertEqual(lib_direct["name"], "foo")
        self.assertEqual(lib_direct["resolved_version"], "1.2.0")
        self.assertTrue(lib_direct["resolved"])


if __name__ == "__main__":
    unittest.main()
