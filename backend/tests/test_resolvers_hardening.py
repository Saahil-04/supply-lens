"""Resolver / graph / OSV / GitHub-client hardening tests (unit level, no network)."""
import json
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

from app.analysis import osv as osv_module
from app.analysis.discovery import discover_dependency_files
from app.analysis.graph import build_dependency_graph
from app.analysis.lockfiles import parse_lockfile
from app.analysis.osv import OSVClient, ScanReport, cvss3_base_score, normalize_vulnerability, scan_packages
from app.analysis.pnpm import build_pnpm_dependency_graph, parse_pnpm_lockfile
from app.analysis.projects import build_npm_projects, workspace_directory_matches
from app.errors import AnalysisError
from app.github.client import GitHubClient

FIXTURES = Path(__file__).parent / "fixtures"


def pnpm_graph(name):
    return build_pnpm_dependency_graph(parse_pnpm_lockfile((FIXTURES / name / "pnpm-lock.yaml").read_text()))


# --------------------------------------------------------------------------- pnpm
class PnpmFormatTests(unittest.TestCase):
    """p7/p8/p9 are the same project locked by pnpm 7 (v5.4), pnpm 8 (v6.0) and pnpm 9 (v9.0)."""

    def test_all_three_formats_agree_on_packages_and_edges(self):
        sets = {}
        for name in ("p7", "p8", "p9"):
            graph = pnpm_graph(name)
            self.assertEqual(graph.unresolved, [], name)
            sets[name] = {(n.name, n.version) for n in graph.nodes.values()}
            self.assertEqual(len(graph.edges), 175, name)
        self.assertEqual(sets["p7"], sets["p8"])
        self.assertEqual(sets["p8"], sets["p9"])
        self.assertGreater(len(sets["p9"]), 100)

    def test_v6_slash_at_keys_are_parsed(self):
        # Regression: pnpm 8 writes '/name@1.0.0'. The previous parser produced 0 packages.
        graph = pnpm_graph("p8")
        self.assertIn(("accepts", "1.3.8"), {(n.name, n.version) for n in graph.nodes.values()})

    def test_top_level_importer_is_synthesised_for_single_project_lockfiles(self):
        # pnpm <= 8 without a workspace has no `importers:`; direct deps sit at the top level.
        for name in ("p7", "p8"):
            direct = pnpm_graph(name).importer_dependencies["."]
            self.assertEqual(set(direct), {"express", "lodash", "strip-ansi-cjs", "fsevents", "mocha"}, name)

    def test_npm_alias_dependency_resolves_to_the_real_package(self):
        for name in ("p7", "p8", "p9"):
            graph = pnpm_graph(name)
            target = graph.nodes[graph.importer_dependencies["."]["strip-ansi-cjs"]]
            self.assertEqual((target.name, target.version), ("strip-ansi", "6.0.1"), name)

    def test_dev_and_optional_flags_are_derived_from_importer_reachability(self):
        for name in ("p7", "p8", "p9"):
            graph = pnpm_graph(name)
            by_name = {}
            for node in graph.nodes.values():
                by_name.setdefault(node.name, []).append(node)
            self.assertTrue(all(n.dev for n in by_name["mocha"]), name)
            self.assertFalse(any(n.dev for n in by_name["express"]), name)
            self.assertTrue(all(n.optional for n in by_name["fsevents"]), name)
            self.assertFalse(any(n.optional for n in by_name["express"]), name)

    def test_workspace_link_dependencies_are_links_not_unresolved(self):
        for name in ("pnpmws8", "pnpmws9"):
            graph = pnpm_graph(name)
            self.assertEqual(graph.unresolved, [], name)
            self.assertEqual(graph.workspace_links["packages/a"], {"@ws/b": "packages/b"})
            self.assertNotIn("@ws/b", graph.importer_dependencies["packages/a"])

    def test_git_and_directory_sources_are_not_registry_packages(self):
        graph = build_pnpm_dependency_graph(parse_pnpm_lockfile("""lockfileVersion: '9.0'
importers:
  .:
    dependencies:
      gitdep: {specifier: 'github:u/r', version: 'https://codeload.github.com/u/r/tar.gz/abc'}
      local: {specifier: 'file:../x', version: 'file:../x'}
      normal: {specifier: ^1.0.0, version: 1.0.0}
packages:
  gitdep@https://codeload.github.com/u/r/tar.gz/abc:
    resolution: {tarball: 'https://codeload.github.com/u/r/tar.gz/abc'}
    version: 1.0.0
  local@file:../x:
    resolution: {directory: ../x, type: directory}
  normal@1.0.0:
    resolution: {integrity: sha512-x}
snapshots:
  gitdep@https://codeload.github.com/u/r/tar.gz/abc: {}
  local@file:../x: {}
  normal@1.0.0: {}
"""))
        sources = {n.name: n.source for n in graph.nodes.values()}
        self.assertEqual(sources, {"gitdep": "git", "local": "file", "normal": "registry"})
        self.assertEqual(graph.unresolved, [])

    def test_ambiguous_peer_variants_resolve_deterministically_and_are_reported(self):
        graph = build_pnpm_dependency_graph(parse_pnpm_lockfile("""lockfileVersion: '9.0'
importers:
  .:
    dependencies:
      app: {specifier: ^1, version: 1.0.0}
packages:
  app@1.0.0: {}
  lib@1.0.0: {}
snapshots:
  app@1.0.0:
    dependencies:
      lib: 1.0.0
  lib@1.0.0(react@17.0.0): {}
  lib@1.0.0(react@18.0.0): {}
"""))
        self.assertEqual(graph.unresolved, [])
        self.assertEqual(len(graph.edges), 1)
        self.assertIn("PNPM_AMBIGUOUS_REFERENCE", [d.code for d in graph.diagnostics])

    def test_v9_project_with_no_dependencies_is_valid(self):
        graph = build_pnpm_dependency_graph(parse_pnpm_lockfile("lockfileVersion: '9.0'\nimporters:\n  .: {}\n"))
        self.assertEqual((len(graph.nodes), graph.unresolved), (0, []))

    def test_unrecognised_future_format_is_refused_when_references_do_not_match(self):
        raw = """lockfileVersion: '12.0'
importers:
  .:
    dependencies:
      a: {specifier: ^1, version: 1.0.0}
      b: {specifier: ^1, version: 1.0.0}
packages:
  something-else-entirely: {}
"""
        with self.assertRaisesRegex(ValueError, "could not be interpreted"):
            build_pnpm_dependency_graph(parse_pnpm_lockfile(raw))

    def test_yaml_aliases_are_rejected_not_expanded(self):
        bomb = "lockfileVersion: '9.0'\na: &a [x, x, x]\nb: &b [*a, *a, *a]\nc: [*b, *b, *b]\n"
        with self.assertRaisesRegex(ValueError, "anchors/aliases"):
            parse_pnpm_lockfile(bomb)

    def test_quoted_star_specifier_is_not_mistaken_for_an_alias(self):
        data = parse_pnpm_lockfile("lockfileVersion: '9.0'\nimporters:\n  .:\n    dependencies:\n      r: {specifier: '*', version: 1.0.0}\n")
        self.assertEqual(data["importers"]["."]["dependencies"]["r"]["specifier"], "*")


