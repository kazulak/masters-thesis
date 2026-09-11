import csv
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import final_eval as f


class ReceiptTests(unittest.TestCase):
    def test_archive_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);work=root/'work';part=work/'receipts'/'A';part.mkdir(parents=True)
            (part/'one.txt').write_text('raw record\n')
            args=type('Args',(),dict(work=str(work),part='receipts/A',output=str(root/'archive.tar.gz')))()
            f.archive(args)
            result=subprocess.run([sys.executable,str(f.PACKAGE/'tools/collect_archive.py'),
               '--archive',str(root/'archive.tar.gz'),'--manifest',str(root/'archive.tar.gz.manifest.json'),
               '--receipt',str(root/'verified.json')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertTrue(f.read(root/'verified.json')['passed'])
    def test_archive_root_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);work=root/'work';work.mkdir();(work/'x').write_bytes(b'xyz')
            args=type('Args',(),dict(work=str(work),part='.',output=str(root/'archive.tar.gz')))()
            f.archive(args)
            r=subprocess.run([sys.executable,str(f.PACKAGE/'tools/collect_archive.py'),'--archive',str(root/'archive.tar.gz'),
                  '--manifest',str(root/'archive.tar.gz.manifest.json'),'--receipt',str(root/'ok.json')],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
    def test_freeze_detects_suite_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp)
            for dirname in ('cases','case_records','plans','reference_records','arms','suites','admission'):(work/dirname).mkdir()
            for fn in ('binding.json','prepared.json','qualified.json'):f.write(work/fn,{})
            f.write(work/'suites/W.json',{'entries':[]})
            f.write(work/'freeze.json',{'inputs':f.capsule_hashes(work)})
            f.verify_freeze(work)
            (work/'suites/W.json').write_text('{"entries":[1]}')
            with self.assertRaises(RuntimeError):f.verify_freeze(work)
    def test_full_synthetic_readout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);work=root/'work';work.mkdir()
            for dirname in ('cases','case_records','plans','reference_records','arms','suites','admission','receipts'):(work/dirname).mkdir()
            f.write(work/'binding.json',{'specification':f.read(f.PACKAGE/'scope.json')})
            f.write(work/'prepared.json',{});f.write(work/'qualified.json',{})
            c={'case_id':'qrng_n08','family':'qrng','n':8,'layers':1,'role':'width'}
            f.write(work/'case_records/qrng_n08.json',c)
            f.write(work/'plans/qrng_n08.json',{'path':[],'planner':{}})
            f.write(work/'admission/qrng_n08.json',{})
            u=f.up(4,8);v=dict(backend='numpy',threads=1)
            entries=[dict(case_id=c['case_id'],arm_id=f.arm_id(a),arm=a) for a in (u,v)]
            f.write(work/'suites/W.json',{'entries':entries,'warmups':0,'measurements':3})
            (work/'receipts/W').mkdir()
            for e in entries:
                for b in range(3):
                    factor=1 if e['arm']['backend']=='upmem' else 2
                    r=dict(case_id=c['case_id'],arm_id=e['arm_id'],arm=e['arm'],
                           status='success',accuracy_qualified=True,metrics={'job_to_state_s':factor*(b+1),
                           'prepared_call_s':factor*(b+1)},validation={'finite':True,'relative_l2':0})
                    out_path = work/'receipts/W'/f"b{b:02d}__{c['case_id']}__{e['arm_id']}.json"
                    f.write(out_path,r)
                    f.write(Path(str(out_path) + '.issued.json'),
                            dict(suite='W',case_id=c['case_id'],arm_id=e['arm_id'],arm=e['arm'],block=b,warmup=False))
            f.write(work/'freeze.json',{'inputs':f.capsule_hashes(work)})
            result=subprocess.run([sys.executable,str(f.PACKAGE/'tools/readout.py'),'--work',str(work),
                                   '--output',str(root/'readout')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            with (root/'readout/comparisons.csv').open() as fp:rows=list(csv.DictReader(fp))
            self.assertEqual(len(rows),2)
            self.assertTrue(all(float(r['ratio'])==2 for r in rows))
            with (root/'readout/largest_tested.csv').open() as fp:ls=list(csv.DictReader(fp))
            self.assertEqual(next(r for r in ls if r['family']=='qrng')['largest_fully_measured_qubits'],'8')

    def test_warmup_and_unsupported_sidecar_readout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); work = root / 'work'; work.mkdir()
            for dirname in ('cases', 'case_records', 'plans', 'reference_records', 'arms', 'suites', 'admission', 'receipts'):
                (work / dirname).mkdir()
            f.write(work / 'binding.json', {'specification': f.read(f.PACKAGE / 'scope.json')})
            f.write(work / 'prepared.json', {})
            f.write(work / 'qualified.json', {})

            c1 = {'case_id': 'qrng_n08', 'family': 'qrng', 'n': 8, 'layers': 1, 'role': 'width'}
            f.write(work / 'case_records/qrng_n08.json', c1)
            f.write(work / 'plans/qrng_n08.json', {'path': [], 'planner': {}})
            f.write(work / 'admission/qrng_n08.json', {})

            c2 = {'case_id': 'bb84_n26', 'family': 'bb84', 'n': 26, 'layers': 1, 'role': 'width'}
            f.write(work / 'case_records/bb84_n26.json', c2)
            f.write(work / 'plans/bb84_n26.json', {'path': [], 'planner': {}})
            f.write(work / 'admission/bb84_n26.json', {})

            u = f.up(4, 8)
            v = dict(backend='numpy', threads=1)
            u_unsupported = f.up(64, 24)

            entries = [
                dict(case_id=c1['case_id'], arm_id=f.arm_id(u), arm=u),
                dict(case_id=c1['case_id'], arm_id=f.arm_id(v), arm=v),
                dict(case_id=c2['case_id'], arm_id=f.arm_id(u_unsupported), arm=u_unsupported),
            ]
            warmups = 1
            measurements = 3
            f.write(work / 'suites/W.json', {'entries': entries, 'warmups': warmups, 'measurements': measurements})
            (work / 'receipts/W').mkdir()

            for e in entries:
                for b in range(warmups + measurements):
                    is_warmup = (b < warmups)
                    out_base = work / 'receipts/W' / f"b{b:02d}__{e['case_id']}__{e['arm_id']}.json"
                    if e['case_id'] == c2['case_id']:
                        raw = dict(
                            status='unsupported',
                            case_id=e['case_id'],
                            capability='prepared_wave_snapshot_limit',
                            error='unsupported execution at preflight',
                        )
                    else:
                        factor = 1 if e['arm']['backend'] == 'upmem' else 2
                        raw = dict(
                            case_id=e['case_id'],
                            arm_id=e['arm_id'],
                            arm=e['arm'],
                            status='success',
                            accuracy_qualified=True,
                            metrics={'job_to_state_s': factor * (b + 1), 'prepared_call_s': factor * (b + 1)},
                            validation={'finite': True, 'relative_l2': 0},
                        )
                    f.write(out_base, raw)
                    f.write(
                        Path(str(out_base) + '.issued.json'),
                        dict(
                            suite='W',
                            block=b,
                            warmup=is_warmup,
                            case_id=e['case_id'],
                            arm_id=e['arm_id'],
                            arm=e['arm'],
                        ),
                    )

            f.write(work / 'freeze.json', {'inputs': f.capsule_hashes(work)})
            result = subprocess.run(
                [sys.executable, str(f.PACKAGE / 'tools/readout.py'), '--work', str(work), '--output', str(root / 'readout')],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            with (root / 'readout/coverage.csv').open() as fp:
                cov = list(csv.DictReader(fp))
            self.assertEqual(len(cov), 3)
            c1_cov = [r for r in cov if r['case_id'] == c1['case_id']]
            self.assertTrue(all(r['expected'] == '3' and r['success'] == '3' and r['complete'] == 'True' for r in c1_cov))
            c2_cov = next(r for r in cov if r['case_id'] == c2['case_id'])
            self.assertEqual(c2_cov['expected'], '3')
            self.assertEqual(c2_cov['unsupported'], '3')
            self.assertEqual(c2_cov['complete'], 'False')

            with (root / 'readout/observations.csv').open() as fp:
                obs = list(csv.DictReader(fp))
            self.assertEqual(len(obs), 12)
            self.assertEqual(sum(1 for r in obs if r['warmup'] == 'True'), 3)
            self.assertEqual(sum(1 for r in obs if r['warmup'] == 'False'), 9)
            unsup_obs = [r for r in obs if r['case_id'] == c2['case_id']]
            self.assertEqual(len(unsup_obs), 4)
            for r in unsup_obs:
                self.assertEqual(r['backend'], 'upmem')
                self.assertEqual(r['arm_id'], f.arm_id(u_unsupported))
                self.assertEqual(r['dpus'], '64')

            with (root / 'readout/times.csv').open() as fp:
                times = list(csv.DictReader(fp))
            self.assertTrue(len(times) > 0)
            with (root / 'readout/comparisons.csv').open() as fp:
                comps = list(csv.DictReader(fp))
            self.assertTrue(len(comps) > 0)

    def test_missing_issued_sidecar_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); work = root / 'work'; work.mkdir()
            for dirname in ('cases', 'case_records', 'plans', 'reference_records', 'arms', 'suites', 'admission', 'receipts'):
                (work / dirname).mkdir()
            f.write(work / 'binding.json', {'specification': f.read(f.PACKAGE / 'scope.json')})
            f.write(work / 'prepared.json', {})
            f.write(work / 'qualified.json', {})
            c = {'case_id': 'qrng_n08', 'family': 'qrng', 'n': 8, 'layers': 1, 'role': 'width'}
            f.write(work / 'case_records/qrng_n08.json', c)
            f.write(work / 'plans/qrng_n08.json', {'path': [], 'planner': {}})
            f.write(work / 'admission/qrng_n08.json', {})
            u = f.up(4, 8)
            entries = [dict(case_id=c['case_id'], arm_id=f.arm_id(u), arm=u)]
            f.write(work / 'suites/W.json', {'entries': entries, 'warmups': 0, 'measurements': 1})
            (work / 'receipts/W').mkdir()
            f.write(work / 'receipts/W' / f"b00__{c['case_id']}__{entries[0]['arm_id']}.json", {'status': 'success'})
            f.write(work / 'freeze.json', {'inputs': f.capsule_hashes(work)})
            result = subprocess.run(
                [sys.executable, str(f.PACKAGE / 'tools/readout.py'), '--work', str(work), '--output', str(root / 'readout')],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('missing issued sidecar', result.stderr)

    def test_mismatched_issued_sidecar_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); work = root / 'work'; work.mkdir()
            for dirname in ('cases', 'case_records', 'plans', 'reference_records', 'arms', 'suites', 'admission', 'receipts'):
                (work / dirname).mkdir()
            f.write(work / 'binding.json', {'specification': f.read(f.PACKAGE / 'scope.json')})
            f.write(work / 'prepared.json', {})
            f.write(work / 'qualified.json', {})
            c = {'case_id': 'qrng_n08', 'family': 'qrng', 'n': 8, 'layers': 1, 'role': 'width'}
            f.write(work / 'case_records/qrng_n08.json', c)
            f.write(work / 'plans/qrng_n08.json', {'path': [], 'planner': {}})
            f.write(work / 'admission/qrng_n08.json', {})
            u = f.up(4, 8)
            entries = [dict(case_id=c['case_id'], arm_id=f.arm_id(u), arm=u)]
            f.write(work / 'suites/W.json', {'entries': entries, 'warmups': 0, 'measurements': 1})
            (work / 'receipts/W').mkdir()
            out_base = work / 'receipts/W' / f"b00__{c['case_id']}__{entries[0]['arm_id']}.json"
            f.write(out_base, {'status': 'success'})
            f.write(Path(str(out_base) + '.issued.json'), dict(suite='W', case_id=c['case_id'], arm_id=entries[0]['arm_id'], block=99, warmup=False))
            f.write(work / 'freeze.json', {'inputs': f.capsule_hashes(work)})
            result = subprocess.run(
                [sys.executable, str(f.PACKAGE / 'tools/readout.py'), '--work', str(work), '--output', str(root / 'readout')],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('issued block mismatch', result.stderr)


if __name__=='__main__':unittest.main()
