"""Generate self-contained Typst table fragments; no LaTeX or external Typst package."""
from __future__ import annotations
import json
from pathlib import Path
from build import FAMILIES, RESOURCE_CASES, ABLATION_CASES, require, number
from plots import ablation_id, case_label, BACKENDS, LABELS


def quote(value):
    # JSON-compatible quote, slash and newline escapes are also Typst string escapes.
    # Retain Unicode literally: Typst does not use JSON's \\uXXXX form.
    return json.dumps(str(value), ensure_ascii=False)


def fmt(value, kind='number'):
    if value is None or value == '': return '—'
    x=number(value)
    if x==0:return '0'
    if kind=='int':return str(int(x))
    if kind=='pct':return f'{x:.2f}'
    if kind=='ratio':return f'{x:.4f}'
    if abs(x)<.001 or abs(x)>=100000:return f'{x:.3e}'
    return f'{x:.4f}'


def typst_table(title, headers, rows, note):
    require(rows and all(len(row)==len(headers) for row in rows),'invalid Typst table shape')
    columns='('+','.join('1fr' for _ in headers)+',)'
    lines=['// Generated; edit synthesis code, not this file.',
           '#text(size: 10pt, weight: "bold", '+quote(title)+')', '#v(5pt)', '#{',
           '  set text(size: 8pt)', '  table(', '    columns: '+columns+',',
           '    inset: 4pt,', '    stroke: 0.35pt,',
           '    table.header(repeat: true, '+', '.join(quote(h) for h in headers)+'),']
    for row in rows:
        lines.append('    '+', '.join(quote(c) for c in row)+',')
    lines+=['  )','}', '#v(4pt)', '#text(size: 8pt, '+quote(note)+')','']
    return '\n'.join(lines)


