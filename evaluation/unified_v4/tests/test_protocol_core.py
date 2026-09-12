"""Synthetic contract tests. No simulated or physical benchmark is executed."""
from __future__ import annotations
import copy
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import protocol_core as p


def synthetic_rows(s,m):
    byid={c['cell_id']:c for c in m['calibration_cells']}
    out=[]
    for slot in m['calibration_slots']:
        a=byid[slot['cell_id']]['arm']
        d,t=(4,8) if a['policy']==p.FP else (2,24)
        value=1.0+abs(a['dpus']-d)+abs(a['tasklets']-t)/100+slot['block']/10000
        if slot['warmup']: value=10000.0
        out.append({**slot,'run_id':'synthetic-only','implementation_commit':s['implementation_commit'],
                    'evaluation_commit':'0'*40,'execution_binding_sha256':p.sha({'synthetic_binding':slot['cell_id']}),'issued':True,'status':'success','same_policy_passed':True,
                    'finite':True,'accuracy_qualified':a['policy']==p.FP,'prepared_call_s':value})
    return out


def synthetic_paths(m,sel):
    out=[]
    for cid in sorted({t['case_id'] for t in m['final_templates']}):
        path=[[0,1]]
        out.append(p.sealed({'case_id':cid,'selection_sha256':sel['content_sha256'],
                             'status':'selected','tensor_count':2,'path':path,
                             'path_sha256':p.sha(path),'path_id':p.sha({'synthetic_case':cid,'path':path})}))
    return out


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s=p.read(p.HERE/'protocol.json'); cls.m=p.compile_manifest(cls.s)
        cls.rows=synthetic_rows(cls.s,cls.m)
        cls.sel=p.select_topologies(cls.s,cls.m,cls.rows)
        cls.paths=synthetic_paths(cls.m,cls.sel)
        cls.fm=p.materialize_final(cls.s,cls.m,cls.sel,cls.paths)

    def test_exact_counts(self): self.assertEqual(self.m['counts'],self.s['expected'])
    def test_primary_family_membership_every_view(self):
        byid={c['case_id']:c for c in self.m['cases']}
        for view in ('T','D','A','Q'):
            self.assertEqual({byid[v['case_id']]['family'] for v in self.m['calibration_views']
                              if v['view']==view and v['cohort']=='primary'},set(p.FAMILIES))
    def test_T_full_grid(self):
        for f in p.FAMILIES:
            rr=[v for v in self.m['calibration_views'] if v['view']=='T' and v['case_id']==p.case(f,18)['case_id']]
            self.assertEqual({v['point'] for v in rr},{f'T{t}' for t in range(1,25)})
    def test_D_full_grid(self):
        for f in p.FAMILIES:
            rr=[v for v in self.m['calibration_views'] if v['view']=='D' and v['case_id']==p.case(f,18)['case_id']]
            self.assertEqual({v['point'] for v in rr},{f'D{d}/T{t}' for d in self.s['dpus'] for t in (8,24)})
    def test_Q_both_policies_same_grid(self):
        cs={c['cell_id']:c for c in self.m['calibration_cells']}
        for f in p.FAMILIES:
            rr=[cs[v['cell_id']]['arm'] for v in self.m['calibration_views'] if v['view']=='Q' and v['case_id']==p.case(f,18)['case_id']]
            self.assertEqual({(a['dpus'],a['tasklets'],a['policy']) for a in rr},
                             {(d,t,z) for d in self.s['dpus'] for t in (8,24) for z in (p.FP,p.I8)})
    def test_A_exact_cumulative_ladder(self):
        cs={c['cell_id']:c for c in self.m['calibration_cells']}
        rr=sorted([v for v in self.m['calibration_views'] if v['view']=='A' and v['case_id']=='bb84_n18'],key=lambda v:v['point'])
        actual=[cs[v['cell_id']]['arm'] for v in rr]
        expect=[p.arm(1,1,'serial_nodes_v1',False),p.arm(1,8,'serial_nodes_v1',False),
                p.arm(4,8,'serial_nodes_v1',False),p.arm(4,8,'serial_nodes_v1',True),p.arm(4,8)]
        self.assertEqual(actual,expect)
    def test_dedup_aliases_not_duplicate_observations(self):
        def vid(view,point):
            return next(v['cell_id'] for v in self.m['calibration_views'] if v['case_id']=='bb84_n18' and v['view']==view and v['point']==point)
        self.assertEqual(vid('A','A0'),vid('T','T1'))
        self.assertEqual(vid('A','A1'),vid('T','T8'))
        self.assertEqual(vid('A','A4'),vid('D','D4/T8'))
        self.assertEqual(vid('D','D4/T8'),vid('Q',f'D4/T8/{p.FP}'))
    def test_distinct_schedules_not_deduplicated(self):
        ids=[p.cell_id(p.core_identity(self.s,'calibration','hs_n18',a,'greedy'))
             for a in (p.arm(4,8,'serial_nodes_v1',False),p.arm(4,8,'serial_nodes_v1',True),p.arm(4,8))]
        self.assertEqual(len(set(ids)),3)
    def test_block_counts(self):
        self.assertEqual(dict(Counter(r['block'] for r in self.m['calibration_slots'])),
                         {0:434,1:434,2:434,3:434,4:434,5:434,6:35,7:35})
    def test_A_extra_blocks_not_reused_in_T(self):
        for v in self.m['calibration_views']:
            self.assertEqual(v['measured_blocks'],[1,2,3,4,5,6,7] if v['view']=='A' else [1,2,3,4,5])
    def test_warmup_explicit(self):
        for r in self.m['calibration_slots']: self.assertIs(r['warmup'],r['block']==0)
    def test_manifest_deterministic(self): self.assertEqual(self.m,p.compile_manifest(copy.deepcopy(self.s)))
    def test_schedule_complete_blocks(self):
        blocks=[r['block'] for r in self.m['calibration_slots']]
        self.assertEqual(blocks,sorted(blocks))
        self.assertEqual(len({r['slot_id'] for r in self.m['calibration_slots']}),2674)
    def test_metadata_affects_identity(self):
        a=p.arm(4,8); key=p.core_identity(self.s,'calibration','hs_n18',a,'greedy')
        new=copy.deepcopy(key);new['arm']['policy']=p.I8
        self.assertNotEqual(p.cell_id(key),p.cell_id(new))
    def test_primary_width_grid_and_edc(self):
        for f in p.FAMILIES:
            rr=[c for c in self.m['cases'] if c['family']==f]
            self.assertEqual(sorted(c['q'] for c in rr),self.s['width_slots'])
            for c in rr: self.assertEqual(c['n'],c['q']-(f=='edc'))
    def test_no_idle_edc_padding(self):
        for c in self.m['cases']:
            if c['family']=='edc': self.assertEqual(c['n'],2*c['parameters']['data_qubits']-1)
    def test_supplement_not_primary(self):
        self.assertTrue(all(c['cohort']=='supplementary' for c in self.m['cases'] if c['family'] in ('stress','ghz')))
    def test_all_final_routes_at_every_width(self):
        grouped=defaultdict(set)
        for t in self.m['final_templates']:grouped[t['case_id']].add(t['role'])
        self.assertEqual(len(grouped),52)
        self.assertTrue(all(v==set(self.s['final_arms']) for v in grouped.values()))
    def test_config_qualification_complete(self):
        actual={p.sha(c['arm']) for c in self.m['calibration_cells']}
        self.assertEqual(Counter(q['configuration_id'] for q in self.m['qualification']),Counter({k:2 for k in actual}))
    def test_counts_fail_closed(self):
        s=copy.deepcopy(self.s);s['expected']['benchmark_slots']+=1
        with self.assertRaises(ValueError):p.compile_manifest(s)
    def test_family_omission_fails(self):
        s=copy.deepcopy(self.s);s['primary_families'].pop()
        with self.assertRaises(ValueError):p.compile_manifest(s)
    def test_boolean_in_integer_grid_fails(self):
        s=copy.deepcopy(self.s);s['tasklets'][0]=True
        with self.assertRaises(ValueError):p.compile_manifest(s)
    def test_topology_grid_drift_fails(self):
        s=copy.deepcopy(self.s);s['topology_tasklets']=[8,16]
        with self.assertRaises(ValueError):p.compile_manifest(s)
    def test_seal_detects_change(self):
        m=copy.deepcopy(self.m);m['counts']['benchmark_slots']+=1
        with self.assertRaises(ValueError):p.check_seal(m)
    def test_exclusive_output(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'manifest';p.write_manifest(out,self.m)
            with self.assertRaises(ValueError):p.write_manifest(out,self.m)
    def test_selection_separate_for_policies(self):
        self.assertEqual(len(self.sel['selections']),14)
        for r in self.sel['selections']:
            self.assertEqual((r['selected']['dpus'],r['selected']['tasklets']), (4,8) if r['policy']==p.FP else (2,24))
    def test_selection_ignores_warmups_and_A_extra_blocks(self):
        rr=copy.deepcopy(self.rows)
        for r in rr:
            if r['block'] in (0,6,7):r['prepared_call_s']=1e-12
        changed=p.select_topologies(self.s,self.m,rr)
        for x,y in zip(self.sel['selections'],changed['selections']):self.assertEqual(x['selected'],y['selected'])
    def test_selection_keeps_int8_quality_limitation(self):
        for r in self.sel['selections']:
            if r['policy']==p.I8:self.assertFalse(r['selected']['all_accuracy_qualified'])
    def test_deterministic_ties(self):
        rr=copy.deepcopy(self.rows)
        for r in rr:r['prepared_call_s']=1.0
        sel=p.select_topologies(self.s,self.m,rr)
        self.assertTrue(all((c['selected']['dpus'],c['selected']['tasklets'])==(1,8) for c in sel['selections']))
    def test_failed_replay_not_selectable(self):
        rr=copy.deepcopy(self.rows);rr[0]['same_policy_passed']=False
        with self.assertRaises(ValueError):p.select_topologies(self.s,self.m,rr)
    def test_float_accuracy_not_ignored(self):
        rr=copy.deepcopy(self.rows)
        next(r for r in rr if r['accuracy_qualified'])['accuracy_qualified']=False
        with self.assertRaises(ValueError):p.select_topologies(self.s,self.m,rr)
    def test_mixed_run_receipts_fail(self):
        rr=copy.deepcopy(self.rows);rr[0]['run_id']='another-campaign'
        with self.assertRaises(ValueError):p.select_topologies(self.s,self.m,rr)
    def test_mixed_evaluator_receipts_fail(self):
        rr=copy.deepcopy(self.rows);rr[0]['evaluation_commit']='1'*40
        with self.assertRaises(ValueError):p.select_topologies(self.s,self.m,rr)
    def test_changed_execution_binding_fails(self):
        rr=copy.deepcopy(self.rows);rr[0]['execution_binding_sha256']='1'*64
        with self.assertRaises(ValueError):p.select_topologies(self.s,self.m,rr)
    def test_wrong_research_source_fails(self):
        rr=copy.deepcopy(self.rows);rr[0]['implementation_commit']='1'*40
        with self.assertRaises(ValueError):p.select_topologies(self.s,self.m,rr)
    def test_missing_receipt_not_ignored(self):
        with self.assertRaises(ValueError):p.select_topologies(self.s,self.m,self.rows[:-1])
    def test_duplicate_receipt_not_ignored(self):
        with self.assertRaises(ValueError):p.select_topologies(self.s,self.m,self.rows+[self.rows[0]])
    def test_final_receipt_cannot_enter_calibration(self):
        rr=copy.deepcopy(self.rows);rr[0]['phase']='final'
        with self.assertRaises(ValueError):p.select_topologies(self.s,self.m,rr)
    def test_bad_boolean_and_block_not_accepted(self):
        for key,value in (('warmup',None),('block',True),('issued','true')):
            rr=copy.deepcopy(self.rows);rr[0][key]=value
            with self.assertRaises(ValueError):p.select_topologies(self.s,self.m,rr)
    def test_nonfinite_or_nonpositive_timer_rejected(self):
        for value in (0,-1,float('nan'),float('inf'),True):
            rr=copy.deepcopy(self.rows);rr[0]['prepared_call_s']=value
            with self.assertRaises(ValueError):p.select_topologies(self.s,self.m,rr)
    def test_unsupported_timing_forbidden(self):
        rr=copy.deepcopy(self.rows);rr[0].update(status='unsupported',reason='known_limit')
        with self.assertRaises(ValueError):p.select_topologies(self.s,self.m,rr)
    def test_unsupported_candidate_retained_but_not_selected(self):
        rr=copy.deepcopy(self.rows);cid=self.sel['selections'][0]['selected']['cell_id']
        for r in rr:
            if r['cell_id']==cid:r.update(status='not_issued_unsupported',issued=False,prepared_call_s=None,reason='synthetic_limit')
        sel=p.select_topologies(self.s,self.m,rr)
        one=next(x for x in sel['selections'] if x['family']=='bb84' and x['policy']==p.FP)
        self.assertNotEqual(one['selected']['cell_id'],cid)
        self.assertFalse(next(c for c in one['candidates'] if c['cell_id']==cid)['eligible'])
    def test_fresh_final_slots_not_calibration_aliases(self):
        self.assertFalse({r['slot_id'] for r in self.fm['slots']} & {r['slot_id'] for r in self.m['calibration_slots']})
    def test_final_counts(self):
        self.assertEqual(len(self.fm['cells']),260);self.assertEqual(len(self.fm['slots']),1560)
        self.assertEqual(Counter(r['backend'] for r in self.fm['slots']),{'upmem':624,'quest32':624,'numpy':312})
    def test_shared_R_DAG(self):
        grouped=defaultdict(list)
        for c in self.fm['cells']:
            if c['arm']['backend']!='quest32':grouped[c['case_id']].append(c['selected_path_id'])
        self.assertTrue(all(len(ids)==3 and len(set(ids))==1 for ids in grouped.values()))
    def test_final_topologies_frozen_per_family_policy(self):
        for c in self.fm['cells']:
            if c['arm']['backend']=='upmem':
                self.assertEqual((c['arm']['dpus'],c['arm']['tasklets']), (4,8) if c['arm']['policy']==p.FP else (2,24))
    def test_no_R_path_does_not_switch_to_greedy(self):
        paths=copy.deepcopy(self.paths);cid=paths[0]['case_id']
        paths[0]=p.sealed({'case_id':cid,'selection_sha256':self.sel['content_sha256'],'status':'no_selected_R_path'})
        fm=p.materialize_final(self.s,self.m,self.sel,paths)
        for c in fm['cells']:
            if c['case_id']==cid:self.assertEqual(c['eligible_for_runtime_admission'],c['arm']['backend']=='quest32')
    def test_missing_final_path_record_fails(self):
        with self.assertRaises(ValueError):p.materialize_final(self.s,self.m,self.sel,self.paths[:-1])
    def test_path_cannot_use_old_selection(self):
        paths=copy.deepcopy(self.paths);v=p.check_seal(paths[0]);v['selection_sha256']='wrong';paths[0]=p.sealed(v)
        with self.assertRaises(ValueError):p.materialize_final(self.s,self.m,self.sel,paths)
    def test_path_bytes_must_match_hash(self):
        paths=copy.deepcopy(self.paths);v=p.check_seal(paths[0]);v['path']=[[1,0]];paths[0]=p.sealed(v)
        with self.assertRaises(ValueError):p.materialize_final(self.s,self.m,self.sel,paths)
    def test_pairwise_path_rules(self):
        self.assertEqual(p.pairwise_path([[0,1],[0,1]],3),[[0,1],[0,1]])
        for path in ([[0,0]],[[0,2]],[[0,True]],[]):
            with self.assertRaises(ValueError):p.pairwise_path(path,2)
    def test_R_score_and_tie_rule(self):
        rows=[dict(origin='G',eligible=True,path_id='c',score=3,path=[[0,1]],tensor_count=2),
              dict(origin='F_trace',eligible=True,path_id='b',score=2,path=[[0,1]],tensor_count=2),
              dict(origin='F_trace',eligible=True,path_id='a',score=2,path=[[1,0]],tensor_count=2)]
        self.assertEqual(p.choose_R(rows)['path_id'],'a')
    def test_R_duplicate_aliases(self):
        r=dict(origin='F_trace',eligible=True,path_id='a',score=2,path=[[0,1]],tensor_count=2)
        self.assertEqual(p.choose_R([r,r]),r)
        r2={**r,'score':1}
        with self.assertRaises(ValueError):p.choose_R([r,r2])
    def test_R_no_candidate(self):self.assertIsNone(p.choose_R([]))
    def test_R_cannot_include_U(self):
        with self.assertRaises(ValueError):p.choose_R([{'origin':'U_trace','eligible':False}])
    def test_R_invalid_score(self):
        for score in (-1,float('nan'),float('inf'),True):
            with self.assertRaises(ValueError):p.choose_R([dict(origin='G',eligible=True,path_id='a',score=score,path=[[0,1]],tensor_count=2)])
    def test_manifest_roundtrip_and_checksums(self):
        import hashlib
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)/'generated';p.write_manifest(folder,self.m)
            self.assertEqual(p.read(folder/'manifest.json'),self.m)
            for line in (folder/'SHA256SUMS').read_text().splitlines():
                dig,name=line.split('  ',1);self.assertEqual(dig,hashlib.sha256((folder/name).read_bytes()).hexdigest())


if __name__=='__main__':unittest.main()
