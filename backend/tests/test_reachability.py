import json
import unittest
from unittest.mock import AsyncMock, patch

from app.analysis import reachability as r
from app.analysis import service as service_module
from tests.test_service_hardening import fake_github


class ImportExtractionTests(unittest.TestCase):
    def test_static_dynamic_and_commonjs_imports(self):
        src = """
        import React from 'react';
        import { a } from "lodash/fp";
        import '@scope/side-effect';
        export * from 'rxjs/operators';
        const x = require('express');
        const y = await import('chalk');
        const z = require.resolve('resolve-me');
        """
        self.assertEqual(r.extract_imports(src), {"react", "lodash", "@scope/side-effect", "rxjs", "express", "chalk", "resolve-me"})

    def test_relative_alias_and_builtin_prefix_are_not_packages(self):
        src = "import a from './a'; import b from '../b'; import c from '@/components/c'; import d from 'node:fs'; import e from '#internal'; import f from '/abs'"
        self.assertEqual(r.extract_imports(src), set())

    def test_comments_and_type_only_imports_do_not_count(self):
        src = """
        // import evil from 'commented-line'
        /* const x = require('commented-block') */
        import type { T } from 'types-only';
        export type { U } from 'also-types-only';
        import real from 'real-dep';
        const url = "http://example.com/a"; require('after-url');
        """
        self.assertEqual(r.extract_imports(src), {"real-dep", "after-url"})

    def test_package_name_edge_cases(self):
        self.assertEqual(r.package_name("@babel/core/lib/x"), "@babel/core")
        self.assertIsNone(r.package_name("@/x"))
        self.assertIsNone(r.package_name(""))

    def test_file_classification(self):
        self.assertEqual(r.classify_file("src/app.ts"), "production")
        self.assertEqual(r.classify_file("src/app.test.ts"), "test")
        self.assertEqual(r.classify_file("__tests__/a.js"), "test")
        self.assertEqual(r.classify_file("webpack.config.js"), "tooling")
        self.assertEqual(r.classify_file("scripts/build.js"), "tooling")

    def test_script_tokens(self):
        self.assertTrue({"next", "eslint"} <= r.script_tokens({"scripts": {"dev": "next dev", "lint": "eslint . --fix"}}))


def usage(imports, total=3, scanned=3):
    return r.ProjectUsage(imports=imports, files_total=total, files_scanned=scanned)


class AssessmentTests(unittest.TestCase):
    def test_direct_import_in_production_code_is_high_confidence(self):
        out = r.assess([("", [("lodash", True)])], {"": usage({"lodash": {"production": ["src/a.js"]}})}, {}, False)
        self.assertEqual((out["status"], out["confidence"], out["files"]), ("imported", "high", ["src/a.js"]))

    def test_transitive_package_inherits_from_an_imported_parent(self):
        out = r.assess([("", [("express", False)])], {"": usage({"express": {"production": ["server.js"]}})}, {}, False)
        self.assertEqual((out["status"], out["via"]), ("transitive_of_imported", "express"))

    def test_only_tests_or_scripts(self):
        self.assertEqual(r.assess([("", [("jest", True)])], {"": usage({"jest": {"test": ["a.test.js"]}})}, {}, False)["status"], "tests_or_tooling_only")
        self.assertEqual(r.assess([("", [("next", True)])], {"": usage({})}, {"": {"next"}}, False)["status"], "tests_or_tooling_only")

    def test_not_imported_requires_a_complete_scan(self):
        self.assertEqual(r.assess([("", [("x", True)])], {"": usage({}, total=3, scanned=3)}, {}, False)["status"], "not_imported")
        # budget truncated the scan: absence of evidence must not become "safe"
        self.assertEqual(r.assess([("", [("x", True)])], {"": usage({}, total=900, scanned=600)}, {}, False)["status"], "unknown")
        self.assertEqual(r.assess([("", [("x", True)])], {}, {}, False)["status"], "unknown")
        self.assertEqual(r.assess([], {}, {}, False)["status"], "unknown")

    def test_one_incomplete_project_prevents_a_not_imported_claim(self):
        out = r.assess([("a", [("x", True)]), ("b", [("x", True)])], {"a": usage({}), "b": usage({}, total=9, scanned=1)}, {}, False)
        self.assertEqual(out["status"], "unknown")

    def test_any_project_importing_wins(self):
        out = r.assess([("a", [("x", True)]), ("b", [("x", True)])], {"a": usage({}), "b": usage({"x": {"production": ["b.js"]}})}, {}, False)
        self.assertEqual(out["status"], "imported")

    def test_dev_dependency_is_dev_only_unless_it_is_imported_in_production(self):
        self.assertEqual(r.assess([("", [("t", True)])], {"": usage({})}, {}, True)["status"], "dev_only")
        self.assertEqual(r.assess([("", [("t", True)])], {"": usage({"t": {"production": ["a.js"]}})}, {}, True)["status"], "imported")

    def test_dev_flag_does_not_hide_a_bundled_parent(self):
        # the vulnerable package is only a transitive dependency of a dev-listed library that production code imports
        out = r.assess([("", [("react", False)])], {"": usage({"react": {"production": ["src/main.tsx"]}})}, {}, True)
        self.assertEqual((out["status"], out["via"]), ("transitive_of_imported", "react"))