# --------------------------------------------------------------------------- npm graph
class NpmGraphTests(unittest.TestCase):
    def test_edge_dedupe_is_not_quadratic(self):
        n = 6000
        packages = {"": {"name": "r", "version": "1.0.0"}}
        for i in range(n):
            packages[f"node_modules/p{i}"] = {"version": "1.0.0", "dependencies": {f"p{(i * 7 + j) % n}": "^1" for j in range(1, 6)}}
        started = time.perf_counter()
        graph = build_dependency_graph(packages)
        elapsed = time.perf_counter() - started
        self.assertEqual(len(graph.nodes), n)
        self.assertEqual(len(graph.edges), n * 5)
        self.assertLess(elapsed, 3.0, f"took {elapsed:.1f}s; was ~19s with the O(E) duplicate check")

    def test_lockfile_v1_v2_v3_describe_the_same_packages(self):
        seen = {}
        for name in ("n1", "n2", "n3"):
            load = parse_lockfile(f"{name}/package-lock.json", (FIXTURES / name / "package-lock.json").read_text())
            self.assertTrue(load.ok, [d.message for d in load.diagnostics])
            seen[name] = {(n.name, n.version) for n in load.graph.nodes.values()}
        self.assertEqual(seen["n1"], seen["n2"])
        self.assertEqual(seen["n2"], seen["n3"])
        self.assertIn("LOCKFILE_LEGACY_FORMAT", [d.code for d in parse_lockfile("p/package-lock.json", (FIXTURES / "n1" / "package-lock.json").read_text()).diagnostics])

    def test_bundled_dependencies_are_not_reported_unresolved(self):
        graph = build_dependency_graph({
            "": {"name": "r", "version": "1.0.0"},
            "node_modules/host": {"version": "1.0.0", "dependencies": {"inner": "^1"}, "bundleDependencies": ["inner"]},
        })
        self.assertEqual(graph.unresolved, [])

    def test_missing_required_dependency_explains_why(self):
        graph = build_dependency_graph({"node_modules/a": {"version": "1.0.0", "dependencies": {"ghost": "^1"}}})
        self.assertEqual(graph.unresolved[0]["dependency"], "ghost")
        self.assertIn("no matching entry", graph.unresolved[0]["reason"])

    def test_workspace_link_resolves_from_the_real_directory_first(self):
        graph = build_dependency_graph({
            "": {"name": "root", "version": "1.0.0"},
            "node_modules/@ws/a": {"resolved": "packages/a", "link": True},
            "packages/a": {"name": "@ws/a", "version": "1.0.0", "dependencies": {"dep": "^1"}},
            "packages/a/node_modules/dep": {"version": "1.0.0"},     # nested install, only for @ws/a
            "node_modules/dep": {"version": "2.0.0"},                # hoisted copy for everyone else
        })
        edge = next(e for e in graph.edges if e.source == "node_modules/@ws/a")
        self.assertEqual(edge.target, "packages/a/node_modules/dep")

    def test_non_registry_sources_are_classified(self):
        graph = build_dependency_graph({
            "node_modules/g": {"version": "1.0.0", "resolved": "git+ssh://git@github.com/u/r.git#abc"},
            "node_modules/f": {"version": "1.0.0", "resolved": "file:../f"},
            "node_modules/r": {"version": "1.0.0", "resolved": "https://registry.npmjs.org/r/-/r-1.0.0.tgz"},
            "node_modules/w": {"resolved": "packages/w", "link": True},
            "packages/w": {"name": "w", "version": "1.0.0"},
        })
        self.assertEqual({n.name: n.source for n in graph.nodes.values()}, {"g": "git", "f": "file", "r": "registry", "w": "workspace"})

    def test_broken_lockfile_returns_a_diagnostic_instead_of_raising(self):
        load = parse_lockfile("package-lock.json", '{"name": "x", <<<<<<< HEAD')
        self.assertFalse(load.ok)
        self.assertEqual(load.diagnostics[0].code, "LOCKFILE_PARSE_ERROR")
        self.assertIn("line", load.diagnostics[0].message)
        self.assertTrue(load.diagnostics[0].hint)

    def test_unsupported_and_oversized_inputs_are_diagnosed(self):
        yarn = parse_lockfile("yarn.lock", "# yarn lockfile v1\n")
        self.assertEqual(yarn.diagnostics[0].code, "LOCKFILE_YARN_UNSUPPORTED")
        self.assertEqual(parse_lockfile("package-lock.json", "   ").diagnostics[0].code, "LOCKFILE_EMPTY_FILE")
        self.assertEqual(parse_lockfile("package-lock.json", "[]").diagnostics[0].code, "LOCKFILE_INVALID")


