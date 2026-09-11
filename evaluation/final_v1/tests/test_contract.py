"""Pure delivery tests. They do not qualify QuEST, the SDK or physical UPMEM."""
import dataclasses
import json
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import final_eval as f
import qualify
import readout


class ContractTests(unittest.TestCase):
    def setUp(self):self.spec=f.read(f.PACKAGE/'scope.json')
    def test_frozen_source(self):self.assertEqual(self.spec['source_commit'],f.FROZEN)
    def test_all_tasklets(self):self.assertEqual(self.spec['tasklets'],list(range(1,25)))
    def test_one_rank_max(self):self.assertEqual(f.dpu_grid(64,self.spec),[1,2,3,4,8,16,32,48,64])
    def test_partial_rank_endpoint(self):self.assertEqual(f.dpu_grid(60,self.spec),[1,2,3,4,8,16,32,48,60])
    def test_rank_too_small(self):
        with self.assertRaises(RuntimeError):f.dpu_grid(3,self.spec)
    def test_rank_not_multirank(self):
        with self.assertRaises(RuntimeError):f.dpu_grid(128,self.spec)
    def test_case_count(self):self.assertEqual(len(f.cases(self.spec)),81)
    def test_width_count(self):self.assertEqual(sum(c['role']=='width' for c in f.cases(self.spec)),72)
    def test_depth_not_width(self):self.assertEqual(sum(c['role']=='depth' for c in f.cases(self.spec)),9)
    def test_edc_ancillas(self):
        ns=[c['n'] for c in f.cases(self.spec) if c['family']=='edc']
        self.assertEqual(ns,[7,11,15,17,19,21,23,25,27]);self.assertTrue(all(n%2 for n in ns))
    def test_hs_even(self):self.assertTrue(all(c['n']%2==0 for c in f.cases(self.spec) if c['family']=='hs'))
    def test_no_duplicate_cases(self):
        cs=f.cases(self.spec);self.assertEqual(len(cs),len({c['case_id'] for c in cs}))
    def test_exact_attempt_budget(self):
        cs,defs=f.suite_definitions(self.spec,64,16)
        self.assertEqual(len(cs),82);self.assertEqual(f.counts(defs),dict(measurement_and_warmup_attempts=10229,physical_attempts=6098))
    def test_suite_counts(self):
        _,ds=f.suite_definitions(self.spec,64,16)
        self.assertEqual({s:len(d['entries'])*(d['warmups']+d['measurements']) for s,d in ds.items()},
             dict(T=1152,D=864,A=680,Q=648,W=6885))
    def test_single_cpu_alias(self):
        _,ds=f.suite_definitions(self.spec,64,1)
        self.assertEqual(len(ds['W']['entries']),81*4)
    def test_quantization_case(self):
        cs,ds=f.suite_definitions(self.spec,64,16)
        self.assertEqual(cs['stress_n18_l4']['role'],'quantization_only')
        self.assertNotIn('stress_n18_l4',{e['case_id'] for e in ds['W']['entries']})
    def test_qualification_budget(self):self.assertEqual(len(qualify.qualification_arms(self.spec,64))*2,132)
    def test_qualification_cpu_reference_count(self):self.assertEqual(len(qualify.fixture_cases()),13)
    def test_no_guided_reoptimization(self):
        self.assertIn('no new search',self.spec['P6_rule'])
        self.assertIn('greedy',self.spec['path_rule'])
    def test_deterministic_order(self):
        _,ds=f.suite_definitions(self.spec,64,2);e=ds['A']['entries']
        self.assertEqual(f.order_entries(e,1,'A',0),f.order_entries(e[::-1],1,'A',0))
        self.assertNotEqual(f.order_entries(e,1,'A',0),f.order_entries(e,1,'A',1))
    def test_json_nonfinite_forbidden(self):
        with self.assertRaises(ValueError):f.canonical({'time':float('nan')})
    def test_write_once(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.json';f.write(p,{'a':1})
            with self.assertRaises(FileExistsError):f.write(p,{'a':2})
            self.assertEqual(f.read(p),{'a':1})
    def test_accuracy_exact(self):
        a=np.array([1,2j],np.complex64);self.assertTrue(f.accuracy(f.errors(a,a),self.spec))
    def test_accuracy_phase_not_aligned(self):
        a=np.array([1,0j]);self.assertFalse(f.accuracy(f.errors(-a,a),self.spec))
    def test_int8_quality_not_assumed(self):self.assertIsNone(self.spec['validation']['int8_full_precision_threshold'])
    def test_accuracy_nonfinite(self):self.assertFalse(f.errors(np.array([np.nan]),np.array([1]))['finite'])
    def test_norm_metrics_distinct(self):
        e=f.errors(np.array([2]),np.array([1]));self.assertEqual(e['norm_drift'],1);self.assertEqual(e['probability_norm_drift'],3)
    def test_comparison_direction(self):
        x=readout.comparison([2,4,6],[1,2,3],100,1)
        self.assertEqual(x['ratio'],2);self.assertEqual(x['denominator_time_reduction_percent'],50)
    def test_comparison_shared_resampling(self):
        a=readout.comparison([1,2,3,4,5],[1,2,3,4,5],100,2)
        self.assertEqual(a['descriptive_low'],1);self.assertEqual(a['descriptive_high'],1)
    def test_ratio_is_not_mean_of_ratios(self):
        a=readout.comparison([1,2,100],[1,4,5],100,1)
        self.assertEqual(a['ratio'],.5)
    def test_uncertainty_deterministic(self):
        self.assertEqual(readout.comparison([1,2,4],[2,3,5],100,7),readout.comparison([1,2,4],[2,3,5],100,7))
    def test_no_invalid_timings(self):
        with self.assertRaises(RuntimeError):readout.comparison([0,1],[1,2])
    def test_mad_raw(self):self.assertEqual(readout.median_mad([1,2,100]),(2,1))
    def test_historical_sources_pinned(self):
        records=f.read(f.PACKAGE/'historical_sources.json')
        self.assertTrue(all(len(r['ref'])==40 for r in records));self.assertEqual(len(records),17)
    def test_five_policies_only(self):
        _,d=f.suite_definitions(self.spec,64,8)
        for suite in d.values():
            for e in suite['entries']:
                if e['arm']['backend']=='upmem':self.assertEqual(e['arm']['geometry'],'panel_only_v1')


if __name__=='__main__':unittest.main()