class PriorityTests(unittest.TestCase):
    def test_downgrade_only_when_demonstrably_not_shipped(self):
        self.assertEqual(r.prioritize("HIGH", False, "imported")["priority"], 1)
        self.assertEqual(r.prioritize("HIGH", False, "not_imported")["priority"], 2)
        self.assertEqual(r.prioritize("HIGH", False, "dev_only")["priority"], 2)
        self.assertEqual(r.prioritize("LOW", False, "dev_only")["priority"], 4)
        self.assertEqual(r.prioritize("HIGH", False, "unknown")["priority"], 1)           # unknown never lowers
        self.assertEqual(r.prioritize("MEDIUM", False, "transitive_of_imported")["priority"], 2)

    def test_malware_is_always_p1_and_baseline_is_reported(self):
        out = r.prioritize("LOW", True, "dev_only")
        self.assertEqual((out["priority"], out["baseline_priority"]), (1, 1))
        out = r.prioritize("CRITICAL", False, "not_imported")
        self.assertEqual((out["priority"], out["baseline_priority"]), (2, 1))
        self.assertIn("lowered", out["priority_reason"])


class SelectionTests(unittest.TestCase):
    def test_production_first_nested_projects_and_exclusions(self):
        tree = [{"type": "blob", "path": p, "sha": p, "size": 10} for p in (
            "src/a.ts", "src/a.test.ts", "node_modules/x/i.js", "dist/o.js", "types/t.d.ts", "web/src/w.ts", "README.md")]
        selected, totals = r.select_source_files(tree, {"", "web"}, ["", "web"], max_files=10)
        self.assertEqual([e["path"] for _, e in selected], ["web/src/w.ts", "src/a.ts", "src/a.test.ts"])   # per project, small first; production first inside
        self.assertEqual(totals, {"": 2, "web": 1})            # web/ files belong to the nested project only
        selected, _ = r.select_source_files(tree, {""}, ["", "web"], max_files=1)
        self.assertEqual([e["path"] for _, e in selected], ["src/a.ts"])