class ProjectDiscoveryTests(unittest.TestCase):
    def test_workspace_globs(self):
        patterns = ["packages/*", "apps/**", "!packages/legacy"]
        self.assertTrue(workspace_directory_matches("packages/a", patterns))
        self.assertTrue(workspace_directory_matches("apps/web/deep", patterns))
        self.assertFalse(workspace_directory_matches("packages/legacy", patterns))
        self.assertFalse(workspace_directory_matches("packages/a/b", patterns))        # '*' is one level
        self.assertFalse(workspace_directory_matches("x/packages/a", patterns))        # anchored at the root

    def test_package_manager_field_decides_between_competing_lockfiles(self):
        files = {"manifests": [{"path": "package.json", "sha": "m"}],
                 "lockfiles": [{"path": "package-lock.json", "sha": "a"}, {"path": "pnpm-lock.yaml", "sha": "b"}, {"path": "yarn.lock", "sha": "c"}]}
        for declared, expected in (("pnpm@9.1.0", "pnpm-lock.yaml"), ("npm@10.0.0", "package-lock.json"), (None, "package-lock.json")):
            manifest = {"name": "x", **({"packageManager": declared} if declared else {})}
            projects, _ = build_npm_projects(files, {"package.json": manifest})
            self.assertEqual(projects[0].lockfile["path"], expected, declared)

    def test_pnpm_is_preferred_over_yarn_when_nothing_else_is_declared(self):
        files = {"manifests": [{"path": "package.json", "sha": "m"}],
                 "lockfiles": [{"path": "yarn.lock", "sha": "c"}, {"path": "pnpm-lock.yaml", "sha": "b"}]}
        projects, _ = build_npm_projects(files, {"package.json": {"name": "x"}})
        self.assertEqual(projects[0].lockfile["path"], "pnpm-lock.yaml")

    def test_committed_node_modules_are_not_projects(self):
        tree = [{"type": "blob", "path": p, "sha": "s"} for p in
                ("package.json", "node_modules/left-pad/package.json", "web/node_modules/x/package-lock.json", "web/package.json")]
        found = discover_dependency_files(tree)
        self.assertEqual([m["path"] for m in found["manifests"]], ["package.json", "web/package.json"])
        self.assertEqual(found["lockfiles"], [])


