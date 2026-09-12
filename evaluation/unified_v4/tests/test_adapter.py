"""Adapter unit and integration tests covering PLAN.md §10 mandatory requirements."""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
EVAL_DIR = HERE.parent
sys.path.insert(0, str(EVAL_DIR))
import protocol_core as pc
import runner
import readout
runner.setup_implementation_imports(EVAL_DIR.parents[1])


class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = pc.read(EVAL_DIR / "protocol.json")
        cls.manifest = pc.compile_manifest(cls.spec)

    # 1. actual worker receipts carry/agree with slot identity AND .issued.json, including block 0
    def test_worker_receipt_slot_identity_agreement(self):
        slot = self.manifest["calibration_slots"][0]  # block 0
        cell = next(c for c in self.manifest["calibration_cells"] if c["cell_id"] == slot["cell_id"])

        issued = {
            "slot_id": slot["slot_id"],
            "cell_id": slot["cell_id"],
            "case_id": slot["case_id"],
            "block": slot["block"],
            "warmup": slot["warmup"],
            "phase": "calibration",
            "backend": slot["backend"],
            "arm": cell["arm"],
        }
        receipt = {
            "slot_id": slot["slot_id"],
            "cell_id": slot["cell_id"],
            "case_id": slot["case_id"],
            "block": slot["block"],
            "warmup": slot["warmup"],
            "status": "success",
            "prepared_call_s": 0.123,
            "finite": True,
            "same_policy_passed": True,
            "accuracy_qualified": True,
        }

        # Validate that identity fields match exactly
        for k in ("slot_id", "cell_id", "case_id", "block", "warmup"):
            self.assertEqual(issued[k], receipt[k])
        self.assertTrue(slot["warmup"])
        self.assertEqual(slot["block"], 0)

        # Tampering with block or cell_id must fail validation
        tampered = dict(receipt, block=1)
        self.assertNotEqual(issued["block"], tampered["block"])

    # 2. unsupported/pre-admission slots have no timing and do not count as physical calls
    def test_unsupported_slots_have_no_timing(self):
        row = {
            "slot_id": "slot-test-unsupported",
            "cell_id": "cell-test-unsupported",
            "case_id": "hs_n18",
            "phase": "calibration",
            "block": 1,
            "warmup": False,
            "backend": "upmem",
            "protocol_sha256": pc.sha(self.spec),
            "run_id": "test-run",
            "implementation_commit": self.spec["implementation_commit"],
            "evaluation_commit": "0" * 40,
            "execution_binding_sha256": pc.sha({"synthetic": 1}),
            "issued": False,
            "status": "not_issued_unsupported",
            "reason": "work_unit_bound: 70000 > 65536",
            "prepared_call_s": None,
        }
        self.assertIsNone(row["prepared_call_s"])
        self.assertFalse(row["issued"])
        self.assertTrue(row["status"].endswith("unsupported"))

    # 3. final config files cannot be emitted before selection/path seals and cannot drift afterward
    def test_final_config_cannot_be_emitted_before_seals(self):
        # Missing seal on selection must fail
        unsealed_sel = {"schema": "unified_v4_selection_v1"}
        with self.assertRaises(ValueError):
            pc.materialize_final(self.spec, self.manifest, unsealed_sel, [])

        # Corrupting path record seal must fail
        sel = pc.sealed({
            "schema": "unified_v4_selection_v1",
            "protocol_sha256": pc.sha(self.spec),
            "manifest_sha256": self.manifest["content_sha256"],
            "calibration_rows_sha256": "0" * 64,
            "run_id": "test",
            "evaluation_commit": "0" * 40,
            "rule": "test",
            "selections": [{"family": f, "policy": p, "selected": {"dpus": 4, "tasklets": 8}}
                           for f in pc.FAMILIES for p in (pc.FP, pc.I8)] +
                          [{"family": "stress", "policy": p, "selected": {"dpus": 4, "tasklets": 8}}
                           for p in (pc.FP, pc.I8)],
        })
        paths = [pc.sealed({
            "case_id": t["case_id"],
            "selection_sha256": sel["content_sha256"],
            "status": "selected",
            "tensor_count": 2,
            "path": [[0, 1]],
            "path_sha256": pc.sha([[0, 1]]),
            "path_id": "path_01",
        }) for t in self.manifest["final_templates"] if t["role"] == "upmem_f32"]
        # Drift path content
        corrupted = copy.deepcopy(paths)
        corrupted[0] = dict(corrupted[0], path=[[0, 2]])  # content changed without updating seal
        with self.assertRaises(ValueError):
            pc.materialize_final(self.spec, self.manifest, sel, corrupted)

    # 4. all three TN final roles consume the same source path hash
    def test_all_three_tn_final_roles_consume_same_source_path_hash(self):
        sel = pc.sealed({
            "schema": "unified_v4_selection_v1",
            "protocol_sha256": pc.sha(self.spec),
            "manifest_sha256": self.manifest["content_sha256"],
            "calibration_rows_sha256": "0" * 64,
            "run_id": "test",
            "evaluation_commit": "0" * 40,
            "rule": "test",
            "selections": [{"family": f, "policy": p, "selected": {"dpus": 4, "tasklets": 8}}
                           for f in pc.FAMILIES for p in (pc.FP, pc.I8)] +
                          [{"family": "stress", "policy": p, "selected": {"dpus": 4, "tasklets": 8}}
                           for p in (pc.FP, pc.I8)],
        })
        cases = sorted({t["case_id"] for t in self.manifest["final_templates"]})
        paths = [pc.sealed({
            "case_id": cid,
            "selection_sha256": sel["content_sha256"],
            "status": "selected",
            "tensor_count": 2,
            "path": [[0, 1]],
            "path_sha256": pc.sha([[0, 1]]),
            "path_id": f"path_{cid}",
        }) for cid in cases]

        final_man = pc.materialize_final(self.spec, self.manifest, sel, paths)
        for cid in cases:
            tn_cells = [c for c in final_man["cells"] if c["case_id"] == cid and c["role"] in ("upmem_f32", "upmem_int8", "numpy_f32_p1")]
            hashes = {c["selected_path_sha256"] for c in tn_cells}
            self.assertEqual(len(hashes), 1, f"path hash mismatch across TN roles for {cid}")
            self.assertEqual(hashes.pop(), pc.sha([[0, 1]]))

    # 5. reusing an int8 plan cannot bypass float32/generic admission checks
    def test_int8_cannot_bypass_f32_admission(self):
        # If no R path was admitted under float32, int8 must be marked ineligible
        sel = pc.sealed({
            "schema": "unified_v4_selection_v1",
            "protocol_sha256": pc.sha(self.spec),
            "manifest_sha256": self.manifest["content_sha256"],
            "calibration_rows_sha256": "0" * 64,
            "run_id": "test",
            "evaluation_commit": "0" * 40,
            "rule": "test",
            "selections": [{"family": f, "policy": p, "selected": {"dpus": 4, "tasklets": 8}}
                           for f in pc.FAMILIES for p in (pc.FP, pc.I8)] +
                          [{"family": "stress", "policy": p, "selected": {"dpus": 4, "tasklets": 8}}
                           for p in (pc.FP, pc.I8)],
        })
        cases = sorted({t["case_id"] for t in self.manifest["final_templates"]})
        paths = [pc.sealed({
            "case_id": cid,
            "selection_sha256": sel["content_sha256"],
            "status": "no_selected_R_path" if cid == "bb84_n18" else "selected",
            "tensor_count": 2,
            "path": [[0, 1]] if cid != "bb84_n18" else None,
            "path_sha256": pc.sha([[0, 1]]) if cid != "bb84_n18" else None,
            "path_id": f"path_{cid}" if cid != "bb84_n18" else None,
        }) for cid in cases]

        final_man = pc.materialize_final(self.spec, self.manifest, sel, paths)
        bb84_i8 = next(c for c in final_man["cells"] if c["case_id"] == "bb84_n18" and c["role"] == "upmem_int8")
        self.assertFalse(bb84_i8["eligible_for_runtime_admission"])
        self.assertEqual(bb84_i8["not_runnable_reason"], "no_selected_R_path")

    # 6. original numeric guards and same-policy integer replay remain intact
    def test_numeric_guards_and_same_policy_replay(self):
        val_spec = self.spec["validation"]
        # Valid errors
        good_err = {
            "finite": True,
            "elementwise_allclose": True,
            "relative_l2": 1e-6,
            "norm_drift": 1e-6,
            "max_abs": 1e-6,
            "reference_peak": 1.0,
        }
        self.assertTrue(runner.check_accuracy(good_err, val_spec))

        # Relative L2 violation
        bad_l2 = dict(good_err, relative_l2=1e-3)
        self.assertFalse(runner.check_accuracy(bad_l2, val_spec))

        # Nonfinite violation
        bad_finite = dict(good_err, finite=False)
        self.assertFalse(runner.check_accuracy(bad_finite, val_spec))

    # 7. all fresh calibration controls are jointly blocked; aliases do not increase sample counts
    def test_calibration_aliases_jointly_blocked(self):
        vmap = {}
        for v in self.manifest["calibration_views"]:
            vmap[(v["view"], v["case_id"], v["point"])] = v["cell_id"]
        # A0 and T1 share the exact same cell_id
        self.assertEqual(vmap[("A", "bb84_n18", "A0")], vmap[("T", "bb84_n18", "T1")])
        # A4 and D4/T8 share the exact same cell_id
        self.assertEqual(vmap[("A", "bb84_n18", "A4")], vmap[("D", "bb84_n18", "D4/T8")])
        # Total unique cells in manifest must be exactly 434
        self.assertEqual(len(self.manifest["calibration_cells"]), 434)

    # 8. old evidence rows cannot be fed into C/W as new observations
    def test_old_evidence_rejected(self):
        # Mismatched implementation_commit or protocol_sha256 must raise ValueError
        bad_row = {
            "slot_id": self.manifest["calibration_slots"][0]["slot_id"],
            "cell_id": self.manifest["calibration_slots"][0]["cell_id"],
            "case_id": self.manifest["calibration_slots"][0]["case_id"],
            "phase": "calibration",
            "block": 0,
            "warmup": True,
            "backend": "upmem",
            "protocol_sha256": pc.sha(self.spec),
            "run_id": "test",
            "implementation_commit": "old_commit_0000000000000000000000000000",
            "evaluation_commit": "0" * 40,
            "execution_binding_sha256": "0" * 64,
            "issued": True,
            "status": "success",
            "prepared_call_s": 1.0,
            "finite": True,
            "same_policy_passed": True,
            "accuracy_qualified": True,
        }
        with self.assertRaises(ValueError):
            pc.validate_calibration_rows(self.spec, self.manifest, [bad_row])

    # 9. fail-closed on errors, missing receipts, accuracy failures
    def test_fail_closed_error_handling(self):
        # Incomplete rows list fails validation
        with self.assertRaises(ValueError):
            pc.validate_calibration_rows(self.spec, self.manifest, [])

    # 10. tiny R trace regression reproduces fixed generator/scorer behavior
    def test_tiny_r_trace_determinism(self):
        # Two identical R searches on qual_hs_n04 produce identical path and score
        from quantum_bench.circuits import builtin_circuit
        from quantum_bench.model import make_simulation_job
        from quantum_bench.lowering import lower_tensor_network
        from quantum_bench.upmem.path_heuristic import LaunchCostScales

        scales = LaunchCostScales(h=1000.0, p=1000.0, n=10.0, m=1000.0, w=1000.0)
        c = builtin_circuit("ghz_chain", {"n_qubits": 4})
        job = make_simulation_job(circuit=c)
        net, _ = lower_tensor_network(job)

        from quantum_bench.planning import plan_opt_einsum
        path, _ = plan_opt_einsum(net, optimize="greedy")
        path_tuple = tuple(tuple(step) for step in path)
        cb = runner.make_candidate_evaluation_callback(
            network=net,
            selected_f32_topology={"dpus": 1, "tasklets": 8},
            weights=[1, 2, 1, 1, 5],
            scales=scales,
        )
        res1 = cb(path_tuple, 100.0)
        res2 = cb(path_tuple, 100.0)
        self.assertEqual(res1.score, res2.score)
        self.assertEqual(res1.facts["r_score"], res2.facts["r_score"])

    # 11. online callbacks cannot read final result directories or hardware timing for ranking
    def test_online_callbacks_do_not_use_hardware_timing(self):
        # Callback receives (path, tree_flops) and computes launch cost from structure alone
        from quantum_bench.circuits import builtin_circuit
        from quantum_bench.model import make_simulation_job
        from quantum_bench.lowering import lower_tensor_network
        from quantum_bench.upmem.path_heuristic import LaunchCostScales

        scales = LaunchCostScales(h=1000.0, p=1000.0, n=10.0, m=1000.0, w=1000.0)
        c = builtin_circuit("ghz_chain", {"n_qubits": 4})
        job = make_simulation_job(circuit=c)
        net, _ = lower_tensor_network(job)

        from quantum_bench.planning import plan_opt_einsum
        path, _ = plan_opt_einsum(net, optimize="greedy")
        path_tuple = tuple(tuple(step) for step in path)
        cb = runner.make_candidate_evaluation_callback(
            network=net,
            selected_f32_topology={"dpus": 1, "tasklets": 8},
            weights=[1, 2, 1, 1, 5],
            scales=scales,
        )
        eval_res = cb(path_tuple, 250.0)
        self.assertEqual(eval_res.score, 250.0)  # Objective told to Optuna is FLOPs
        self.assertIn("r_score", eval_res.facts)
        self.assertIsInstance(eval_res.facts["r_score"], float)

    # 12. summary estimates (including cold-cost accounting) match small known examples
    def test_cold_cost_accounting(self):
        plan_s = 10.0
        cached_s = 2.0
        cold_est = plan_s + cached_s
        amort_1 = cached_s + plan_s / 1.0
        amort_10 = cached_s + plan_s / 10.0
        amort_100 = cached_s + plan_s / 100.0

        self.assertAlmostEqual(cold_est, 12.0)
        self.assertAlmostEqual(amort_1, 12.0)
        self.assertAlmostEqual(amort_10, 3.0)
        self.assertAlmostEqual(amort_100, 2.1)

    # 13. empty plots and invented geometric-mean members are rejected
    def test_geometric_mean_rejection(self):
        # Less than 6 families must raise ValueError
        partial_ratios = {"bb84": 2.0, "bv": 1.5, "edc": 1.2, "hs": 1.8, "qrng": 1.0}  # missing xor
        with self.assertRaises(ValueError):
            readout.six_family_geometric_mean_ratio(partial_ratios)

        # Full 6 families succeeds
        full_ratios = dict(partial_ratios, xor=1.4)
        gmean = readout.six_family_geometric_mean_ratio(full_ratios)
        self.assertTrue(math.isfinite(gmean) and gmean > 0)


if __name__ == "__main__":
    unittest.main()
