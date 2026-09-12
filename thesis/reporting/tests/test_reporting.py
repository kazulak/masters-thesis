"""Regression checks for scientific summaries; all writes use temporary storage."""
import copy
import csv
import importlib.util
import io
import json
import math
from pathlib import Path
import statistics
import tempfile
import unittest
from unittest.mock import patch


REPORTING = Path(__file__).resolve().parents[1]
ROOT = REPORTING.parents[1]
RESULTS = ROOT / "thesis/implementation/thesis_results/unified_final_v4"
READOUT = RESULTS / "readout"


def module(name):
    spec = importlib.util.spec_from_file_location(name, REPORTING / "tables" / f"{name}.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def csv_rows(path):
    with path.open(newline="") as source:
        return list(csv.DictReader(source))


def replace_csv(path, rows):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    original = Path.open

    def opened(target, *args, **kwargs):
        return io.StringIO(stream.getvalue()) if target == path else original(target, *args, **kwargs)

    return patch.object(Path, "open", opened)


def replace_json(path, value):
    original = Path.read_text

    def read(target, *args, **kwargs):
        return json.dumps(value) if target == path else original(target, *args, **kwargs)

    return patch.object(Path, "read_text", read)


class CorrectnessTable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = module("table02_correctness")
        cls.observations = csv_rows(READOUT / "observations.csv")

    def test_primary_extrema_include_calibration_and_final(self):
        for row in self.table.build_rows():
            samples = [s for s in self.observations if s["issued"] == "True"
                       and s["warmup"] == "False" and s["backend"] == "upmem"
                       and s["case_id"].split("_")[0] == row["family"]]
            self.assertEqual(len({s["slot_id"] for s in samples}), 350)
            f32 = [json.loads(s["validation"]) for s in samples
                   if json.loads(s["arm"])["policy"] == self.table.FLOAT]
            int8 = [json.loads(s["validation"]) for s in samples
                    if json.loads(s["arm"])["policy"] == self.table.INT8]
            self.assertEqual((row["f32_count"], row["int8_count"]), (245, 105))
            self.assertEqual(row["f32_passes"], 245)
            self.assertEqual(row["int8_replay_passes"], 105)
            self.assertEqual(row["f32_max_relative_l2"], max(v["relative_l2"] for v in f32))
            self.assertEqual(row["int8_max_relative_l2"], max(v["relative_l2"] for v in int8))
            self.assertEqual(row["int8_min_fidelity"], min(v["fidelity_normalized"] for v in int8))

    def test_warmups_do_not_change_extrema(self):
        expected = self.table.build_rows()
        observations = copy.deepcopy(self.observations)
        for sample in observations:
            if sample["warmup"] == "True" and sample["validation"]:
                value = json.loads(sample["validation"])
                value["relative_l2"], value["fidelity_normalized"] = 999, 0
                sample["validation"] = json.dumps(value)
        with replace_csv(READOUT / "observations.csv", observations):
            self.assertEqual(self.table.build_rows(), expected)

    def test_identical_physical_slots_are_counted_once(self):
        expected = self.table.build_rows()
        with replace_csv(READOUT / "observations.csv", self.observations + [self.observations[0]]):
            self.assertEqual(self.table.build_rows(), expected)

    def test_conflicting_physical_slot_is_rejected(self):
        conflict = dict(self.observations[0], status="failed")
        with replace_csv(READOUT / "observations.csv", self.observations + [conflict]):
            with self.assertRaises(ValueError):
                self.table.build_rows()

    def test_int8_error_is_disclosed_without_a_posthoc_threshold(self):
        observations = copy.deepcopy(self.observations)
        sample = next(s for s in observations if s["case_id"] == "edc_n17"
                      and s["warmup"] == "False" and s["backend"] == "upmem"
                      and json.loads(s["arm"])["policy"] == self.table.INT8)
        value = json.loads(sample["validation"])
        value["relative_l2"], value["fidelity_normalized"] = 0.25, 0.8
        sample["validation"] = json.dumps(value)
        sample["accuracy_qualified"] = "False"
        with replace_csv(READOUT / "observations.csv", observations):
            row = next(r for r in self.table.build_rows() if r["family"] == "edc")
        self.assertEqual(row["int8_max_relative_l2"], 0.25)
        self.assertEqual(row["int8_min_fidelity"], 0.8)
        self.assertEqual(row["int8_replay_passes"], 105)
        self.assertEqual(row["int8_status"], "Approximate")

    def test_missing_primary_observation_is_not_silently_dropped(self):
        observations = list(self.observations)
        observations.pop(next(i for i, s in enumerate(observations)
                              if s["case_id"] == "bb84_n18" and s["warmup"] == "False"
                              and s["backend"] == "upmem"))
        with replace_csv(READOUT / "observations.csv", observations):
            with self.assertRaises(ValueError):
                self.table.build_rows()


class MainTableDefinitions(unittest.TestCase):
    def test_edc_uses_data_and_syndrome_wires(self):
        table = module("table01_workloads")
        row = next(r for r in table.build_rows() if r["family"] == "edc")
        self.assertEqual((row["calibration_case"], row["calibration_n"]), ("edc_n17", 17))
        manifest = json.loads((RESULTS / "manifest/manifest.json").read_text())
        next(c for c in manifest["cases"] if c["case_id"] == "edc_n17")["n"] = 18
        with replace_json(RESULTS / "manifest/manifest.json", manifest):
            with self.assertRaises(ValueError):
                table.build_rows()

    def test_resources_come_from_frozen_policy_specific_winners(self):
        selections = json.loads((RESULTS / "selection.json").read_text())["selections"]
        lookup = {(s["family"], s["policy"]): s["selected"] for s in selections}
        for row in module("table03_resources").build_rows():
            for short, policy in (("f32", "split_complex_float32_v1"), ("int8", "complex_int8_shared_scale_v1")):
                chosen = lookup[row["family"], policy]
                self.assertEqual((row[f"{short}_dpus"], row[f"{short}_tasklets"]),
                                 (chosen["dpus"], chosen["tasklets"]))

    def test_path_table_preserves_stored_ratio_orientation_and_intervals(self):
        path_results = ROOT / "thesis/implementation/thesis_results/upmem_cost_guided_path_v1"
        source = {(r["contrast"], r["group"]): r for r in csv_rows(path_results / "readout/aggregates.csv")
                  if r["metric"] == "session_inclusive_s"}
        rows = module("table04_path_selection").build_rows()
        self.assertEqual([r["contrast"] for r in rows], ["G/F", "F/R", "R/U", "G/U"])
        for row in rows:
            for group in ("1dpu_t8", "4dpu_t8", "all"):
                stored = source[row["contrast"], group]
                for key, field in (("ratio", "family_balanced_geometric_ratio"),
                                   ("low", "paired_bootstrap_low"), ("high", "paired_bootstrap_high")):
                    self.assertEqual(row[group][key], float(stored[field]))
        primary = next(r for r in rows if r["contrast"] == "R/U")["all"]
        self.assertLess(primary["low"], 1)
        self.assertGreater(primary["high"], 1)

    def test_cpu_summary_is_geometric_over_matched_widths_and_families(self):
        table = module("table05_cpu_comparison")
        source = csv_rows(READOUT / "W.csv")
        timings = {(r["case_id"], r["role"]): float(r["median_job_to_state_cached_path_s"]) for r in source}
        rows = table.build_rows()
        self.assertEqual(len(rows), 14)
        for row in rows:
            if row["family"] == "overall":
                continue
            cases = [c for c, role in timings if role == row["policy"] and c.startswith(row["family"] + "_n")]
            self.assertEqual(len(cases), 7)
            for cpu, actual in row["ratios"].items():
                expected = math.exp(statistics.mean(math.log(timings[c, row["policy"]] / timings[c, cpu]) for c in cases))
                self.assertAlmostEqual(actual, expected, places=12)
        for row in (r for r in rows if r["family"] == "overall"):
            for cpu, actual in row["ratios"].items():
                families = [r["ratios"][cpu] for r in rows if r["family"] != "overall" and r["policy"] == row["policy"]]
                self.assertEqual(len(families), 6)
                self.assertAlmostEqual(actual, math.exp(statistics.mean(map(math.log, families))), places=12)

    def test_cpu_only_endpoint_does_not_enter_common_width_summary(self):
        table = module("table05_cpu_comparison")
        expected = table.build_rows()
        rows = csv_rows(READOUT / "W.csv")
        for row in rows:
            if row["case_id"] == "bb84_n26":
                row["median_job_to_state_cached_path_s"] = str(100 * float(row["median_job_to_state_cached_path_s"]))
        with replace_csv(READOUT / "W.csv", rows):
            self.assertEqual(table.build_rows(), expected)


class AppendixIntegrity(unittest.TestCase):
    def test_no_path_execution_cannot_be_reported_as_zero(self):
        table = module("app_table02_cold_cost")
        rows = csv_rows(READOUT / "cold_cost.csv")
        next(r for r in rows if r["path_status"] == "no_selected_R_path")["median_cached_s"] = "0"
        with tempfile.TemporaryDirectory() as tmp, patch.object(table, "TABLE_OUTPUT", Path(tmp)):
            with replace_csv(READOUT / "cold_cost.csv", rows):
                with self.assertRaises((ValueError, AssertionError)):
                    table.build()
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_archive_count_must_match_retention(self):
        table = module("app_table03_accounting")
        accounting = json.loads((READOUT / "accounting.json").read_text())
        accounting["archive_files_count"] -= 1
        with tempfile.TemporaryDirectory() as tmp, patch.object(table, "TABLE_OUTPUT", Path(tmp)):
            with replace_json(READOUT / "accounting.json", accounting):
                with self.assertRaises((ValueError, AssertionError)):
                    table.build()
            self.assertEqual(list(Path(tmp).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
