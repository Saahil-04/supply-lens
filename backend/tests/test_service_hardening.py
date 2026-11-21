"""End-to-end service + API behaviour for the hardened pipeline (fake GitHub, fake OSV)."""
import json
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

from app import main
from app.analysis import service as service_module
from app.analysis.store import analysis_store
from app.errors import AnalysisError

FIXTURES = Path(__file__).parent / "fixtures"
P8_MANIFEST = {
    "name": "fixture-app", "version": "1.0.0",
    "dependencies": {"express": "4.17.1", "lodash": "4.17.20", "strip-ansi-cjs": "npm:strip-ansi@^6.0.1"},
    "devDependencies": {"mocha": "^10.2.0"}, "optionalDependencies": {"fsevents": "^2.3.3"},
}


def fake_github(tree, contents, *, repo="demo"):
    async def get_file(owner, name, sha):
        value = contents[sha]
        if isinstance(value, Exception):
            raise value
        return value
    return type("FakeGitHub", (), {
        "get_repository": AsyncMock(return_value={"owner": {"login": "acme"}, "name": repo, "full_name": f"acme/{repo}", "default_branch": "main"}),
        "get_latest_commit_sha": AsyncMock(return_value="abc123"),
        "get_repository_tree": AsyncMock(return_value=tree),
        "get_file_content": staticmethod(get_file) if False else (lambda self, o, n, s: get_file(o, n, s)),
        "close": AsyncMock(),
    })()


async def run(tree, contents, findings=None):
    scan = AsyncMock(return_value=findings or [])
    with patch.object(service_module, "GitHubClient", return_value=fake_github(tree, contents)), \
         patch.object(service_module, "scan_packages", new=scan):
        return await service_module.analyze_repository("https://github.com/acme/demo"), scan


def codes(result):
    return [d["code"] for d in result["analysis_metadata"]["diagnostics"]]


class PipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_npm_lockfile_v1_is_now_analyzed(self):
        tree = [{"type": "blob", "path": "package.json", "sha": "m"}, {"type": "blob", "path": "package-lock.json", "sha": "l"}]
        result, _ = await run(tree, {"m": json.dumps(P8_MANIFEST), "l": (FIXTURES / "n1" / "package-lock.json").read_text()})
        self.assertGreater(result["summary"]["total_packages"], 100)
        self.assertEqual(result["summary"]["projects_with_resolved_graph"], 1)
        self.assertIn("LOCKFILE_LEGACY_FORMAT", codes(result))
        direct = {d["name"]: d for d in result["projects"][0]["direct_dependencies"]}
        self.assertTrue(direct["express"]["resolved"])
        self.assertEqual(result["analysis_metadata"]["lockfiles"][0]["lockfile_version"], "1")

    async def test_pnpm_v6_single_project_resolves_direct_dependencies_and_scopes(self):
        tree = [{"type": "blob", "path": "package.json", "sha": "m"}, {"type": "blob", "path": "pnpm-lock.yaml", "sha": "l"}]
        result, _ = await run(tree, {"m": json.dumps(P8_MANIFEST), "l": (FIXTURES / "p8" / "pnpm-lock.yaml").read_text()})
        direct = {d["name"]: d for d in result["projects"][0]["direct_dependencies"]}
        self.assertTrue(all(d["resolved"] for d in direct.values()), direct)
        self.assertEqual(direct["strip-ansi-cjs"]["resolved_version"], "6.0.1")
        self.assertEqual(result["analysis_metadata"]["vulnerability_analysis_status"], "complete")
        mocha = next(p for p in result["packages"] if p["name"] == "mocha")
        self.assertTrue(mocha["is_dev"] and mocha["is_direct"])
        self.assertEqual(result["analysis_metadata"]["lockfiles"][0]["format"], "pnpm")

    async def test_pnpm_workspace_links_resolve_and_root_lists_members(self):
        tree = [{"type": "blob", "path": p, "sha": p} for p in ("package.json", "packages/a/package.json", "packages/b/package.json", "pnpm-lock.yaml")]
        contents = {
            "package.json": json.dumps({"name": "root", "devDependencies": {"typescript": "^5.4.0"}}),
            "packages/a/package.json": json.dumps({"name": "@ws/a", "dependencies": {"@ws/b": "workspace:*", "lodash": "4.17.20"}}),
            "packages/b/package.json": json.dumps({"name": "@ws/b", "version": "2.5.0", "dependencies": {"lodash": "4.17.15", "minimist": "^1.2.0", "react": "*"}}),
            "pnpm-lock.yaml": (FIXTURES / "pnpmws8" / "pnpm-lock.yaml").read_text(),
        }
        result, _ = await run(tree, contents)
        by_path = {p["path"]: p for p in result["projects"]}
        link = next(d for d in by_path["packages/a"]["direct_dependencies"] if d["name"] == "@ws/b")
        self.assertEqual((link["resolved"], link["kind"], link["resolved_version"]), (True, "workspace", "2.5.0"))
        self.assertTrue(by_path[""]["is_workspace_root"])
        self.assertEqual(by_path[""]["workspace_members"], ["packages/a/package.json", "packages/b/package.json"])
        self.assertEqual(result["analysis_metadata"]["vulnerability_analysis_status"], "complete")

    async def test_yarn_only_project_says_clearly_why_it_is_partial(self):
        tree = [{"type": "blob", "path": "package.json", "sha": "m"}, {"type": "blob", "path": "yarn.lock", "sha": "y"}]
        result, scan = await run(tree, {"m": json.dumps({"name": "x", "dependencies": {"a": "^1"}}), "y": "# yarn"})
        self.assertIn("LOCKFILE_YARN_UNSUPPORTED", codes(result))
        self.assertEqual(result["analysis_metadata"]["lockfiles"][0]["status"], "unsupported")
        self.assertEqual(result["analysis_metadata"]["vulnerability_analysis_status"], "partial")
        self.assertEqual(result["analysis_metadata"]["status"], "partial")

    async def test_corrupt_lockfile_in_one_project_does_not_stop_the_others(self):
        tree = [{"type": "blob", "path": p, "sha": p} for p in ("a/package.json", "a/package-lock.json", "b/package.json", "b/package-lock.json")]
        good = {"lockfileVersion": 3, "packages": {"": {}, "node_modules/left-pad": {"version": "1.3.0"}}}
        contents = {
            "a/package.json": json.dumps({"name": "a", "dependencies": {"left-pad": "^1"}}), "a/package-lock.json": json.dumps(good),
            "b/package.json": json.dumps({"name": "b", "dependencies": {"x": "^1"}}), "b/package-lock.json": "<<<<<<< HEAD\n{",
        }
        result, _ = await run(tree, contents)
        self.assertEqual(result["summary"]["projects_with_resolved_graph"], 1)
        self.assertEqual(result["summary"]["total_packages"], 1)
        failure = next(d for d in result["analysis_metadata"]["diagnostics"] if d["code"] == "LOCKFILE_PARSE_ERROR")
        self.assertEqual(failure["path"], "b/package-lock.json")
        self.assertEqual(failure["severity"], "error")
        self.assertEqual(result["analysis_metadata"]["vulnerability_analysis_status"], "partial")
        self.assertEqual(result["analysis_metadata"]["diagnostics"][0]["severity"], "error")     # errors listed first

    async def test_unparsable_manifest_is_reported_with_its_path(self):
        tree = [{"type": "blob", "path": "package.json", "sha": "m"}, {"type": "blob", "path": "web/package.json", "sha": "w"}]
        result, _ = await run(tree, {"m": json.dumps({"name": "ok"}), "w": '{"name": '})
        diag = next(d for d in result["analysis_metadata"]["diagnostics"] if d["code"] == "MANIFEST_PARSE_ERROR")
        self.assertEqual(diag["path"], "web/package.json")
        self.assertIn("Could not parse web/package.json", result["analysis_metadata"]["warnings"][0])

    async def test_out_of_date_lockfile_names_the_missing_dependencies(self):
        tree = [{"type": "blob", "path": "package.json", "sha": "m"}, {"type": "blob", "path": "package-lock.json", "sha": "l"}]
        lock = {"lockfileVersion": 3, "packages": {"": {}, "node_modules/a": {"version": "1.0.0"}}}
        result, _ = await run(tree, {"m": json.dumps({"dependencies": {"a": "^1", "newly-added": "^2"}}), "l": json.dumps(lock)})
        diag = next(d for d in result["analysis_metadata"]["diagnostics"] if d["code"] == "DIRECT_DEPENDENCIES_UNRESOLVED")
        self.assertEqual(diag["details"]["names"], ["newly-added"])
        self.assertTrue(diag["hint"])

    async def test_optional_and_peer_declarations_do_not_make_coverage_partial(self):
        tree = [{"type": "blob", "path": "package.json", "sha": "m"}, {"type": "blob", "path": "package-lock.json", "sha": "l"}]
        lock = {"lockfileVersion": 3, "packages": {"": {}, "node_modules/a": {"version": "1.0.0"}}}
        manifest = {"dependencies": {"a": "^1"}, "peerDependencies": {"react": "*"}, "optionalDependencies": {"fsevents": "*"}}
        result, _ = await run(tree, {"m": json.dumps(manifest), "l": json.dumps(lock)})
        self.assertEqual(result["analysis_metadata"]["vulnerability_analysis_status"], "complete")

    async def test_git_sourced_packages_are_inventoried_but_flagged_not_assessed(self):
        tree = [{"type": "blob", "path": "package.json", "sha": "m"}, {"type": "blob", "path": "package-lock.json", "sha": "l"}]
        lock = {"lockfileVersion": 3, "packages": {"": {}, "node_modules/g": {"version": "1.0.0", "resolved": "git+ssh://git@github.com/u/g.git#abc"}}}
        result, _ = await run(tree, {"m": json.dumps({"dependencies": {"g": "github:u/g"}}), "l": json.dumps(lock)})
        self.assertEqual(result["summary"]["total_packages"], 1)
        self.assertIn("PACKAGES_NOT_SCANNABLE", codes(result))
        self.assertEqual(result["analysis_metadata"]["vulnerability_analysis_status"], "partial")
        self.assertEqual(result["analysis_metadata"]["coverage"]["packages_not_scannable"], 1)

    async def test_findings_explain_how_a_transitive_package_is_reached_and_the_safe_version(self):
        tree = [{"type": "blob", "path": "package.json", "sha": "m"}, {"type": "blob", "path": "package-lock.json", "sha": "l"}]
        lock = {"lockfileVersion": 3, "packages": {
            "": {}, "node_modules/top": {"version": "1.0.0", "dependencies": {"mid": "^1"}},
            "node_modules/mid": {"version": "1.0.0", "dependencies": {"leaf": "^1"}}, "node_modules/leaf": {"version": "1.0.0"}}}
        finding = {"id": "GHSA-1", "package_id": "package-lock.json::node_modules/leaf", "package_name": "leaf", "installed_version": "1.0.0",
                   "package_path": "node_modules/leaf", "lockfile": "package-lock.json", "severity": "HIGH", "fixed_versions": ["1.2.0"]}
        second = {**finding, "id": "GHSA-2", "fixed_versions": ["1.10.0"]}
        result, _ = await run(tree, {"m": json.dumps({"dependencies": {"top": "^1"}}), "l": json.dumps(lock)}, [finding, second])
        self.assertEqual(result["vulnerabilities"][0]["introduced_via"], ["top@1.0.0", "mid@1.0.0", "leaf@1.0.0"])
        self.assertFalse(result["vulnerabilities"][0]["is_direct"])
        rec = result["recommendations"][0]
        self.assertEqual(rec["minimum_safe_version"], "1.10.0")          # semantic, not lexical, ordering
        self.assertEqual(rec["fixed_versions"], ["1.2.0", "1.10.0"])
        self.assertIn("top@1.0.0", rec["recommendation"])

    async def test_rate_limit_while_downloading_files_fails_the_analysis_clearly(self):
        tree = [{"type": "blob", "path": "package.json", "sha": "m"}]
        limited = AnalysisError("GITHUB_RATE_LIMITED", "limit", status_code=429, retryable=True)
        with self.assertRaises(AnalysisError) as ctx:
            await run(tree, {"m": limited})
        self.assertEqual(ctx.exception.code, "GITHUB_RATE_LIMITED")

    async def test_osv_outage_keeps_the_inventory_and_says_so(self):
        tree = [{"type": "blob", "path": "package.json", "sha": "m"}, {"type": "blob", "path": "package-lock.json", "sha": "l"}]
        lock = {"lockfileVersion": 3, "packages": {"": {}, "node_modules/a": {"version": "1.0.0"}}}
        with patch.object(service_module, "GitHubClient", return_value=fake_github(tree, {"m": json.dumps({"dependencies": {"a": "1"}}), "l": json.dumps(lock)})), \
             patch.object(service_module, "scan_packages", new=AsyncMock(side_effect=httpx.ConnectError("down"))):
            result = await service_module.analyze_repository("https://github.com/acme/demo")
        self.assertEqual(result["analysis_metadata"]["vulnerability_analysis_status"], "failed")
        self.assertIn("OSV_UNAVAILABLE", codes(result))
        self.assertIsNone(result["summary"]["vulnerabilities_found"])
        self.assertEqual(result["summary"]["total_packages"], 1)

    async def test_metadata_reports_timings_and_coverage(self):
        tree = [{"type": "blob", "path": "package.json", "sha": "m"}]
        result, _ = await run(tree, {"m": json.dumps({"name": "x"})})
        self.assertTrue({"github_fetch", "lockfile_parse", "osv", "total"} <= set(result["analysis_metadata"]["timings_ms"]))
        self.assertIn("direct_dependencies_declared", result["analysis_metadata"]["coverage"])


class APIErrorContractTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        analysis_store._entries.clear()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()

    async def _post(self, side_effect):
        with patch.object(main, "analyze_repository", new=AsyncMock(side_effect=side_effect)):
            return await self.client.post("/analyze", json={"repository_url": "https://github.com/acme/demo"})

    async def test_analysis_error_becomes_a_structured_body_and_keeps_detail(self):
        error = AnalysisError("GITHUB_RATE_LIMITED", "GitHub's API rate limit was reached.", status_code=429, retryable=True,
                              hint="Try again later.", details={"retry_in_seconds": 42})
        response = await self._post(error)
        body = response.json()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["retry-after"], "42")
        self.assertEqual(body["detail"], "GitHub's API rate limit was reached.")
        self.assertEqual(body["error"], {"code": "GITHUB_RATE_LIMITED", "message": body["detail"], "hint": "Try again later.", "retryable": True, "details": {"retry_in_seconds": 42}})

    async def test_other_failures_all_carry_codes(self):
        for exc, status, code in ((ValueError("bad"), 422, "ANALYSIS_FAILED"), (httpx.ReadTimeout("t"), 504, "UPSTREAM_TIMEOUT"),
                                  (httpx.ConnectError("c"), 502, "UPSTREAM_UNREACHABLE"), (RuntimeError("boom"), 500, "INTERNAL_ERROR")):
            response = await self._post(exc)
            self.assertEqual((response.status_code, response.json()["error"]["code"]), (status, code))
        self.assertNotIn("boom", (await self._post(RuntimeError("boom"))).text)     # internals are not leaked

    async def test_not_found_responses_have_codes(self):
        response = await self.client.get("/analyses/nope")
        self.assertEqual((response.status_code, response.json()["error"]["code"]), (404, "NOT_FOUND"))

    async def test_server_busy_is_a_retryable_503(self):
        with patch.object(main._analysis_slots, "locked", return_value=True):
            response = await self._post(None)
        self.assertEqual((response.status_code, response.json()["error"]["code"], response.json()["error"]["retryable"]), (503, "SERVER_BUSY", True))

    async def test_diagnostics_endpoint_and_severity_ordering(self):
        result = {
            "repository": {}, "summary": {}, "packages": [],
            "vulnerabilities": [
                {"id": "A", "severity": "MEDIUM", "cvss_score": 6.0, "package_name": "p"},
                {"id": "B", "severity": "CRITICAL", "cvss_score": None, "package_name": "p"},     # unscored but critical
                {"id": "C", "severity": "LOW", "cvss_score": 3.0, "package_name": "p"},
            ],
            "analysis_metadata": {"status": "partial", "vulnerability_analysis_status": "partial", "diagnostics_summary": {"error": 1, "warning": 1, "info": 0},
                                  "diagnostics": [{"code": "X", "severity": "error", "message": "m"}, {"code": "Y", "severity": "warning", "message": "n"}], "lockfiles": [], "coverage": {}},
        }
        with patch.object(main, "analyze_repository", new=AsyncMock(return_value=result)):
            created = (await self.client.post("/analyze", json={"repository_url": "https://github.com/acme/demo"})).json()
        self.assertEqual(created["diagnostics_summary"]["error"], 1)
        analysis_id = created["analysis_id"]
        diagnostics = (await self.client.get(f"/analyses/{analysis_id}/diagnostics", params={"severity": "error"})).json()
        self.assertEqual([d["code"] for d in diagnostics["items"]], ["X"])
        vulns = (await self.client.get(f"/analyses/{analysis_id}/vulnerabilities")).json()
        self.assertEqual([v["id"] for v in vulns["items"]], ["B", "A", "C"])           # severity first, then score


if __name__ == "__main__":
    unittest.main()


class AggregationTests(unittest.IsolatedAsyncioTestCase):
    async def test_many_lockfileless_projects_become_one_diagnostic(self):
        tree = [{"type": "blob", "path": "package.json", "sha": "root"}] + [{"type": "blob", "path": f"examples/e{i}/package.json", "sha": f"e{i}"} for i in range(40)]
        contents = {"root": json.dumps({"name": "root"}), **{f"e{i}": json.dumps({"dependencies": {"a": "1", "b": "2"}}) for i in range(40)}}
        result, _ = await run(tree, contents)
        found = [d for d in result["analysis_metadata"]["diagnostics"] if d["code"] == "PROJECT_WITHOUT_LOCKFILE"]
        self.assertEqual(len(found), 1)
        self.assertEqual((found[0]["details"]["count"], found[0]["details"]["dependencies_declared"]), (40, 80))
        self.assertEqual(found[0]["details"]["by_top_level_directory"], {"examples": 40})
        self.assertEqual(result["analysis_metadata"]["coverage"]["projects_without_lockfile"], 40)
        self.assertEqual(result["analysis_metadata"]["vulnerability_analysis_status"], "partial")
