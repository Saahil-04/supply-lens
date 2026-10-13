import unittest
from unittest.mock import AsyncMock, patch

import httpx

from app import main
from app.analysis.store import analysis_store


class AnalysisResourceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        analysis_store._entries.clear()
        self.result = {
            "repository": {"name": "acme/demo", "url": "https://github.com/acme/demo", "default_branch": "main", "commit_sha": "abc123"},
            "summary": {"total_packages": 2, "vulnerabilities_found": 1, "risk_level": "high"},
            "projects": [{"path": "", "name": "demo", "manifest_path": "package.json", "lockfile_path": "package-lock.json"}],
            "packages": [
                {"id": "package-lock.json::node_modules/a", "name": "a", "version": "1.0.0", "path": "node_modules/a", "lockfile": "package-lock.json", "is_direct": True, "is_dev": False},
                {"id": "package-lock.json::node_modules/b", "name": "b", "version": "2.0.0", "path": "node_modules/b", "lockfile": "package-lock.json", "is_direct": False, "is_dev": True},
            ],
            "dependency_graph": {"nodes": [
                {"id": "package-lock.json::node_modules/a", "name": "a"},
                {"id": "package-lock.json::node_modules/b", "name": "b"},
            ], "edges": [{"source": "package-lock.json::node_modules/a", "target": "package-lock.json::node_modules/b", "dependency_type": "normal"}]},
            "vulnerabilities": [{"id": "GHSA-test", "severity": "HIGH", "package_name": "b", "summary": "test advisory", "details": "A long full advisory description", "references": ["https://example.test/advisory"], "package_id": "package-lock.json::node_modules/b", "installed_version": "2.0.0", "package_path": "node_modules/b", "lockfile": "package-lock.json", "aliases": ["CVE-2026-0001"], "modified": "2026-09-01T00:00:00Z", "published": "2026-08-01T00:00:00Z", "fixed_versions": ["2.1.0"], "cvss_score": 8.1}],
            "recommendations": [{"package_name": "b", "installed_version": "2.0.0", "fixed_versions": ["2.1.0"], "recommendation": "Upgrade"}],
            "sbom": {"bomFormat": "CycloneDX", "specVersion": "1.6", "components": []},
            "analysis_metadata": {"status": "partial", "vulnerability_analysis_status": "partial", "warnings": ["test warning"]},
        }
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        analysis_store._entries.clear()

    async def _create(self):
        with patch.object(main, "analyze_repository", new=AsyncMock(return_value=self.result)):
            response = await self.client.post("/analyze", json={"repository_url": "https://github.com/acme/demo"})
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertIn("analysis_id", body)
        self.assertNotIn("packages", body, "creation response must stay compact")
        return body["analysis_id"]

    async def test_create_summary_and_paginated_resources(self):
        analysis_id = await self._create()
        summary = await self.client.get(f"/analyses/{analysis_id}")
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json()["summary"]["total_packages"], 2)

        packages = await self.client.get(f"/analyses/{analysis_id}/packages", params={"direct": "true", "limit": 1})
        self.assertEqual(packages.status_code, 200)
        self.assertEqual(len(packages.json()["items"]), 1)
        self.assertEqual(packages.json()["pagination"]["total"], 1)

        vulns = await self.client.get(f"/analyses/{analysis_id}/vulnerabilities", params={"severity": "HIGH", "has_fix": "true"})
        self.assertEqual(vulns.status_code, 200)
        finding = vulns.json()["items"][0]
        self.assertEqual(finding["id"], "GHSA-test")
        self.assertIn("finding_id", finding)
        self.assertIn("detail", finding["links"])
        self.assertNotIn("details", finding)
        self.assertNotIn("references", finding)

        detail = await self.client.get(finding["links"]["detail"])
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["details"], "A long full advisory description")
        self.assertEqual(detail.json()["references"], ["https://example.test/advisory"])

        recs = await self.client.get(f"/analyses/{analysis_id}/recommendations")
        self.assertEqual(recs.json()["pagination"]["total"], 1)

    async def test_graph_neighborhood_and_sbom_download(self):
        analysis_id = await self._create()
        package_id = "package-lock.json::node_modules/a"
        graph = await self.client.get(f"/analyses/{analysis_id}/graph", params={"package_id": package_id, "depth": 1, "direction": "out"})
        self.assertEqual(graph.status_code, 200)
        self.assertEqual(len(graph.json()["nodes"]), 2)
        self.assertEqual(len(graph.json()["edges"]), 1)

        sbom = await self.client.get(f"/analyses/{analysis_id}/sbom")
        self.assertEqual(sbom.status_code, 200)
        self.assertEqual(sbom.json()["bomFormat"], "CycloneDX")
        self.assertIn("attachment; filename=", sbom.headers["content-disposition"])

    async def test_missing_or_expired_analysis_is_404(self):
        response = await self.client.get("/analyses/not-a-real-id")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
