import unittest

from evaluation import evaluate as ev


def row(status, **kw):
    base = {"repo": "a/b", "advisory": "G1", "package": "p", "is_direct": True, "is_dev": False, "reachability": status,
            "priority": 1, "baseline_priority": 1, "manual_label": ""}
    return {**base, **kw}


class EvaluationTests(unittest.TestCase):
    def test_summary_measures_the_p1_reduction(self):
        rows = [row("imported"), row("not_imported", priority=2), row("dev_only", priority=2, is_dev=True), row("unknown", is_direct=False)]
        s = ev.summarize(rows)
        self.assertEqual((s["baseline_p1"], s["context_p1"], s["p1_reduction_pct"]), (4, 2, 50.0))
        self.assertEqual((s["downgraded_findings"], s["reachability_known_pct"]), (2, 75.0))
        self.assertEqual(ev.summarize([]), {"findings": 0})

    def test_flatten_handles_missing_reachability(self):
        out = ev.flatten({"repository": {"commit_sha": "abcdef1234567"}, "vulnerabilities": [{"id": "X", "package_name": "p"}]}, "o/r")
        self.assertEqual((out[0]["reachability"], out[0]["commit"]), ("unknown", "abcdef1234"))

    def test_sample_is_stratified_and_reproducible(self):
        rows = [row("not_imported") for _ in range(30)] + [row("imported") for _ in range(3)]
        a, b = ev.sample_for_validation(rows, per_status=10), ev.sample_for_validation(rows, per_status=10)
        self.assertEqual(a, b)
        self.assertEqual(sum(r["reachability"] == "not_imported" for r in a), 10)
        self.assertEqual(sum(r["reachability"] == "imported" for r in a), 3)

    def test_wilson_interval_is_wide_for_small_samples(self):
        low, high = ev.wilson(9, 10)
        self.assertTrue(0.55 < low < 0.6 and 0.97 < high < 1.0)
        self.assertEqual(ev.wilson(0, 0), (0.0, 0.0))

    def test_scoring_flags_dangerous_errors(self):
        labelled = [row("not_imported", manual_label="not_used"), row("not_imported", manual_label="used", package="bad"),
                    row("imported", manual_label="used"), row("imported", manual_label="unsure"), row("dev_only", manual_label="not_used")]
        out = ev.score_validation(labelled)
        self.assertEqual((out["claims_not_used"]["n"], out["claims_not_used"]["correct"]), (3, 2))
        self.assertEqual((out["claims_used"]["n"], out["claims_used"]["precision"]), (1, 1.0))
        self.assertEqual(out["dangerous_errors"]["count"], 1)
        self.assertEqual(out["unsure_excluded"], 1)
