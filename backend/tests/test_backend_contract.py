import json
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from app.analysis.dependencies import resolve_dependency_path
from app.analysis.graph import DependencyType, build_dependency_graph
from app.analysis.osv import normalize_vulnerability, scan_packages
from app.analysis.sbom import build_cyclonedx_sbom
from app.github.client import GitHubClient
from app.analysis import service as service_module


class APIContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_health_and_no_manifest_error_status(self):
        from app import main as main_module
        async def no_manifests(_url):
            raise ValueError("No package.json manifests were found in this repository")
        transport = httpx.ASGITransport(app=main_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            health = await client.get("/health")
            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.json(), {"status": "ok"})
            with patch.object(main_module, "analyze_repository", side_effect=no_manifests):
                response = await client.post("/analyze", json={"repository_url": "https://github.com/acme/demo"})
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json()["detail"], "No package.json manifests were found in this repository")


class URLValidationTests(unittest.TestCase):
    def test_accepts_repo_url_and_git_suffix(self):
        self.assertEqual(GitHubClient.parse_repository_url("https://github.com/acme/widget.git"), ("acme", "widget"))

    def test_rejects_non_github_and_subpage_urls(self):
        for url in ("https://example.com/acme/widget", "https://github.com/acme/widget/tree/main", "not a URL"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                GitHubClient.parse_repository_url(url)


class GraphTests(unittest.TestCase):
    def test_builds_normal_and_optional_edges_without_duplicate_normal_edge(self):
        graph = build_dependency_graph({
            "": {"name": "root", "version": "1.0.0"},
            "node_modules/app": {"version": "1.0.0", "dependencies": {"lib": "^1"}, "optionalDependencies": {"lib": "^1"}},
            "node_modules/lib": {"version": "1.2.0", "dev": True},
        })
        self.assertEqual(len(graph.nodes), 2)
        self.assertEqual(len(graph.edges), 1)
        self.assertEqual(graph.edges[0].dependency_type, DependencyType.OPTIONAL)
        self.assertTrue(graph.nodes["node_modules/lib"].dev)

    def test_resolves_workspace_link_using_target_metadata(self):
        graph = build_dependency_graph({
            "": {"name": "root", "version": "1.0.0"},
            "node_modules/workspace-lib": {"resolved": "packages/lib", "link": True},
            "packages/lib": {"name": "workspace-lib", "version": "2.3.4", "dependencies": {"tiny": "^1"}},
            "node_modules/tiny": {"version": "1.1.0"},
        })
        alias = graph.nodes["node_modules/workspace-lib"]
        self.assertEqual(alias.version, "2.3.4")
        self.assertTrue(alias.is_link)
        self.assertTrue(any(e.source == "node_modules/workspace-lib" and e.target == "node_modules/tiny" for e in graph.edges))

    def test_missing_version_is_reported_not_fabricated(self):
        graph = build_dependency_graph({"node_modules/broken": {"resolved": "https://example.test/broken.tgz"}})
        self.assertNotIn("node_modules/broken", graph.nodes)
        self.assertTrue(graph.unresolved)


class RepositoryServiceTests(unittest.IsolatedAsyncioTestCase):
    async def _run_service(self, tree, contents):
        class FakeGitHub:
            async def get_repository(self, url):
                return {"owner": {"login": "acme"}, "name": "demo", "full_name": "acme/demo", "default_branch": "main"}
            async def get_latest_commit_sha(self, owner, repository, branch):
                return "abc123"
            async def get_repository_tree(self, owner, repository, commit_sha):
                return tree
            async def get_file_content(self, owner, repository, sha):
                return contents[sha]
            async def close(self):
                self.closed = True
        fake = FakeGitHub()
        with patch.object(service_module, "GitHubClient", return_value=fake), patch.object(service_module, "scan_packages", new=AsyncMock(return_value=[])):
            result = await service_module.analyze_repository("https://github.com/acme/demo")
        return result

    async def test_manifest_without_lockfile_returns_partial_inventory(self):
        tree = [{"type": "blob", "path": "package.json", "sha": "manifest"}]
        result = await self._run_service(tree, {"manifest": json.dumps({"name": "demo", "dependencies": {"left-pad": "^1.3.0"}})})
        self.assertEqual(result["summary"]["manifests_found"], 1)
        self.assertEqual(result["summary"]["lockfiles_found"], 0)
        self.assertEqual(result["projects"][0]["direct_dependencies"][0]["resolved_version"], None)
        self.assertEqual(result["analysis_metadata"]["vulnerability_analysis_status"], "partial")
        self.assertTrue(result["analysis_metadata"]["warnings"])

    async def test_lockfile_inventory_does_not_read_nonexistent_is_dev_field(self):
        tree = [
            {"type": "blob", "path": "package.json", "sha": "manifest"},
            {"type": "blob", "path": "package-lock.json", "sha": "lock"},
        ]
        lockfile = {"name": "demo", "lockfileVersion": 3, "packages": {
            "": {"name": "demo", "version": "1.0.0"},
            "node_modules/left-pad": {"version": "1.3.0", "resolved": "https://registry.npmjs.org/left-pad/-/left-pad-1.3.0.tgz", "dev": True},
        }}
        result = await self._run_service(tree, {
            "manifest": json.dumps({"name": "demo", "dependencies": {"left-pad": "^1.3.0"}}),
            "lock": json.dumps(lockfile),
        })
        self.assertEqual(result["summary"]["total_packages"], 1)
        self.assertEqual(result["packages"][0]["version"], "1.3.0")
        self.assertTrue(result["packages"][0]["is_direct"])
        self.assertTrue(result["packages"][0]["is_dev"])
        self.assertEqual(result["analysis_metadata"]["vulnerability_analysis_status"], "complete")

    async def test_repository_without_manifests_has_clear_error(self):
        class FakeGitHub:
            async def get_repository(self, url):
                return {"owner": {"login": "acme"}, "name": "demo", "default_branch": "main"}
            async def get_latest_commit_sha(self, *args): return "abc123"
            async def get_repository_tree(self, *args): return [{"type": "blob", "path": "README.md", "sha": "readme"}]
            async def close(self): pass
        with patch.object(service_module, "GitHubClient", return_value=FakeGitHub()):
            with self.assertRaisesRegex(ValueError, "No package.json manifests"):
                await service_module.analyze_repository("https://github.com/acme/demo")


class SBOMTests(unittest.TestCase):
    def test_cyclonedx_contains_project_package_and_dependency_relationship(self):
        projects = [{
            "path": "", "name": "demo", "version": "1.0.0", "has_resolved_graph": True,
            "graph_lockfile_path": "package-lock.json",
            "direct_dependencies": [{"name": "@scope/lib", "resolved": True, "package_path": "node_modules/@scope/lib"}],
        }]
        packages = [{
            "id": "package-lock.json::node_modules/@scope/lib", "name": "@scope/lib", "version": "2.0.0",
            "path": "node_modules/@scope/lib", "lockfile": "package-lock.json", "is_direct": True,
        }]
        sbom = build_cyclonedx_sbom({"name": "acme/demo", "commit_sha": "abc"}, projects, packages, [])
        self.assertEqual(sbom["bomFormat"], "CycloneDX")
        self.assertEqual(sbom["specVersion"], "1.6")
        package_component = next(c for c in sbom["components"] if c.get("type") == "library")
        self.assertEqual(package_component["purl"], "pkg:npm/%40scope/lib@2.0.0")
        project_ref = next(c["bom-ref"] for c in sbom["components"] if c.get("type") == "application")
        project_dependency = next(d for d in sbom["dependencies"] if d["ref"] == project_ref)
        self.assertEqual(project_dependency["dependsOn"], [packages[0]["id"]])


class OSVTests(unittest.IsolatedAsyncioTestCase):
    async def test_batch_response_maps_vulnerability_to_package_instance(self):
        class FakeOSV:
            async def query_batch(self, queries):
                if queries != [{"package": {"name": "demo", "ecosystem": "npm"}, "version": "1.0.0"}]:
                    raise AssertionError(f"Unexpected OSV queries: {queries!r}")
                # querybatch returns an ID stub, not the full advisory.
                return [{"vulns": [{"id": "GHSA-demo", "modified": "2026-09-01T00:00:00Z"}]}]
            async def get_vulnerability(self, vulnerability_id):
                self.detail_calls = getattr(self, "detail_calls", []) + [vulnerability_id]
                return {
                    "id": "GHSA-demo", "summary": "Demo issue", "aliases": ["CVE-2026-0001"],
                    "database_specific": {"severity": "HIGH"},
                    "affected": [{"ranges": [{"events": [{"introduced": "0"}, {"fixed": "1.2.0"}]}]}],
                }
            async def close(self):
                pass
        packages = [{"id": "package-lock.json::node_modules/demo", "name": "demo", "version": "1.0.0", "path": "node_modules/demo", "lockfile": "package-lock.json"}]
        findings = await scan_packages(packages, client=FakeOSV())
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["severity"], "HIGH")
        self.assertEqual(findings[0]["fixed_versions"], ["1.2.0"])
        self.assertEqual(findings[0]["package_id"], packages[0]["id"])

    async def test_full_advisory_is_fetched_once_for_multiple_package_instances(self):
        class FakeOSV:
            def __init__(self):
                self.detail_calls = []
            async def query_batch(self, queries):
                return [{"vulns": [{"id": "GHSA-shared"}]} for _ in queries]
            async def get_vulnerability(self, vulnerability_id):
                self.detail_calls.append(vulnerability_id)
                return {"id": vulnerability_id, "summary": "Shared advisory", "database_specific": {"severity": "LOW"}}
            async def close(self):
                pass

        client = FakeOSV()
        packages = [
            {"id": "lock::node_modules/demo", "name": "demo", "version": "1.0.0", "path": "node_modules/demo", "lockfile": "lock"},
            {"id": "other-lock::node_modules/demo", "name": "demo", "version": "1.0.0", "path": "node_modules/demo", "lockfile": "other-lock"},
        ]
        findings = await scan_packages(packages, client=client)
        self.assertEqual(len(findings), 2)
        self.assertEqual(client.detail_calls, ["GHSA-shared"])
        self.assertTrue(all(item["summary"] == "Shared advisory" for item in findings))

    def test_severity_unknown_when_osv_does_not_supply_it(self):
        package = {"id": "x", "name": "demo", "version": "1.0.0", "path": "node_modules/demo", "lockfile": "package-lock.json"}
        result = normalize_vulnerability({"id": "OSV-1"}, package)
        self.assertEqual(result["severity"], "UNKNOWN")
        self.assertEqual(result["fixed_versions"], [])


if __name__ == "__main__":
    unittest.main()