def render_tables(r,out):
    folder=Path(out)/'tables';folder.mkdir()
    index=[]
    def emit(name,title,headers,rows,note,dataset,selector='all'):
        (folder/(name+'.typ')).write_text(typst_table(title,headers,rows,note),encoding='utf-8')
        index.append({'table_id':name,'typst':'tables/'+name+'.typ','title':title,'note':note,
                      'source_dataset':dataset,'row_selector':selector,'rows':len(rows)})
    emit('accounting','Final campaign accounting',
         ['Suite','Cells','All attempts','Warmups','Measured success','Measured unsupported'],
         [[a[k] for k in ('suite','cells','attempts','warmups','measured_success','measured_unsupported')] for a in r['accounting']],
         'Warmups are excluded from every measured summary. An unsupported attempt is not a successful physical kernel execution.', 'data/accounting.csv')
    for suite in ('T','D'):
        for cid in RESOURCE_CASES:
            cs=[c for c in r['cells'] if c['suite']==suite and c['case_id']==cid]
            cs.sort(key=lambda c:(c['tasklets'],c['dpus']))
            rows=[]
            for c in cs:
                cmp=next(x for x in r['comparisons'] if x['suite']==suite and x['case_id']==cid
                         and x['denominator']==c['arm_id'] and x['metric']=='prepared_call_s')
                rows.append([c['dpus'],c['tasklets'],fmt(c['prepared_call_s']),fmt(cmp['ratio'],'ratio'),
                             '['+fmt(cmp['descriptive_low'],'ratio')+', '+fmt(cmp['descriptive_high'],'ratio')+']',
                             fmt(100*cmp['parallel_efficiency'],'pct')])
            emit(suite.lower()+'_'+cid,case_label(cid)+' — '+('tasklet' if suite=='T' else 'DPU')+' scaling',
                 ['DPUs','Tasklets','Prepared (s)','Speedup','Descriptive 95% interval','Efficiency (%)'],rows,
                 'All measured grid points. Baseline is T1 or D1 at the same fixed T. Five measured blocks. No timing-optimal resource claim.',
                 'data/'+('tasklets' if suite=='T' else 'dpus')+'.csv; data/comparisons.csv',cid)
    emit('best_resources','Descriptive resource minima',
         ['Suite / case','Fixed T','Best observed count','Endpoint','Endpoint speedup','Endpoint efficiency (%)'],
         [[b['suite']+' / '+case_label(b['case_id']),b['fixed_tasklets'] or 'sweep',b['best_observed_resource'],
           b['endpoint'],fmt(b['endpoint_ratio_vs_one'],'ratio'),fmt(100*b['endpoint_efficiency'],'pct')] for b in r['best_resources']],
         'Minimum prepared-call median, ties broken by smaller resource count. Selected after observation for description only; no independent optimum confirmation and no change to the fixed width-study configuration.', 'data/best_resources.csv')
    for cid in ABLATION_CASES:
        cs=sorted([c for c in r['ablations'] if c['case_id']==cid],key=ablation_id)
        emit('ablation_'+cid,case_label(cid)+' — matched final executor',
             ['Arm','D / T','Schedule / fusion','Prepared (s)','Raw MAD (s)','Job-to-state (s)'],
             [['A'+str(ablation_id(c)),f'{c["dpus"]} / {c["tasklets"]}',
               ('DAG' if c['schedule']=='static_dag_waves_v1' else 'serial')+(' / fused' if c['fuse'] else ' / unfused'),
               fmt(c['prepared_call_s']),fmt(c['prepared_call_s_mad']),fmt(c['job_to_state_s'])] for c in cs],
             'Seven measured blocks. All arms already use WRAM panels, packed waves, float32 and the same greedy path.', 'data/ablations.csv',cid)
        qs=[c for c in r['comparisons'] if c['suite']=='A' and c['case_id']==cid and c['metric']=='prepared_call_s']
        emit('ablation_effects_'+cid,case_label(cid)+' — isolated transitions',
             ['Comparison','Time ratio','Descriptive 95% interval','Time reduction (%)'],
             [[c['comparison'],fmt(c['ratio'],'ratio'),f'[{fmt(c["descriptive_low"],"ratio")}, {fmt(c["descriptive_high"],"ratio")}]',
               fmt(c['time_reduction_pct'],'pct')] for c in qs],
             'Ratio <1 and negative time reduction are regressions. Combined A0/A4 is a directly observed contrast.', 'data/comparisons.csv',cid+'/A/prepared_call_s')
    for fam in FAMILIES:
        cs=[c for c in r['width'] if c['family']==fam]
        rows=[]
        for n in sorted({c['n'] for c in cs}):
            q={c['arm_id']:c for c in cs if c['n']==n}
            u=q[BACKENDS[0]]; cpu=q['quest32_p8']
            cmp=next((c for c in r['cpu_comparison'] if c['family']==fam and c['n']==n
                      and c['numerator']=='quest32_p8' and c['metric']=='job_to_state_s'),None)
            rows.append([n,fmt(u.get('job_to_state_s')),fmt(cpu.get('job_to_state_s')),
                         fmt(q.get('quest32_p1',{}).get('job_to_state_s')),fmt(q.get('numpy_p1',{}).get('job_to_state_s')),
                         fmt(cmp['ratio'],'ratio') if cmp else 'unsupported'])
        emit('width_'+fam,fam.upper()+' — job-to-state comparison',
             ['Total qubits','UPMEM (s)','QuEST P8 (s)','QuEST P1 (s)','NumPy P1 (s)','P8 / UPMEM'],rows,
             'UPMEM D64/T24, greedy path; QuEST single precision. Dash in CPU anchor columns means not planned. Unsupported UPMEM endpoint is retained, not replaced by zero time.', 'data/width.csv; data/cpu_comparison.csv',fam)
    emit('frontiers','Largest qualified declared-grid points',
         ['Family','UPMEM','QuEST P8','QuEST P1','NumPy P1'],
         [[fam.upper()]+[next(c['largest_fully_measured_qubits'] for c in r['frontiers'] if c['family']==fam and c['arm_id']==aid) for aid in BACKENDS] for fam in FAMILIES],
         'These are grid outcomes, not absolute capacity maxima. P1/NumPy anchors end earlier by design. UPMEM endpoints were admission-rejected.', 'data/frontiers.csv')
    emit('circuits','Circuit and fixed-path geometry',
         ['Case','Total qubits','Gates','Input tensors','DAG nodes','Output MiB'],
         [[c['case_id'],c['n'],c['gate_count'],c['tensor_count'],c['node_count'],fmt(c['statevector_mib'])] for c in r['circuits']],
         'Includes all declared widths, including unsupported execution points. EDC counts data and syndrome wires. Qubit count alone does not measure contraction difficulty.', 'data/circuits.csv')
    for metric,suffix in [('session_inclusive_s','inclusive'),('total_wall_s','steady')]:
        q=[c for c in r['p6_aggregates'] if c['metric']==metric]
        emit('p6_'+suffix,'P6 accepted '+suffix+' aggregate contrasts',
             ['Group','Contrast','Ratio','Descriptive 95% interval','Time reduction (%)'],
             [[c['group'],c['contrast'],fmt(c['ratio'],'ratio'),
               f'[{fmt(c["paired_bootstrap_low"],"ratio")}, {fmt(c["paired_bootstrap_high"],"ratio")}]',fmt(c['time_reduction_pct'],'pct')] for c in q],
             'Original family-balanced P6 statistics imported unchanged. No refit, pooling or new confidence procedure; R/U near one is not equivalence.', 'data/p6_aggregates.csv',metric)
    emit('p6_search','P6 offline search cost',
         ['Cell','Method','Proposals','Eligible paths','Search wall (s)'],
         [[c['cell_id'].split('_')[0].upper()+' / '+c['cell_id'].split('/')[-1],c['method'],c['proposals'],c['unique_eligible_paths'],fmt(c['search_wall_s'])] for c in r['p6_search']],
         'Offline search cost is separate from physical execution. One paired search-seed schedule, not repeated optimizer trials.', 'data/p6_search.csv')
    emit('quantization','Software quantization characterization',
         ['Circuit','Contractions','L2 vs float32 (%)','L2 vs complex128 (%)','Logical compression'],
         [[c['circuit_id'],c['contraction_count'],fmt(c['relative_l2_percent']),fmt(c['error_vs_complex128_percent']),fmt(c['nominal_compression_ratio'],'ratio')] for c in r['quantization']],
         'These CSVs characterize software policy replay, not physical timing. Logical compression is not measured transfer reduction. The separate historical physical study established same-policy replay and workload-dependent error.', 'data/quantization.csv')
    emit('mechanisms','Completed investigations and negative findings',
         ['Investigation','Recorded outcome','Disposition / qualification'],
         [[c['module'].replace('_',' '),c['recorded_finding'],c['disposition']+'; '+c['synthesis_treatment']] for c in r['mechanisms']],
         'Historical narratives are not recomputed raw observations. Chat-context transcriptions are explicitly unverified numeric context. Do not multiply these heterogeneous studies into a cumulative speedup.', 'data/mechanisms.csv')
    # Standalone layout inspection; fragments remain usable in the user's manuscript.
    lines=['#set page(paper: "a4", margin: 18mm)', '#set text(font: "DejaVu Sans", size: 9pt)',
           '= Thesis synthesis — table inspection', 'Generated tables. Source data and qualifications accompany every table.', '']
    for entry in index:
        lines+=['#pagebreak(weak: true)', '#include '+quote(entry['typst']), '']
    (Path(out)/'gallery.typ').write_text('\n'.join(lines),encoding='utf-8')
    return index