# --------------------------------------------------------------------------- OSV
def osv_client(handler):
    client = OSVClient(transport=httpx.MockTransport(handler))
    client.backoff_base = 0
    return client


PKG = {"id": "lock::node_modules/demo", "name": "demo", "version": "1.0.0", "path": "node_modules/demo", "lockfile": "lock"}


class OSVResilienceTests(unittest.IsolatedAsyncioTestCase):
    async def test_transient_5xx_and_429_are_retried(self):
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(503)
            if calls["n"] == 2:
                return httpx.Response(429, headers={"Retry-After": "0"})
            return httpx.Response(200, json={"results": [{}]})
        client = osv_client(handler)
        self.assertEqual(await client.query_batch([{"package": {"name": "a", "ecosystem": "npm"}, "version": "1.0.0"}]), [{}])
        self.assertEqual(calls["n"], 3)
        await client.close()

    async def test_client_errors_are_not_retried(self):
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            return httpx.Response(400)
        client = osv_client(handler)
        with self.assertRaises(httpx.HTTPStatusError):
            await client.get_vulnerability("GHSA-x")
        self.assertEqual(calls["n"], 1)
        await client.close()

    async def test_paginated_results_are_followed(self):
        pages = []

        class Fake:
            async def query_batch(self, queries):
                pages.append(queries[0].get("page_token"))
                if queries[0].get("page_token") is None:
                    return [{"vulns": [{"id": "A-1"}], "next_page_token": "t2"}]
                return [{"vulns": [{"id": "A-2"}]}]
            async def get_vulnerability(self, vid):
                return {"id": vid, "database_specific": {"severity": "LOW"}}
            async def close(self):
                pass
        found = await scan_packages([PKG], client=Fake())
        self.assertEqual(sorted(v["id"] for v in found), ["A-1", "A-2"])
        self.assertEqual(pages, [None, "t2"])

    async def test_one_failed_advisory_does_not_discard_the_other_findings(self):
        class Fake:
            async def query_batch(self, queries):
                return [{"vulns": [{"id": "GOOD-1"}, {"id": "BAD-1"}]}]
            async def get_vulnerability(self, vid):
                if vid == "BAD-1":
                    raise httpx.ReadTimeout("slow")
                return {"id": vid, "summary": "ok", "database_specific": {"severity": "HIGH"}}
            async def close(self):
                pass
        report = ScanReport()
        found = await scan_packages([PKG], client=Fake(), report=report)
        self.assertEqual({v["id"] for v in found}, {"GOOD-1", "BAD-1"})
        self.assertTrue(next(v for v in found if v["id"] == "BAD-1")["details_unavailable"])
        self.assertFalse(report.complete)
        self.assertEqual(report.failed_advisories, ["BAD-1"])
        self.assertEqual(report.diagnostics[0].code, "OSV_ADVISORY_DETAIL_FAILED")

    async def test_partial_batch_failure_is_reported_total_failure_raises(self):
        packages = [{**PKG, "id": f"l::{i}", "name": f"p{i}", "version": "1.0.0"} for i in range(3)]

        class FlakyFake:
            async def query_batch(self, queries):
                if queries[0]["package"]["name"] == "p0":
                    raise httpx.ConnectError("down")
                return [{} for _ in queries]
            async def close(self):
                pass
        with patch.object(osv_module, "BATCH_SIZE", 1):
            report = ScanReport()
            await scan_packages(packages, client=FlakyFake(), report=report)
            self.assertEqual(report.failed_queries, 1)
            self.assertEqual(report.diagnostics[0].code, "OSV_QUERY_FAILED")

            class DownFake:
                async def query_batch(self, queries):
                    raise httpx.ConnectError("down")
                async def close(self):
                    pass
            with self.assertRaises(httpx.ConnectError):
                await scan_packages(packages, client=DownFake())

    async def test_withdrawn_advisories_are_not_reported(self):
        class Fake:
            async def query_batch(self, queries):
                return [{"vulns": [{"id": "GHSA-withdrawn"}]}]
            async def get_vulnerability(self, vid):
                return {"id": vid, "withdrawn": "2026-01-01T00:00:00Z"}
            async def close(self):
                pass
        report = ScanReport()
        self.assertEqual(await scan_packages([PKG], client=Fake(), report=report), [])
        self.assertEqual(report.withdrawn_advisories, ["GHSA-withdrawn"])

    async def test_only_registry_packages_are_queried(self):
        queried = []

        class Fake:
            async def query_batch(self, queries):
                queried.extend(q["package"]["name"] for q in queries)
                return [{} for _ in queries]
            async def close(self):
                pass
        packages = [
            {**PKG, "name": "real", "source": "registry"},
            {**PKG, "id": "2", "name": "from-git", "source": "git"},
            {**PKG, "id": "3", "name": "workspace-pkg", "source": "workspace", "is_link": True},
        ]
        report = ScanReport()
        await scan_packages(packages, client=Fake(), report=report)
        self.assertEqual(queried, ["real"])
        self.assertEqual(report.packages_skipped, 2)


