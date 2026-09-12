"""Reporting regressions against immutable published v4 evidence; no execution."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'evaluation/unified_v4'))
import readout  # noqa: E402 - standalone script import

DATA = ROOT / 'thesis/implementation/thesis_results/unified_final_v4'


def load(name):
    return json.loads((DATA / name).read_text())


class AccountingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = [load(p) for p in ('manifest/manifest.json', 'final_manifest.json',
                                       'calibration_rows.json', 'final_rows.json', 'path_records.json', 'retention.json')]

    def test_canonical_route_path_and_physical_accounting(self):
        a = readout.derive_accounting(*self.inputs)
        self.assertEqual((a['paths']['selected'], a['paths']['no_selected'], a['paths']['searches']), (46, 6, 52))
        self.assertEqual(a['paths']['proposals'], 6656)
        self.assertEqual({r: c['issued'] for r, c in a['routes'].items()},
                         dict(zip(readout.FINAL_ROLES, (276, 276, 276, 312, 312))))
        self.assertTrue(all(c['planned'] == 312 and c['success'] == c['issued'] for c in a['routes'].values()))
        self.assertEqual(a['final'], dict(planned=1560, issued=1452, success=1452, not_issued=108))
        self.assertEqual(a['physical']['final'], dict(planned=624, issued=552, success=552, not_issued=72))
        self.assertEqual((a['physical']['issued'], a['physical']['ceiling']), (3334, 3406))
        self.assertEqual(a['qualification']['configurations'], 54)
        self.assertEqual(a['archive_files_count'], 8288)
        self.assertEqual({p['case_id'] for p in a['paths']['frontiers']},
                         {'bb84_n26','bv_n26','edc_n25','hs_n26','qrng_n26','xor_n26'})
        self.assertEqual(sum(r['count'] for r in a['route_outcomes'] if not r['issued']), 108)

    def check_bad(self, mutate):
        inputs = copy.deepcopy(self.inputs)
        mutate(inputs)
        with self.assertRaises(ValueError):
            readout.derive_accounting(*inputs)

    def test_duplicate_slot_rejected(self):
        self.check_bad(lambda x: x[3].__setitem__(0, x[3][1]))

    def test_missing_slot_rejected(self):
        self.check_bad(lambda x: x[3].pop())

    def test_wrong_case_rejected(self):
        self.check_bad(lambda x: x[3][0].update(case_id='bb84_n26'))

    def test_nonboolean_issue_rejected(self):
        self.check_bad(lambda x: x[3][0].update(issued=1))

    def test_no_path_issue_rejected(self):
        self.check_bad(lambda x: next(r for r in x[3] if not r['issued']).update(issued=True))

    def test_wrong_frontier_reason_rejected(self):
        self.check_bad(lambda x: next(r for r in x[3] if not r['issued']).update(reason='MRAM'))

    def test_frontier_runtime_rejected(self):
        self.check_bad(lambda x: next(r for r in x[3] if not r['issued']).update(job_to_state_cached_path_s=0))

    def test_incorrect_retention_count_rejected(self):
        self.check_bad(lambda x: x[5]['attempt_counts'].update(final_issued_slots=1453))

    def test_retention_identity_bindings_rejected(self):
        for key in ('run_id', 'implementation_commit', 'evaluator_commit', 'protocol_sha256',
                    'static_manifest_sha256', 'selection_sha256', 'final_manifest_sha256'):
            with self.subTest(key=key):
                self.check_bad(lambda x: x[5].update({key: 'wrong'}))

    def test_missing_path_record_rejected(self):
        self.check_bad(lambda x: x[4].pop())

    def test_wrong_path_binding_rejected(self):
        self.check_bad(lambda x: x[4][0].update(case_id='unknown'))


class ColdCostTests(unittest.TestCase):
    def test_supported_uses_cached_job_to_state(self):
        case = dict(case_id='fixture', family='bb84', n=8)
        path = dict(planning_once_s=100., status='selected', reason=None)
        rows = [dict(job_to_state_cached_path_s=v, prepared_call_s=.001) for v in (2., 3., 4.)]
        out = readout.cold_cost_row(case, path, rows)
        self.assertEqual([out[k] for k in ('median_cached_s','cold_estimate','amortized_k1','amortized_k10','amortized_k100')],
                         [3., 103., 103., 13., 4.])

    def test_no_path_retains_search_only(self):
        case = dict(case_id='fixture', family='bb84', n=26)
        path = dict(planning_once_s=37., status='no_selected_R_path', reason='no_admitted_candidate')
        out = readout.cold_cost_row(case, path, [])
        self.assertEqual(out['planning_once_s'], 37.)
        self.assertEqual(out['path_reason'], 'no_admitted_candidate')
        for key in ('median_cached_s','cold_estimate','amortized_k1','amortized_k10','amortized_k100'):
            self.assertIsNone(out[key])
        with self.assertRaises(ValueError):
            readout.cold_cost_row(case, path, [dict(job_to_state_cached_path_s=1)])

    def test_selected_path_missing_or_invalid_cached_metric_rejected(self):
        case = dict(case_id='fixture', family='bb84', n=8)
        path = dict(planning_once_s=100., status='selected', reason=None)
        for rows in ([], [dict(prepared_call_s=1)], [dict(job_to_state_cached_path_s=0)],
                     [dict(job_to_state_cached_path_s=float('nan'))]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                readout.cold_cost_row(case, path, rows)


class ReceiptJoinTests(unittest.TestCase):
    def test_receipts_enrich_without_overriding(self):
        row = dict(slot_id='s', prepared_call_s=2., cell_id='c')
        issued = dict(slot_id='s', cell_id='c', issued_time_utc='timestamp')
        receipt = dict(slot_id='s', prepared_call_s=2., cell_id='c', kernel_s=1.)
        joined = readout.join_receipts(row, issued, receipt)
        self.assertEqual(joined['prepared_call_s'], 2.)
        self.assertEqual(joined['kernel_s'], 1.)

    def test_changed_identity_timing_or_binding_rejected(self):
        row = dict(slot_id='s', prepared_call_s=2., execution_binding_sha256='binding')
        for change in (dict(slot_id='different'), dict(prepared_call_s=3.), dict(execution_binding_sha256='other')):
            with self.subTest(change=change), self.assertRaises(ValueError):
                readout.join_receipts(row, dict(slot_id='s'), {**row, **change})


if __name__ == '__main__':
    unittest.main()
