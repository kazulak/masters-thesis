"""Test the unified-v4 generator, independently of the legacy synthesis generator."""
import copy
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

PUB = Path(__file__).resolve().parents[1]
ROOT = PUB.parents[2]
spec = importlib.util.spec_from_file_location('unified_v4_publication', PUB / 'build.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
DATA = ROOT / 'thesis/implementation/thesis_results/unified_final_v4'


def json_read(name):
    return json.loads((DATA / name).read_text())


def csv_read(name):
    with (DATA / 'readout' / name).open() as f:
        return list(csv.DictReader(f))


class PublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json_read('manifest/manifest.json')
        cls.final = json_read('final_manifest.json')
        cls.paths = json_read('path_records.json')
        cls.labels = b.ablation_labels(cls.manifest)
        cls.w = csv_read('W.csv')

    def tearDown(self):
        b.plt.close('all')

    def test_ablation_labels_match_frozen_arms(self):
        expected = ['D1/T1 serial unfused','D1/T8 serial unfused','D4/T8 serial unfused',
                    'D4/T8 serial fused','D4/T8 static-DAG fused']
        for stage, text in zip(('A0','A1','A2','A3','A4'), expected):
            self.assertTrue(self.labels[stage]['description'].startswith(text))
        self.assertIn('complex launch fusion / four-product fusion', self.labels['A3']['description'])
        with patch.object(b, 'save_fig') as save:
            b.build_figure_f3(csv_read('A.csv'), self.labels)
        fig = save.call_args.args[0]
        self.assertTrue(all('D1/T8' in ax.get_xticklabels()[1].get_text() for ax in fig.axes[3:]))

    def test_ablation_geometric_mean_unchanged(self):
        rows = csv_read('aggregates.csv')
        actual = next(float(r['ratio']) for r in rows if r['case_id'] == 'six_family_geometric_mean'
                      and r['contrast'] == 'A0_A4_matched_endpoint')
        self.assertAlmostEqual(actual, 6.247, places=3)
        a = csv_read('A.csv')
        ratios = []
        for cid in b.CALIBRATION_CASES.values():
            values = {r['point']: float(r['median_prepared_call_s']) for r in a if r['case_id'] == cid}
            ratios.append(values['A0']/values['A4'])
        self.assertAlmostEqual(b.gmean(ratios), actual, places=12)

    def test_frontiers_have_axis_relative_text_and_no_runtime_markers(self):
        with patch.object(b, 'save_fig') as save:
            b.build_figure_f6(self.w, self.final, self.paths)
        fig = save.call_args.args[0]
        for ax, family in zip(fig.axes, b.PRIMARY_FAMILIES):
            notes = [t for t in ax.texts if 'R path unavailable' in t.get_text()]
            self.assertEqual(len(notes), 1)
            self.assertEqual(notes[0].get_transform(), ax.get_xaxis_transform())
            self.assertIn('no admitted candidate', notes[0].get_text())
            self.assertEqual(len(ax.lines), 4)
            max_n = 25 if family == 'edc' else 26
            self.assertEqual(max(ax.lines[0].get_xdata()), max_n)
            self.assertEqual(max(ax.lines[1].get_xdata()), max_n)
            self.assertEqual(max(ax.lines[2].get_xdata()), max_n-2)
            self.assertEqual(max(ax.lines[3].get_xdata()), max_n-2)

    def test_unexplained_missing_width_data_rejected(self):
        with self.assertRaises(ValueError):
            b.build_figure_f6(self.w[1:], self.final, self.paths)

    def test_duplicate_width_data_rejected(self):
        with self.assertRaises(ValueError):
            b.build_figure_f6(self.w + [self.w[0]], self.final, self.paths)

    def test_unknown_frontier_cause_rejected(self):
        paths = copy.deepcopy(self.paths)
        next(p for p in paths if p['status'] != 'selected')['reason'] = 'MRAM'
        with self.assertRaises(ValueError):
            b.build_figure_f6(self.w, self.final, paths)

    def test_tables_use_correct_labels_counts_and_missing_costs(self):
        a = b.v4_readout.derive_accounting(self.manifest, self.final, json_read('calibration_rows.json'),
                                         json_read('final_rows.json'), self.paths, json_read('retention.json'))
        cold = []
        for p in self.paths:
            c = next(c for c in self.manifest['cases'] if c['case_id'] == p['case_id'])
            cold.append(b.v4_readout.cold_cost_row(c, p, [dict(job_to_state_cached_path_s=2)] if p['status']=='selected' else []))
        with tempfile.TemporaryDirectory() as tmp, patch.object(b, 'TAB_DIR', Path(tmp)):
            b.build_table_t3(csv_read('A.csv'), csv_read('aggregates.csv'), self.labels)
            b.build_table_t5(json_read('selection.json'))
            b.build_table_t6(cold)
            b.build_table_t7(a)
            tables = {p.name: p.read_text() for p in Path(tmp).glob('*.typ')}
        self.assertIn('D1/T8 serial unfused', tables['T3_ablation_cumulative.typ'])
        self.assertIn('four-product fusion', tables['T3_ablation_cumulative.typ'])
        self.assertIn('no quality tuning for int8', tables['T5_selection_winners.typ'])
        self.assertIn('Cached-path job-to-state', tables['T6_cold_amortized_costs.typ'])
        self.assertIn('rather than separately timed cold executions', tables['T6_cold_amortized_costs.typ'])
        self.assertEqual(tables['T6_cold_amortized_costs.typ'].count('[—], [—], [—], [—]'), 6)
        for text in ('3,334', '3,406', '8,288', 'selected paths: 46', 'no-path outcomes: 6', '[276]', '[312]'):
            self.assertIn(text, tables['T7_campaign_accounting.typ'])


if __name__ == '__main__':
    unittest.main()