class ServiceReachabilityTests(unittest.IsolatedAsyncioTestCase):
    async def run_case(self, sources, finding_pkg="leaf", max_files=600, manifest=None, include=True):
        tree = [{"type": "blob", "path": "package.json", "sha": "m"}, {"type": "blob", "path": "package-lock.json", "sha": "l"}]
        contents = {"m": json.dumps(manifest or {"dependencies": {"top": "^1"}, "devDependencies": {"jest": "^29"}}),
                    "l": json.dumps({"lockfileVersion": 3, "packages": {
                        "": {}, "node_modules/top": {"version": "1.0.0", "dependencies": {"leaf": "^1"}},
                        "node_modules/leaf": {"version": "1.0.0"},
                        "node_modules/jest": {"version": "29.0.0", "dev": True}}})}
        for path, text in sources.items():
            tree.append({"type": "blob", "path": path, "sha": path, "size": len(text)})
            contents[path] = text
        def finding(name, sev="HIGH"):
            return {"id": f"GHSA-{name}", "package_id": f"package-lock.json::node_modules/{name}", "package_name": name, "installed_version": "1.0.0",
                    "package_path": f"node_modules/{name}", "lockfile": "package-lock.json", "severity": sev, "fixed_versions": ["2.0.0"]}
        scan = AsyncMock(return_value=[finding("leaf"), finding("top"), finding("jest", "MEDIUM")])
        with patch.object(service_module, "GitHubClient", return_value=fake_github(tree, contents)), \
             patch.object(service_module, "scan_packages", new=scan), patch.object(service_module, "DEFAULT_MAX_FILES", max_files):
            return await service_module.analyze_repository("https://github.com/acme/demo", include_reachability=include)

    def statuses(self, result):
        return {v["package_name"]: (v["reachability"]["status"], v["priority"], v["baseline_priority"]) for v in result["vulnerabilities"]}

    async def test_end_to_end_statuses_and_priorities(self):
        result = await self.run_case({"src/index.js": "import top from 'top';", "src/a.test.js": "require('jest')"})
        self.assertEqual(self.statuses(result), {"top": ("imported", 1, 1), "leaf": ("transitive_of_imported", 1, 1), "jest": ("dev_only", 3, 2)})
        self.assertEqual(result["summary"]["reachability"], {"imported": 1, "transitive_of_imported": 1, "dev_only": 1})
        self.assertEqual(result["summary"]["priority_counts"], {"P1": 2, "P2": 0, "P3": 1, "P4": 0})
        self.assertEqual(result["summary"]["baseline_priority_counts"], {"P1": 2, "P2": 1, "P3": 0, "P4": 0})
        top = next(v for v in result["vulnerabilities"] if v["package_name"] == "top")
        self.assertEqual(top["reachability"]["files"], ["src/index.js"])
        self.assertTrue(result["analysis_metadata"]["reachability"]["enabled"])

    async def test_package_never_imported_is_not_imported_and_downgraded(self):
        result = await self.run_case({"src/index.js": "console.log('hi')"})
        self.assertEqual(self.statuses(result)["top"], ("not_imported", 2, 1))
        self.assertEqual(self.statuses(result)["leaf"], ("not_imported", 2, 1))

    async def test_truncated_scan_yields_unknown_with_a_diagnostic(self):
        result = await self.run_case({f"src/f{i}.js": "x" for i in range(5)}, max_files=2)
        self.assertEqual(self.statuses(result)["top"][0], "unknown")
        self.assertEqual(self.statuses(result)["top"][1], 1)            # unknown never lowers priority
        self.assertIn("REACHABILITY_TRUNCATED", [d["code"] for d in result["analysis_metadata"]["diagnostics"]])

    async def test_no_source_files_is_unknown_not_not_imported(self):
        result = await self.run_case({})
        self.assertEqual(self.statuses(result)["top"][0], "unknown")
        self.assertIn("REACHABILITY_NO_SOURCE", [d["code"] for d in result["analysis_metadata"]["diagnostics"]])

    async def test_npm_script_usage_counts_as_tooling(self):
        result = await self.run_case({"src/index.js": "1"}, manifest={"dependencies": {"top": "^1"}, "scripts": {"start": "top serve"}})
        self.assertEqual(self.statuses(result)["top"][0], "tests_or_tooling_only")

    async def test_can_be_switched_off(self):
        result = await self.run_case({"src/index.js": "import top from 'top'"}, include=False)
        self.assertEqual(self.statuses(result)["top"], ("unknown", 1, 1))
        self.assertFalse(result["analysis_metadata"]["reachability"]["enabled"])

    async def test_download_failures_prevent_not_imported(self):
        tree = [{"type": "blob", "path": "package.json", "sha": "m"}, {"type": "blob", "path": "package-lock.json", "sha": "l"},
                {"type": "blob", "path": "src/a.js", "sha": "a", "size": 5}]
        lock = {"lockfileVersion": 3, "packages": {"": {}, "node_modules/top": {"version": "1.0.0"}}}
        contents = {"m": json.dumps({"dependencies": {"top": "1"}}), "l": json.dumps(lock), "a": RuntimeError("boom")}
        finding = {"id": "G", "package_id": "package-lock.json::node_modules/top", "package_name": "top", "installed_version": "1.0.0",
                   "package_path": "node_modules/top", "lockfile": "package-lock.json", "severity": "HIGH", "fixed_versions": []}
        with patch.object(service_module, "GitHubClient", return_value=fake_github(tree, contents)), \
             patch.object(service_module, "scan_packages", new=AsyncMock(return_value=[finding])):
            result = await service_module.analyze_repository("https://github.com/acme/demo")
        self.assertEqual(result["vulnerabilities"][0]["reachability"]["status"], "unknown")
        self.assertIn("REACHABILITY_FILES_FAILED", [d["code"] for d in result["analysis_metadata"]["diagnostics"]])


