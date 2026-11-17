import copy
import json
import unittest
from pathlib import Path

from lab9.eval import load_spec
from lab9.gate import integrity_check


class TestM7Integrity(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.base = json.loads(
            Path("reports/baseline_v2_m6.json").read_text(
                encoding="utf-8"
            )
        )
        cls.spec = load_spec(
            Path("config/metric_spec_v2.yaml")
        )

    def test_valid_report(self):
        problems = integrity_check(
            self.base, self.base, self.spec
        )
        self.assertEqual(problems, [])

    def test_nan_metric(self):
        pr = copy.deepcopy(self.base)
        pr["metrics"]["pass_rate"] = float("nan")
        self.assertTrue(
            integrity_check(pr, self.base, self.spec)
        )

    def test_missing_row(self):
        pr = copy.deepcopy(self.base)
        pr["rows"].pop()
        self.assertTrue(
            integrity_check(pr, self.base, self.spec)
        )

    def test_duplicate_row(self):
        pr = copy.deepcopy(self.base)
        pr["rows"][1] = copy.deepcopy(pr["rows"][0])
        self.assertTrue(
            integrity_check(pr, self.base, self.spec)
        )

    def test_changed_seed(self):
        pr = copy.deepcopy(self.base)
        pr["rows"][0]["seed"] = 999
        self.assertTrue(
            integrity_check(pr, self.base, self.spec)
        )

    def test_changed_slice(self):
        pr = copy.deepcopy(self.base)
        pr["rows"][0]["slices"] = []
        self.assertTrue(
            integrity_check(pr, self.base, self.spec)
        )

    def test_evaluator_failure(self):
        pr = copy.deepcopy(self.base)
        pr["evaluator_failures"] = ["grader crashed"]
        self.assertTrue(
            integrity_check(pr, self.base, self.spec)
        )

    def test_null_grader(self):
        pr = copy.deepcopy(self.base)
        pr["rows"][0]["refund_amount_correct"] = None
        self.assertTrue(
            integrity_check(pr, self.base, self.spec)
        )

    def test_loosened_threshold(self):
        new_spec = copy.deepcopy(self.spec)

        for metric in new_spec["metrics"]:
            if metric["id"] == "pass_rate":
                metric["threshold"]["min"] = 0.50

        problems = integrity_check(
            self.base, self.base,
            new_spec, self.spec
        )
        self.assertTrue(
            any("loosened min" in p for p in problems)
        )

    def test_removed_blocking(self):
        new_spec = copy.deepcopy(self.spec)

        for metric in new_spec["metrics"]:
            if metric["id"] == "pass_hat_5":
                metric["blocking"] = False

        problems = integrity_check(
            self.base, self.base,
            new_spec, self.spec
        )
        self.assertTrue(
            any("removed blocking" in p for p in problems)
        )

    def test_removed_slice(self):
        new_spec = copy.deepcopy(self.spec)
        new_spec["slices"] = [
            s for s in new_spec["slices"]
            if s["name"] != "denial"
        ]

        problems = integrity_check(
            self.base, self.base,
            new_spec, self.spec
        )
        self.assertTrue(
            any("removed slice" in p for p in problems)
        )


if __name__ == "__main__":
    unittest.main()
