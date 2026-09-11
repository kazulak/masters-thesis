import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import build as b
import tables
import verify
from fixture import campaign


class NumericTests(unittest.TestCase):
    def test_median_not_mean(self): self.assertEqual(b.median_mad([1,2,100]),(2,1))
    def test_ratio_reduction(self): self.assertAlmostEqual(b.ratio_fields(2)['time_reduction_pct'],50)
    def test_regression_increase(self): self.assertAlmostEqual(b.ratio_fields(.5)['denominator_time_increase_pct'],100)
    def test_nonfinite(self):
        for x in ('NaN','inf','-inf'):
            with self.assertRaises(ValueError):b.number(x)
    def test_missing_number(self):
        with self.assertRaises(ValueError):b.number('')
    def test_optional_number(self):self.assertIsNone(b.number('',optional=True))
    def test_strict_integer(self):
        for x in ('1.0',True,'01'):
            with self.assertRaises(ValueError):b.integer(x)
    def test_strict_boolean(self):
        for x in (None,'',1,'0','maybe'):
            with self.assertRaises(ValueError):b.boolean(x)
    def test_boolean_values(self):
        self.assertTrue(b.boolean('True'));self.assertFalse(b.boolean('False'))
    def test_bootstrap_self(self):self.assertEqual(b.bootstrap([1,3,5],[1,3,5],100,12),(1,1))
    def test_bootstrap_repeatable(self):self.assertEqual(b.bootstrap([1,3,5],[2,3,9],100,12),b.bootstrap([1,3,5],[2,3,9],100,12))
    def test_bootstrap_unequal(self):
        with self.assertRaises(ValueError):b.bootstrap([1,2],[1],100,0)
    def test_bootstrap_nonpositive(self):
        with self.assertRaises(ValueError):b.bootstrap([0,2],[1,1],100,0)
    def test_path_traversal(self):
        for p in ('../x','/x','x/../../y','x:y'):
            with self.assertRaises(ValueError):b.safe_path(p)
    def test_csv_duplicate_header(self):
        with self.assertRaises(ValueError):b.csv_rows(b'a,a\n1,2\n','x')
    def test_csv_bad_shape(self):
        with self.assertRaises(ValueError):b.csv_rows(b'a,b\n1,2,3\n','x')
    def test_original_history_source_id(self):
        r=b.csv_rows(b'source_id,value\ncomposition,1\n','history')[0]
        self.assertEqual(r['source_id'],'composition');self.assertEqual(r['input_source_id'],'history')
    def test_typst_escaping(self):
        text=tables.typst_table('a #b',['x','y'],[['[not code]','"quoted" \\ literal']],'≤ 1')
        self.assertIn('"[not code]"',text);self.assertIn('\\"quoted\\"',text)
        self.assertIn('≤',text);self.assertNotIn('\\u2264',text)
    def test_typst_shape_rejected(self):
        with self.assertRaises(ValueError):tables.typst_table('t',['a'],[['b','c']],'x')
    def test_real_p6_numbers(self):
        rows=b.csv_rows((Path(__file__).parent/'fixtures/real_p6_aggregates.csv').read_bytes(),'p6')
        r=next(r for r in rows if r['group']=='all' and r['contrast']=='G/U' and r['metric']=='session_inclusive_s')
        self.assertAlmostEqual(b.ratio_fields(float(r['family_balanced_geometric_ratio']))['time_reduction_pct'],21.0427409,places=5)
        u=next(r for r in rows if r['group']=='all' and r['contrast']=='R/U' and r['metric']=='session_inclusive_s')
        self.assertLess(float(u['paired_bootstrap_low']),1);self.assertGreater(float(u['paired_bootstrap_high']),1)
    def test_real_quantization_numbers(self):
        rows=b.csv_rows((Path(__file__).parent/'fixtures/real_quantization.csv').read_bytes(),'quantization')
        for r in rows:b.close(float(r['logical_float32_operand_bytes'])/float(r['logical_int8_operand_bytes']),float(r['nominal_compression_ratio']),'real logical compression')
        self.assertAlmostEqual(100*float(rows[-1]['relative_l2_vs_float32_same_dag']),8.316143602132797)


class CampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.original,cls.config=campaign()
    def mutate(self,fn):
        data=copy.deepcopy(self.original);fn(data)
        with self.assertRaises((ValueError,KeyError)):b.derive(data,self.config,verify_intervals=False)
    def test_complete_shape_and_intervals(self):
        r,a=b.derive(self.original,self.config)
        self.assertEqual(a['accounting']['measured_success'],1175)
        self.assertEqual(len(r['frontiers']),24)
        self.assertEqual(sum(c['complete'] for c in r['cells']),229)
        self.assertEqual(len(r['times']),1871);self.assertEqual(len(r['comparisons']),453)
    def test_warmup_missing(self):self.mutate(lambda d:d['final_observations'][0].pop('warmup'))
    def test_warmup_reclassified(self):self.mutate(lambda d:d['final_observations'][0].update(warmup='False'))
    def test_duplicate_attempt(self):self.mutate(lambda d:d['final_observations'].__setitem__(1,copy.deepcopy(d['final_observations'][0])))
    def test_missing_attempt(self):self.mutate(lambda d:d['final_observations'].pop())
    def test_extra_attempt(self):self.mutate(lambda d:d['final_observations'].append(copy.deepcopy(d['final_observations'][0])))
    def test_wrong_arm(self):self.mutate(lambda d:d['final_observations'][1].update(tasklets='99'))
    def test_wrong_block(self):self.mutate(lambda d:d['final_observations'][1].update(block='99'))
    def test_failed_status(self):self.mutate(lambda d:d['final_observations'][1].update(status='failure'))
    def test_accuracy_false(self):self.mutate(lambda d:d['final_observations'][1].update(accuracy_qualified='False'))
    def test_scalar_error_bound(self):self.mutate(lambda d:d['final_observations'][1].update(relative_l2='.1'))
    def test_nonfinite_timing(self):self.mutate(lambda d:d['final_observations'][1].update(prepared_call_s='nan'))
    def test_wrong_coverage(self):self.mutate(lambda d:d['final_coverage'][0].update(success='6'))
    def test_wrong_summary(self):self.mutate(lambda d:d['final_times'][0].update(median='123456'))
    def test_wrong_mad(self):self.mutate(lambda d:d['final_times'][0].update(raw_mad='123456'))
    def test_duplicate_summary(self):self.mutate(lambda d:d['final_times'].__setitem__(1,copy.deepcopy(d['final_times'][0])))
    def test_wrong_ratio(self):self.mutate(lambda d:d['final_comparisons'][0].update(ratio='2'))
    def test_wrong_reduction(self):self.mutate(lambda d:d['final_comparisons'][0].update(denominator_time_reduction_percent='12'))
    def test_wrong_efficiency(self):self.mutate(lambda d:d['final_comparisons'][0].update(parallel_efficiency='9'))
    def test_wrong_interval(self):
        data=copy.deepcopy(self.original);data['final_comparisons'][0]['descriptive_high']='2'
        with self.assertRaises(ValueError):b.derive(data,self.config)
    def test_frontier_mismatch(self):self.mutate(lambda d:d['final_largest_tested'][0].update(largest_fully_measured_qubits='26'))
    def test_geometry_error(self):self.mutate(lambda d:d['final_contractions'][0].update(real_macs='3'))
    def test_output_size_error(self):self.mutate(lambda d:d['final_circuits'][0].update(full_state_c64_bytes='17'))
    def test_p6_ratio_error(self):self.mutate(lambda d:d['p6_contrasts'][0].update(ratio_of_medians='99'))
    def test_p6_alias_error(self):self.mutate(lambda d:d['p6_contrasts'][0].update(same_selected_path='True'))
    def test_p6_aggregate_error(self):self.mutate(lambda d:d['p6_aggregates'][0].update(family_balanced_geometric_ratio='99'))
    def test_quant_compression_error(self):self.mutate(lambda d:d['quantization'][0].update(nominal_compression_ratio='99'))
    def test_history_context_not_promoted(self):
        data=copy.deepcopy(self.original);data['mechanisms'][0]['provenance_class']='chat_context_transcription_not_newly_source_verified'
        r,_=b.derive(data,self.config,verify_intervals=False)
        self.assertIn('unverified',r['mechanisms'][0]['synthesis_treatment'])


class GitTests(unittest.TestCase):
    def test_pinned_git_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def git(*args):return subprocess.check_output(['git','-C',str(root),*args],stderr=subprocess.DEVNULL).decode().strip()
            git('init');git('config','user.email','fixture@example.invalid');git('config','user.name','Fixture')
            (root/'evidence').mkdir();(root/'evidence/data.csv').write_bytes(b'x\n1\n')
            h=b.sha((root/'evidence/data.csv').read_bytes())
            (root/'evidence/SHA256SUMS').write_text(h+'  data.csv\n')
            git('add','.');git('commit','-m','synthetic fixture');ref=git('rev-parse','HEAD')
            loader=b.GitSources(root,dict(evidence_commit=ref,repository='fixture/repo',checksum_packages=['evidence']))
            loader.verify_packages();self.assertEqual(loader.package_checks[0]['verified_members'],1)
            (root/'evidence/data.csv').write_text('not the Git object')
            self.assertEqual(loader.read(ref,'evidence/data.csv'),b'x\n1\n')
            with self.assertRaises(ValueError):loader.read('main','evidence/data.csv')
            with self.assertRaises(ValueError):loader.read(ref,'missing')
    def test_bad_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def git(*a):return subprocess.check_output(['git','-C',str(root),*a],stderr=subprocess.DEVNULL).decode().strip()
            git('init');git('config','user.email','fixture@example.invalid');git('config','user.name','Fixture')
            (root/'e').mkdir();(root/'e/x').write_text('data');(root/'e/SHA256SUMS').write_text('0'*64+'  x\n')
            git('add','.');git('commit','-m','bad manifest');ref=git('rev-parse','HEAD')
            with self.assertRaises(ValueError):b.GitSources(root,dict(evidence_commit=ref,repository='fixture/repo',checksum_packages=['e'])).verify_packages()


if __name__=='__main__':unittest.main()