if __name__ == "__main__":
    unittest.main()


class FairBudgetTests(unittest.TestCase):
    def test_large_project_cannot_starve_the_others(self):
        tree = [{"path": f"a/src/f{i}.ts", "type": "blob", "sha": f"a{i}"} for i in range(50)]
        tree += [{"path": "z/src/only.ts", "type": "blob", "sha": "z0"}, {"path": "m/src/x.ts", "type": "blob", "sha": "m0"}]
        selected, totals = r.select_source_files(tree, {"a", "m", "z"}, ["a", "m", "z"], max_files=10)
        roots = [root for root, _ in selected]
        self.assertEqual((roots.count("z"), roots.count("m")), (1, 1))     # small projects scanned completely
        self.assertEqual(roots.count("a"), 8)                               # the rest goes to the big one
        self.assertEqual(len(selected), 10)
        self.assertEqual(totals["a"], 50)

    def test_unknown_carries_a_reason(self):
        usage = {"web": r.ProjectUsage(files_total=5, files_scanned=2)}
        partial = r.assess([("web", [("lodash", True)])], usage, {}, False)
        self.assertEqual((partial["status"], partial["reason"]), ("unknown", "scan_incomplete"))
        missing = r.assess([("other", [("lodash", True)])], usage, {}, False)
        self.assertEqual(missing["reason"], "no_source_files")
        starved = r.assess([("web", [("lodash", True)])], {"web": r.ProjectUsage(files_total=5)}, {}, False)
        self.assertEqual(starved["reason"], "not_scanned_budget")
        self.assertEqual(r.assess([], {}, {}, False)["reason"], "no_direct_owner")


class ToolingClaimNeedsFullProductionScan(unittest.TestCase):
    def test_script_token_alone_does_not_downgrade_a_partly_scanned_project(self):
        partial = {"web": r.ProjectUsage(files_total=9, files_scanned=3)}
        out = r.assess([("web", [("vite", True)])], partial, {"web": {"vite"}}, False)
        self.assertEqual((out["status"], out["reason"]), ("unknown", "scan_incomplete"))

    def test_tooling_claim_allowed_once_production_files_were_all_read(self):
        done = {"web": r.ProjectUsage(files_total=9, files_scanned=3, non_production_scanned=1)}
        self.assertEqual(r.assess([("web", [("vite", True)])], done, {"web": {"vite"}}, False)["status"], "tests_or_tooling_only")
        failed = {"web": r.ProjectUsage(files_total=9, files_scanned=3, files_failed=1, non_production_scanned=1)}
        self.assertEqual(r.assess([("web", [("vite", True)])], failed, {"web": {"vite"}}, False)["status"], "unknown")