class OSVNormalizationTests(unittest.TestCase):
    def test_cvss_v3_scores_match_the_first_specification_examples(self):
        for vector, score in {
            "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H": 9.8,
            "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H": 10.0,
            "CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H": 7.8,
            "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N": 6.1,
            "CVSS:3.0/AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:N/A:N": 3.7,
        }.items():
            self.assertEqual(cvss3_base_score(vector), score, vector)
        self.assertIsNone(cvss3_base_score("CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N"))
        self.assertIsNone(cvss3_base_score("garbage"))

    def test_severity_is_computed_from_a_vector_when_no_label_exists(self):
        item = normalize_vulnerability({"id": "X", "severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}]}, PKG)
        self.assertEqual((item["severity"], item["cvss_score"]), ("CRITICAL", 9.8))

    def test_malware_advisories_are_never_low_or_unknown(self):
        item = normalize_vulnerability({"id": "MAL-2026-1234", "summary": "Malicious code in demo"}, PKG)
        self.assertEqual(item["severity"], "CRITICAL")
        self.assertTrue(item["is_malware"])

    def test_fix_versions_follow_the_installed_release_line_and_sort_semantically(self):
        advisory = {"affected": [{"package": {"name": "demo", "ecosystem": "npm"}, "ranges": [{"type": "SEMVER", "events": [
            {"introduced": "0"}, {"fixed": "1.2.3"}]}, {"type": "SEMVER", "events": [{"introduced": "2.0.0"}, {"fixed": "2.0.1"}]}]}]}
        on = lambda v: normalize_vulnerability(advisory, {**PKG, "version": v})["fixed_versions"]
        self.assertEqual(on("2.0.0"), ["2.0.1"])           # not ['1.2.3', '2.0.1']: 1.2.3 would be a downgrade
        self.assertEqual(on("1.0.0"), ["1.2.3"])
        self.assertEqual(on("3.0.0"), [])
        multi = {"affected": [{"package": {"name": "demo", "ecosystem": "npm"}, "ranges": [{"type": "SEMVER", "events": [
            {"introduced": "0"}, {"fixed": "1.10.0"}]}]}, {"package": {"name": "demo", "ecosystem": "npm"}, "ranges": [
            {"type": "SEMVER", "events": [{"introduced": "0"}, {"fixed": "1.9.0"}]}]}]}
        self.assertEqual(normalize_vulnerability(multi, PKG)["fixed_versions"], ["1.9.0", "1.10.0"])

    def test_advisory_entries_for_other_packages_are_ignored(self):
        advisory = {"affected": [{"package": {"name": "other", "ecosystem": "npm"}, "ranges": [{"type": "SEMVER", "events": [{"introduced": "0"}, {"fixed": "9.9.9"}]}]}]}
        self.assertEqual(normalize_vulnerability(advisory, PKG)["fixed_versions"], [])

    def test_no_fix_available_when_installed_version_is_last_affected(self):
        advisory = {"affected": [{"package": {"name": "demo", "ecosystem": "npm"}, "ranges": [{"type": "SEMVER", "events": [{"introduced": "0"}, {"last_affected": "1.5.0"}]}]}]}
        self.assertEqual(normalize_vulnerability(advisory, PKG)["fixed_versions"], [])

    def test_findings_sort_by_severity_rank_not_alphabetically(self):
        self.assertLess(osv_module.SEVERITY_RANK["MEDIUM"], osv_module.SEVERITY_RANK["LOW"])


# --------------------------------------------------------------------------- GitHub client
def github(handler):
    client = GitHubClient(transport=httpx.MockTransport(handler))
    client.backoff_base = 0
    return client


class GitHubClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_error_statuses_map_to_stable_codes(self):
        cases = [
            (404, {}, "REPOSITORY_NOT_FOUND", 404),
            (401, {}, "GITHUB_AUTH_FAILED", 502),
            (409, {}, "REPOSITORY_EMPTY", 422),
            (403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(int(time.time()) + 3600)}, "GITHUB_RATE_LIMITED", 429),
            (403, {}, "GITHUB_FORBIDDEN", 403),
        ]
        for status, headers, code, http_status in cases:
            client = github(lambda request, s=status, h=headers: httpx.Response(s, headers=h, json={"message": "x"}))
            with self.assertRaises(AnalysisError) as ctx:
                await client.get_repository("https://github.com/acme/demo")
            self.assertEqual((ctx.exception.code, ctx.exception.status_code), (code, http_status), status)
            await client.close()

    async def test_rate_limit_error_tells_the_caller_when_to_retry(self):
        reset = int(time.time()) + 3600
        client = github(lambda r: httpx.Response(403, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(reset)}))
        with self.assertRaises(AnalysisError) as ctx:
            await client.get_repository("https://github.com/acme/demo")
        error = ctx.exception
        self.assertTrue(error.retryable)
        self.assertGreater(error.details["retry_in_seconds"], 3000)
        self.assertIn("GITHUB_TOKEN", error.hint or "") if not client.authenticated else None
        await client.close()

    async def test_5xx_is_retried_then_succeeds(self):
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            return httpx.Response(502) if calls["n"] < 3 else httpx.Response(200, json={"owner": {"login": "acme"}, "name": "demo"})
        client = github(handler)
        self.assertEqual((await client.get_repository("https://github.com/acme/demo"))["name"], "demo")
        self.assertEqual(calls["n"], 3)
        await client.close()

    async def test_timeouts_and_connection_errors_are_reported_clearly(self):
        def boom(exc):
            def handler(request):
                raise exc
            return handler
        for exc, code in ((httpx.ReadTimeout("t"), "GITHUB_TIMEOUT"), (httpx.ConnectError("c"), "GITHUB_UNREACHABLE")):
            client = github(boom(exc))
            with self.assertRaises(AnalysisError) as ctx:
                await client.get_repository("https://github.com/acme/demo")
            self.assertEqual(ctx.exception.code, code)
            self.assertTrue(ctx.exception.retryable)
            await client.close()

    async def test_invalid_urls_have_a_code_and_remain_value_errors(self):
        for url in ("https://example.com/a/b", "https://github.com/a/b/tree/main", "nonsense", ""):
            with self.assertRaises(ValueError) as ctx:
                GitHubClient.parse_repository_url(url)
            self.assertEqual(ctx.exception.code, "INVALID_REPOSITORY_URL")

    async def test_truncated_tree_falls_back_to_a_directory_walk_skipping_vendor_dirs(self):
        trees = {
            "root": {"tree": [
                {"path": "package.json", "type": "blob", "sha": "m0"},
                {"path": "apps", "type": "tree", "sha": "apps"},
                {"path": "node_modules", "type": "tree", "sha": "nm"},
            ]},
            "apps": {"tree": [{"path": "web", "type": "tree", "sha": "web"}]},
            "web": {"tree": [{"path": "package.json", "type": "blob", "sha": "m1"}, {"path": "pnpm-lock.yaml", "type": "blob", "sha": "l1"}]},
        }
        requested = []

        def handler(request):
            sha = request.url.path.rsplit("/", 1)[-1]
            requested.append(sha)
            if request.url.params.get("recursive"):
                return httpx.Response(200, json={"truncated": True, "tree": []})
            return httpx.Response(200, json=trees[sha])
        client = github(handler)
        tree = await client.get_repository_tree("acme", "big", "root")
        self.assertEqual(sorted(e["path"] for e in tree), ["apps/web/package.json", "apps/web/pnpm-lock.yaml", "package.json"])
        self.assertNotIn("nm", requested)
        self.assertEqual(client.diagnostics[0].code, "REPOSITORY_TREE_TRUNCATED")
        await client.close()

    async def test_blobs_are_cached_by_sha(self):
        import base64
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            return httpx.Response(200, json={"encoding": "base64", "content": base64.b64encode(b'{"a":1}').decode(), "size": 7})
        client = github(handler)
        self.assertEqual(await client.get_file_content("Acme", "cache-test", "sha-unique-1"), '{"a":1}')
        self.assertEqual(await client.get_file_content("acme", "cache-test", "sha-unique-1"), '{"a":1}')
        self.assertEqual(calls["n"], 1)
        await client.close()


if __name__ == "__main__":
    unittest.main()
