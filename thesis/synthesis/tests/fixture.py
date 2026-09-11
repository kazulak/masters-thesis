"""SYNTHETIC full-shape test campaign. Never used by the production builder."""
from collections import defaultdict
import copy
import json
import math
from pathlib import Path
import statistics
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import build as b


def up(d,t,s='static_dag_waves_v1',f=True):
    return dict(backend='upmem',dpus=d,tasklets=t,threads=1,policy='split_complex_float32_v1',schedule=s,fuse=f,geometry='panel_only_v1')


def aid(a):
    if a['backend']!='upmem':return a['backend']+'_p'+str(a['threads'])
    return f'upmem_d{a["dpus"]}_t{a["tasklets"]}_{a["schedule"]}_{int(a["fuse"])}_f32'


def campaign():
    config=json.loads((b.HERE/'SOURCES.json').read_text())
    data={k:[] for k in ('final_observations','final_coverage','final_times','final_comparisons','final_circuits','final_contractions','final_largest_tested','final_plan_facts','p6_methods','p6_contrasts','p6_aggregates','p6_search','quantization','mechanisms','history_sources')}
    data['scope']={'bootstrap_draws':10000,'seed':20260911,'validation':{'fp32_relative_l2_max':1e-5,'fp32_norm_drift_max':2e-5}}
    data['binding']={'host':'SYNTHETIC TEST FIXTURE','cpu_cpus':list(range(8)),'capacity':64}
    data['historical_bindings']={}
    data['p6_diagnostics']={'features':['H','P','N','M','W'],'pooled_total_feature_correlations':[[1 if i==j else .2 for j in range(5)] for i in range(5)],'interpretation':'SYNTHETIC diagnostic fixture'}
    cases={}
    for family in b.FAMILIES:
        for slot in (8,12,16,18,20,22,24,26):
            n=slot-1 if family=='edc' else slot
            cid=f'{family}_n{n:02d}'
            cases[cid]=dict(case_id=cid,family=family,n=str(n),layers='1',role='width',width_slot=str(slot),
                 tensor_count=str(2*n),node_count=str(2*n-1),gate_counts=json.dumps({'h':n}),
                 full_state_c64_bytes=str(8*2**n),full_state_c128_bytes=str(16*2**n),
                 largest_intermediate_elements=str(2**n),source_row=len(cases)+2)
    cases['stress_n16_l2']=dict(case_id='stress_n16_l2',family='stress',n='16',layers='2',role='resource',
        tensor_count='120',node_count='119',gate_counts=json.dumps({'h':16,'rz':48,'cx':30}),
        full_state_c64_bytes=str(8*2**16),full_state_c128_bytes=str(16*2**16),largest_intermediate_elements=str(2**16),source_row=50)
    data['final_circuits']=list(cases.values())
    for cid,c in cases.items():
        data['final_contractions'].append(dict(case_id=cid,node_id='c0',B='1',M='1',K='2',N=str(2**int(c['n'])),real_macs=str(8*2**int(c['n'])),source_row=len(data['final_contractions'])+2))
    serial='serial_nodes_v1'
    suites={s:{'entries':[],'warmups':1,'measurements':7 if s=='A' else 5} for s in 'TDAW'}
    def add(s,c,a):suites[s]['entries'].append(dict(case_id=c,arm=a,arm_id=aid(a)))
    for cid in b.RESOURCE_CASES:
        for t in range(1,25):add('T',cid,up(1,t,serial,False))
        for d in (1,2,4,8,16,32,64):
            for t in (8,24):add('D',cid,up(d,t))
    aseq=(up(1,1,serial,False),up(1,8,serial,False),up(4,8,serial,False),up(4,8,serial,True),up(4,8))
    for cid in b.ABLATION_CASES:
        for a in aseq:add('A',cid,a)
    for cid,c in cases.items():
        if c['role']!='width':continue
        add('W',cid,up(64,24));add('W',cid,dict(backend='quest32',threads=8))
        if int(c['width_slot']) in (8,12,16,18):
            add('W',cid,dict(backend='quest32',threads=1));add('W',cid,dict(backend='numpy',threads=1))
    gs={};cell_ok={}
    for s,d in suites.items():
        data['suite_'+s]=d
        for e in d['entries']:
            a=e['arm'];cid=e['case_id'];key=(s,cid,e['arm_id']);rows=[]
            unsupported=s=='W' and a['backend']=='upmem' and cid in config['unsupported_cases']
            cell_ok[key]=not unsupported
            for block in range(1+d['measurements']):
                row=dict(suite=s,case_id=cid,arm_id=e['arm_id'],block=str(block),warmup=str(block==0),
                    status='unsupported' if unsupported else 'success',accuracy_qualified='' if unsupported else 'True',
                    **{k:str(v) for k,v in a.items()},source_row=len(data['final_observations'])+2)
                if not unsupported:
                    n=int(cases[cid]['n']);base=(n/8+1)*(1+.012*block)
                    cost=(.4+5/(a['tasklets']*min(a['dpus'],8))+.006*a['dpus']) if a['backend']=='upmem' else .02/a['threads']
                    # Large warmup sentinel catches accidental inclusion in summaries.
                    x=base*cost*(10 if block==0 else 1)
                    row.update(job_to_state_s=str(x+.05),prepared_call_s=str(x),session_inclusive_s=str(x*.95),kernel_s=str(x*.4),
                      relative_l2='1e-7',max_abs='1e-8',norm_drift='1e-7',probability_norm_drift='2e-7',fidelity='.999999',
                      call_actual_multithreading=str(a['backend']=='quest32' and a['threads']>1))
                    if a['backend'] in ('upmem','numpy'):row['steady_s']=str(x*.7)
                    if a['backend']=='upmem':row.update(session_open_s=str(x*.2),session_close_s=str(x*.05),h2d_s=str(x*.07),d2h_s=str(x*.08),h2d_bytes=str(12*2**n),d2h_bytes=str(8*2**n))
                rows.append(row);data['final_observations'].append(row)
            gs[key]=rows[1:]
            cov=dict(suite=s,case_id=cid,arm_id=e['arm_id'],expected=str(d['measurements']),success=str(0 if unsupported else d['measurements']),unsupported=str(d['measurements'] if unsupported else 0),
                     complete=str(not unsupported),quality_qualified=str(not unsupported),source_row=len(data['final_coverage'])+2)
            for k in ('not_attempted','not_collected','timeout','memory_limit','failure'):cov[k]='0'
            data['final_coverage'].append(cov)
            if not unsupported:
                for m in b.METRICS:
                    if m not in rows[1]:continue
                    median,mad=b.median_mad([float(r[m]) for r in rows[1:]])
                    data['final_times'].append(dict(suite=s,case_id=cid,arm_id=e['arm_id'],metric=m,median=str(median),raw_mad=str(mad),count=str(d['measurements']),quality_qualified='True',source_row=len(data['final_times'])+2))
            if a['backend']=='upmem':
                data['final_plan_facts'].append(dict(case_id=cid,arm_id=e['arm_id'],plan_facts_json=json.dumps({'status':'unsupported' if unsupported else 'admitted','reason':'synthetic admission limit' if unsupported else None}),source_row=len(data['final_plan_facts'])+2))
    def pair(s,c,x,y,label,resource=None):
        if not cell_ok[(s,c,x)] or not cell_ok[(s,c,y)]:return
        for m in ('job_to_state_s','prepared_call_s','session_inclusive_s'):
            if s=='W' and m=='session_inclusive_s':continue
            xs=[float(r[m]) for r in gs[s,c,x]];ys=[float(r[m]) for r in gs[s,c,y]]
            ratio=statistics.median(xs)/statistics.median(ys)
            lo,hi=b.bootstrap(xs,ys,10000,20260911)
            data['final_comparisons'].append(dict(suite=s,case_id=c,numerator=x,denominator=y,comparison=label,metric=m,ratio=str(ratio),descriptive_low=str(lo),descriptive_high=str(hi),denominator_time_reduction_percent=str(100*(1-1/ratio)),paired_blocks=str(len(xs)),equal_quality_claim='True',parallel_efficiency=str(ratio/resource) if resource else '',source_row=len(data['final_comparisons'])+2))
    for s,d in suites.items():
        for cid in sorted({e['case_id'] for e in d['entries']}):
            es=[e for e in d['entries'] if e['case_id']==cid]
            if s=='T':
                for e in es:pair(s,cid,aid(up(1,1,serial,False)),e['arm_id'],'tasklet_scaling',e['arm']['tasklets'])
            if s=='D':
                for e in es:pair(s,cid,aid(up(1,e['arm']['tasklets'])),e['arm_id'],'dpu_scaling',e['arm']['dpus'])
            if s=='A':
                for a1,a2,label in zip(aseq,aseq[1:],('tasklets','dpus','complex_fusion','dag_concurrency')):pair(s,cid,aid(a1),aid(a2),label)
                pair(s,cid,aid(aseq[0]),aid(aseq[-1]),'matched_combined_executor')
            if s=='W':
                for e in es:
                    if e['arm']['backend']!='upmem':pair(s,cid,e['arm_id'],aid(up(64,24)),'cpu_vs_upmem')
    for a in (aid(up(64,24)),'quest32_p8','quest32_p1','numpy_p1'):
        for fam in b.FAMILIES:
            ns=[int(cases[c]['n']) for s,c,arm in gs if s=='W' and arm==a and cases[c]['family']==fam and cell_ok[s,c,arm]]
            data['final_largest_tested'].append(dict(family=fam,arm_id=a,largest_fully_measured_qubits=str(max(ns)),claim='synthetic fixture',source_row=len(data['final_largest_tested'])+2))
    pmap={}
    for fam in b.FAMILIES:
        for topo in ('1dpu_t8','4dpu_t8'):
            cid=fam+'_test/'+topo
            for method,v in zip('GFRU',(1.2,1.04,1.0,1.0)):
                row=dict(cell_id=cid,family=fam.upper(),topology_id=topo,method=method,path_id=('RU' if method in 'RU' else method),source_row=len(data['p6_methods'])+2)
                for field,scale in [('session_inclusive_s',1),('total_wall_s',.7),('session_open_s',.2),('session_close_s',.1),('kernel_s',.3)]:row[field+'_median']=str(v*scale)
                data['p6_methods'].append(row);pmap[cid,method]=row
            for contrast in ('G/F','F/R','R/U','F/U','G/R','G/U'):
                for m in ('session_inclusive_s','total_wall_s'):
                    x,y=contrast.split('/');ratio=float(pmap[cid,x][m+'_median'])/float(pmap[cid,y][m+'_median'])
                    data['p6_contrasts'].append(dict(cell_id=cid,family=fam.upper(),topology_id=topo,contrast=contrast,metric=m,ratio_of_medians=str(ratio),denominator_time_reduction_pct=str(100*(1-1/ratio)),paired_bootstrap_low=str(ratio*.99),paired_bootstrap_high=str(ratio*1.01),same_selected_path=str(pmap[cid,x]['path_id']==pmap[cid,y]['path_id']),source_row=len(data['p6_contrasts'])+2))
            for method in ('F','U'):data['p6_search'].append(dict(cell_id=cid,method=method,proposals='128',unique_eligible_paths='128',search_wall_s='8.125',source_row=len(data['p6_search'])+2))
    for group in ('all','1dpu_t8','4dpu_t8'):
        for contrast in ('G/F','F/R','R/U','F/U','G/R','G/U'):
            for m in ('session_inclusive_s','total_wall_s'):
                ps=[r for r in data['p6_contrasts'] if r['contrast']==contrast and r['metric']==m and (group=='all' or r['topology_id']==group)]
                ratio=math.exp(statistics.mean(math.log(float(r['ratio_of_medians'])) for r in ps))
                data['p6_aggregates'].append(dict(group=group,contrast=contrast,metric=m,cells=str(len(ps)),families='6',family_balanced_geometric_ratio=str(ratio),paired_bootstrap_low=str(ratio*.99),paired_bootstrap_high=str(ratio*1.01),source_row=len(data['p6_aggregates'])+2))
    data['quantization']=b.csv_rows((Path(__file__).parent/'fixtures/real_quantization.csv').read_bytes(),'quantization')
    for i in range(32):data['mechanisms'].append(dict(module=f'synthetic_{i}',recorded_finding='Synthetic historical fixture, not a measurement.',disposition='mixed',source_id='synthetic',provenance_class='recorded_summary_not_recomputed',source_row=i+2))
    return data,config
