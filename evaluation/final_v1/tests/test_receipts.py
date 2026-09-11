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
                    r=dict(suite='W',case_id=c['case_id'],arm_id=e['arm_id'],arm=e['arm'],block=b,warmup=False,
                           status='success',accuracy_qualified=True,metrics={'job_to_state_s':factor*(b+1),
                           'prepared_call_s':factor*(b+1)},validation={'finite':True,'relative_l2':0})
                    f.write(work/'receipts/W'/f"b{b:02d}__{c['case_id']}__{e['arm_id']}.json",r)
            f.write(work/'freeze.json',{'inputs':f.capsule_hashes(work)})
            result=subprocess.run([sys.executable,str(f.PACKAGE/'tools/readout.py'),'--work',str(work),
                                   '--output',str(root/'readout')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            with (root/'readout/comparisons.csv').open() as fp:rows=list(csv.DictReader(fp))
            self.assertEqual(len(rows),2)
            self.assertTrue(all(float(r['ratio'])==2 for r in rows))
            with (root/'readout/largest_tested.csv').open() as fp:ls=list(csv.DictReader(fp))
            self.assertEqual(next(r for r in ls if r['family']=='qrng')['largest_fully_measured_qubits'],'8')


if __name__=='__main__':unittest.main()
