"""Deterministic publication figures from verified synthesis rows. No data selection by result."""
from __future__ import annotations
import hashlib
import json
import platform
import importlib.metadata
import zlib
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from build import FAMILIES, RESOURCE_CASES, ABLATION_CASES, require, number

BACKENDS = ('upmem_d64_t24_static_dag_waves_v1_1_f32', 'quest32_p8', 'quest32_p1', 'numpy_p1')
LABELS = ('UPMEM D64/T24', 'QuEST P8', 'QuEST P1', 'NumPy same-DAG P1')


def case_label(cid):
    return cid.replace('_n', ' ').replace('_l2', ' L2').upper()


def ablation_id(c):
    if c['dpus']==1 and c['tasklets']==1: return 0
    if c['dpus']==1: return 1
    if not c['fuse']: return 2
    if c['schedule']=='serial_nodes_v1': return 3
    return 4


def interval_curve(ax, x, mid, lo, hi, label, marker='o'):
    line, = ax.plot(x, mid, marker=marker, markersize=4, linewidth=1.2, label=label)
    ax.vlines(x, lo, hi, color=line.get_color(), linewidth=.8)


def render(r, source, out):
    matplotlib.rcdefaults()
    matplotlib.rcParams.update({'font.family':'DejaVu Sans', 'font.size':9,
        'axes.titlesize':11, 'axes.labelsize':10, 'legend.fontsize':8,
        'svg.hashsalt':'masters-thesis-synthesis-v1', 'svg.fonttype':'path',
        'savefig.dpi':180, 'figure.dpi':100})
    folder=Path(out)/'figures'; folder.mkdir()
    index=[]
    def figure():
        return plt.subplots(figsize=(7.2,4.6))
    def emit(fig, name, caption, dataset, selector):
        require(any(ax.has_data() for ax in fig.axes), 'refusing empty figure '+name)
        for ax in fig.axes:
            if ax.get_legend_handles_labels()[0]:
                if name.startswith('p6_aggregate_'):
                    ax.legend(loc='upper center', bbox_to_anchor=(.5,-.18), ncol=3)
                else:
                    ax.legend()
        fig.tight_layout(pad=1.2)
        fig.savefig(folder/(name+'.svg'),metadata={'Date':None,'Creator':'thesis synthesis v1'})
        svg=folder/(name+'.svg')
        svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n',encoding='utf-8')
        fig.savefig(folder/(name+'.png'),metadata={'Software':'thesis synthesis v1'})
        plt.close(fig)
        index.append({'figure_id':name,'svg':'figures/'+name+'.svg','png':'figures/'+name+'.png',
                      'caption':caption,'source_dataset':dataset,'row_selector':selector})
    def parity(ax):
        ax.axhline(1,linestyle='--',linewidth=.7)
    # T and D use prepared-call as the primary resource scope. Kernel timer is diagnostic.
    for suite in ('T','D'):
        field='tasklets' if suite=='T' else 'dpus'
        for cid in RESOURCE_CASES:
            rs=[c for c in r['cells'] if c['suite']==suite and c['case_id']==cid and c['quality_qualified']]
            fixed=[None] if suite=='T' else [8,24]
            fig,ax=figure()
            for t in fixed:
                q=sorted([c for c in rs if t is None or c['tasklets']==t], key=lambda c:c[field])
                label='Prepared call' if t is None else f'Prepared call, T{t}'
                ax.errorbar([c[field] for c in q],[c['prepared_call_s'] for c in q],
                            yerr=[c['prepared_call_s_mad'] for c in q],marker='o',markersize=4,label=label)
                ax.plot([c[field] for c in q],[c['kernel_s'] for c in q],linestyle=':',marker='x',
                        label='SDK kernel timer' if t is None else f'SDK kernel timer, T{t}')
            ax.set(xlabel='Tasklets (one DPU)' if suite=='T' else 'DPUs (one rank)',ylabel='Time (s)',title=case_label(cid))
            if suite=='D': ax.set_xscale('log',base=2); ax.set_xticks([1,2,4,8,16,32,64],labels=['1','2','4','8','16','32','64'])
            emit(fig,f'{suite.lower()}_{cid}_time','Median prepared-call time with raw MAD; SDK launch/wait kernel timer is shown separately, not an arithmetic-only timer or an additive component.','data/tasklets.csv' if suite=='T' else 'data/dpus.csv',cid)
            for kind in ('speedup','efficiency'):
                fig,ax=figure()
                for t in fixed:
                    q=sorted([c for c in rs if t is None or c['tasklets']==t],key=lambda c:c[field])
                    ids={c['arm_id']:c for c in q}
                    z=sorted([c for c in r['comparisons'] if c['suite']==suite and c['case_id']==cid
                              and c['metric']=='prepared_call_s' and c['denominator'] in ids],
                             key=lambda c:ids[c['denominator']][field])
                    x=[ids[c['denominator']][field] for c in z]
                    scale=[100/v if kind=='efficiency' else 1 for v in x]
                    interval_curve(ax,x,[c['ratio']*s for c,s in zip(z,scale)],
                                   [c['descriptive_low']*s for c,s in zip(z,scale)],
                                   [c['descriptive_high']*s for c,s in zip(z,scale)],
                                   'T sweep' if t is None else f'T{t}')
                ax.axhline(100 if kind=='efficiency' else 1,linestyle='--',linewidth=.7)
                ax.set(xlabel='Tasklets' if suite=='T' else 'DPUs',
                       ylabel='Parallel efficiency (%)' if kind=='efficiency' else 'Baseline / alternative time',
                       title=case_label(cid)+' — prepared call')
                if suite=='D': ax.set_xscale('log',base=2); ax.set_xticks([1,2,4,8,16,32,64],labels=['1','2','4','8','16','32','64'])
                emit(fig,f'{suite.lower()}_{cid}_{kind}','Accepted paired-block descriptive intervals. Baseline is one tasklet or one DPU at the same fixed tasklet count. Efficiency is speedup divided by resource count; no optimal-count claim.',
                     'data/comparisons.csv',f'{suite}/{cid}/prepared_call_s')
    # Matched A0..A4, including negative increments.
    transitions=('tasklets','dpus','complex_fusion','dag_concurrency','matched_combined_executor')
    for cid in ABLATION_CASES:
        cs=sorted([c for c in r['ablations'] if c['case_id']==cid],key=ablation_id)
        fig,ax=figure()
        ax.bar(range(5),[c['prepared_call_s'] for c in cs],yerr=[c['prepared_call_s_mad'] for c in cs])
        ax.set_xticks(range(5),labels=['A0','A1','A2','A3','A4'])
        ax.set(ylabel='Prepared-call time (s), median ± raw MAD',title=case_label(cid))
        emit(fig,f'ablation_{cid}_time','A0 D1/T1 serial unfused; A1 D1/T8; A2 D4/T8; A3 fused; A4 static DAG waves. All use the panel kernel, float32 and the same greedy path.', 'data/ablations.csv',cid)
        cs=sorted([c for c in r['comparisons'] if c['suite']=='A' and c['case_id']==cid and c['metric']=='prepared_call_s'],key=lambda c:transitions.index(c['comparison']))
        fig,ax=figure()
        y=np.arange(len(cs))
        ax.hlines(y,[c['descriptive_low'] for c in cs],[c['descriptive_high'] for c in cs])
        ax.plot([c['ratio'] for c in cs],y,'o')
        ax.axvline(1,linestyle='--',linewidth=.7)
        ax.set_yticks(y,labels=['A0/A1: tasklets','A1/A2: DPUs','A2/A3: fusion','A3/A4: DAG','A0/A4: combined'])
        ax.set(xlabel='Baseline / alternative time',title=case_label(cid)+' — matched effects')
        ax.set_xscale('log');ax.invert_yaxis()
        emit(fig,f'ablation_{cid}_ratios','Accepted descriptive intervals; <1 is a regression. Combined A0/A4 is a directly measured contrast, not multiplication across historical studies.', 'data/comparisons.csv',cid+'/A/prepared_call_s')
    for cid in ABLATION_CASES:
        fig,ax=figure()
        for part,label in [('session_open_s','Opening'),('steady_s','Steady execution'),('session_close_s','Closing')]:
            q=sorted([c for c in r['lifecycle'] if c['suite']=='A' and c['case_id']==cid and c['component']==part],key=ablation_id)
            ax.errorbar(range(5),[100*c['median_per_sample_share'] for c in q],
                        yerr=[100*c['raw_mad_share'] for c in q],marker='o',label=label)
        ax.set_xticks(range(5),labels=['A0','A1','A2','A3','A4'])
        ax.set(ylabel='Median per-attempt lifecycle share (%)',title=case_label(cid)+' — lifecycle composition')
        emit(fig,'lifecycle_'+cid,'Shares are computed per attempt before median/MAD. These three lifecycle components sum per sample, but their medians need not sum to 100%; hence no stacked median decomposition is used.', 'data/lifecycle.csv',cid+'/A')
    for family in FAMILIES:
        cs=[c for c in r['width'] if c['family']==family]
        fig,ax=figure()
        for aid,label in zip(BACKENDS,LABELS):
            q=sorted([c for c in cs if c['arm_id']==aid and c['quality_qualified']],key=lambda c:c['n'])
            ax.errorbar([c['n'] for c in q],[c['job_to_state_s'] for c in q],yerr=[c['job_to_state_s_mad'] for c in q],marker='o',markersize=4,label=label)
        bad=sorted(c['n'] for c in cs if c['backend']=='upmem' and not c['quality_qualified'])
        for n in bad:
            ax.axvline(n,linestyle=':',linewidth=.8)
            ax.text(n,.96,'UPMEM unsupported',rotation=90,va='top',ha='right',transform=ax.get_xaxis_transform(),fontsize=7)
        ax.set(xlabel='Total allocated qubits',ylabel='Job-to-state time (s), median ± raw MAD',title=family.upper())
        ax.set_yscale('log')
        emit(fig,'width_'+family,'Same preloaded circuit to owned complete statevector, excluding validation and serialization. UPMEM is fixed D64/T24 with greedy planning. CPU anchors end by design; rejected UPMEM endpoints are marked, not plotted as times.', 'data/width.csv',family)
        fig,ax=figure()
        for aid,label in zip(BACKENDS[1:],LABELS[1:]):
            q=sorted([c for c in r['cpu_comparison'] if c['family']==family and c['numerator']==aid and c['metric']=='job_to_state_s'],key=lambda c:c['n'])
            interval_curve(ax,[c['n'] for c in q],[c['ratio'] for c in q],
                           [c['descriptive_low'] for c in q],[c['descriptive_high'] for c in q],label)
        parity(ax);ax.set_yscale('log')
        ax.set(xlabel='Total allocated qubits',ylabel='CPU time / UPMEM time',title=family.upper()+' — job-to-state comparison')
        emit(fig,'cpu_ratio_'+family,'Values below one favour the CPU; values above one favour UPMEM. Only mutually qualified paired cells enter ratios. QuEST P8 means eight requested CPU threads, not a globally best or proven SOTA simulator.', 'data/cpu_comparison.csv',family+'/job_to_state_s')
        fig,ax=figure()
        q=sorted([c for c in cs if c['backend']=='upmem' and c['quality_qualified']],key=lambda c:c['n'])
        for key,label in [('h2d_bytes','H2D payload'),('d2h_bytes','D2H payload')]:
            ax.plot([c['n'] for c in q],[c[key]/2**20 for c in q],marker='o',label=label)
        ax.plot([c['n'] for c in q],[8*2**c['n']/2**20 for c in q],linestyle=':',label='Full complex64 output size')
        ax.set_yscale('log')
        ax.set(xlabel='Total allocated qubits',ylabel='MiB',title=family.upper()+' — application-visible movement')
        emit(fig,'traffic_'+family,'Median application-visible H2D and D2H bytes, not total physical bus traffic. Output storage is shown only as a size reference; it is not another measured transfer.', 'data/width.csv',family+'/UPMEM')
    # Resource/circuit context and supported frontier, without pretending anchors failed.
    fig,ax=figure()
    for i,(aid,label) in enumerate(zip(BACKENDS,LABELS)):
        q=[next(c for c in r['frontiers'] if c['family']==fam and c['arm_id']==aid) for fam in FAMILIES]
        ax.scatter([c['largest_fully_measured_qubits'] for c in q],np.arange(6)+(i-1.5)*.14,label=label)
    ax.set_yticks(range(6),labels=[s.upper() for s in FAMILIES]);ax.invert_yaxis()
    ax.set(xlabel='Largest qualified point in the declared grid (qubits)',title='Measured frontiers, not absolute capacity limits')
    emit(fig,'frontiers','UPMEM endpoints reflect recorded admission limits. QuEST P8 reached its planned grid endpoint. QuEST P1 and NumPy stop at their smaller planned anchor grids; these are not capacity failures.', 'data/frontiers.csv','all')
    for key,label,name in [('tensor_count','Input tensors','tensor_counts'),('real_macs','Four-real-product MAC count','work_counts')]:
        fig,ax=figure()
        for fam in FAMILIES:
            q=sorted([c for c in r['circuits'] if c['family']==fam and c['role']=='width'],key=lambda c:c['n'])
            ax.plot([c['n'] for c in q],[number(c[key]) for c in q],marker='o',label=fam.upper())
        if key=='real_macs':ax.set_yscale('log')
        ax.set(xlabel='Total allocated qubits',ylabel=label,title='Fixed greedy tensor-network geometry')
        emit(fig,name,'Deterministic circuit/plan facts, not measured performance or a causal roofline model. Different families have different structure at the same qubit count.', 'data/circuits.csv','role=width')
    for key,threshold,name in [('relative_l2_max',source['scope']['validation']['fp32_relative_l2_max'],'relative_l2'),
                              ('norm_drift_max',source['scope']['validation']['fp32_norm_drift_max'],'norm_drift')]:
        fig,ax=figure()
        for aid,label in zip(BACKENDS,LABELS):
            vals=[]
            for fam in FAMILIES:
                q=[c for c in r['accuracy'] if c['suite']=='W' and c['family']==fam and c['arm_id']==aid]
                vals.append(max(number(c[key]) for c in q))
            ax.plot(range(6),vals,marker='o',label=label)
        ax.axhline(threshold,linestyle='--',label='Frozen metric threshold')
        ax.set_yscale('symlog',linthresh=1e-10);ax.set_ylim(bottom=0)
        ax.set_xticks(range(6),labels=[s.upper() for s in FAMILIES])
        ax.set(ylabel=key.replace('_',' '),title='Worst recorded measured-width error per family/backend')
        emit(fig,'accuracy_'+name,'Maximum across measured blocks and qualified widths, not a mean or confidence interval. Zero errors remain zero; symlog is linear within ±1e-10. Complete qualification uses all frozen error checks, not this metric alone.', 'data/accuracy.csv','suite=W')
    # P6 point estimates and intervals are imported from their accepted sources.
    order=('G/F','F/R','R/U','F/U','G/R','G/U')
    for metric,suffix in [('session_inclusive_s','inclusive'),('total_wall_s','steady')]:
        fig,ax=figure()
        for i,group in enumerate(('all','1dpu_t8','4dpu_t8')):
            q=[next(c for c in r['p6_aggregates'] if c['group']==group and c['contrast']==contrast and c['metric']==metric) for contrast in order]
            y=np.arange(len(order))+(i-1)*.18
            line,=ax.plot([c['ratio'] for c in q],y,'o',label=group)
            ax.hlines(y,[number(c['paired_bootstrap_low']) for c in q],[number(c['paired_bootstrap_high']) for c in q],color=line.get_color())
        ax.axvline(1,linestyle='--');ax.set_yticks(range(len(order)),labels=order);ax.invert_yaxis()
        ax.set(xlabel='Numerator / denominator time',title='P6 accepted family-balanced ratios — '+suffix)
        emit(fig,'p6_aggregate_'+suffix,'Original P6 descriptive intervals, imported unchanged. G greedy; F FLOP selection; R reranking; U guided generation. A near-one R/U interval is not statistical equivalence.', 'data/p6_aggregates.csv',metric)
    for contrast in ('R/U','F/R','G/U'):
        q=sorted([c for c in r['p6_cells'] if c['contrast']==contrast and c['metric']=='session_inclusive_s'],key=lambda c:c['cell_id'])
        fig,ax=plt.subplots(figsize=(7.2,5.6));y=np.arange(len(q))
        ax.hlines(y,[number(c['paired_bootstrap_low']) for c in q],[number(c['paired_bootstrap_high']) for c in q])
        ax.plot([c['ratio'] for c in q],y,'o');ax.axvline(1,linestyle='--')
        ax.set_yticks(y,labels=[c['family']+' / '+c['topology_id']+(' [same path]' if str(c['same_selected_path']).lower()=='true' else '') for c in q])
        from matplotlib.ticker import MaxNLocator
        ax.xaxis.set_major_locator(MaxNLocator(nbins=5))
        ax.invert_yaxis();ax.set(xlabel=contrast+' time ratio',title='P6 per-cell inclusive outcomes')
        emit(fig,'p6_cells_'+contrast.replace('/','_over_'),'All twelve cells, including regressions and method aliases. Same-path methods share observations; aliases are not independent replications.', 'data/p6_cells.csv',contrast+'/session_inclusive_s')
    q=sorted([c for c in r['p6_methods'] if c['family'].lower()=='hs' and c['topology_id']=='4dpu_t8'],key=lambda c:('G','F','R','U').index(c['method']))
    fig,ax=figure()
    for field,label in [('session_inclusive_s_median','Inclusive'),('session_open_s_median','Session opening'),('total_wall_s_median','Steady execution'),('kernel_s_median','SDK kernel timer')]:
        ax.plot(range(4),[number(c[field]) for c in q],marker='o',label=label)
    ax.set_xticks(range(4),labels=[c['method'] for c in q]);ax.set(ylabel='Recorded median (s)',title='P6 HS18/D4 — lifecycle-sensitive regression')
    emit(fig,'p6_hs_lifecycle','Separate medians and nested timers are not additive. The inclusive regression coexists with similar kernel time; this is not proof of a specific causal bottleneck.', 'data/p6_methods.csv','HS / 4dpu_t8')
    fig,ax=plt.subplots(figsize=(7.2,5.6))
    ids=sorted({c['cell_id'] for c in r['p6_search']})
    for method in ('F','U'):
        q=[next(c for c in r['p6_search'] if c['cell_id']==cid and c['method']==method) for cid in ids]
        ax.plot([number(c['search_wall_s']) for c in q],range(len(ids)),'o',label=method)
    ax.set_yticks(range(len(ids)),labels=[c.split('_')[0].upper()+' / '+c.split('/')[-1] for c in ids]);ax.invert_yaxis()
    ax.set(xlabel='Offline search wall time (s)',title='P6 planning cost — not added to physical execution medians')
    emit(fig,'p6_search','Recorded offline F/U searches. Not additional physical runs and not a repeated-seed generalization study.', 'data/p6_search.csv','all')
    diag=source['p6_diagnostics'];fig,ax=figure()
    matrix=np.asarray(diag['pooled_total_feature_correlations'],dtype=float)
    im=ax.imshow(matrix,vmin=-1,vmax=1)
    ax.set_xticks(range(5),labels=diag['features']);ax.set_yticks(range(5),labels=diag['features'])
    for i in range(5):
        for j in range(5):ax.text(j,i,f'{matrix[i,j]:.3f}',ha='center',va='center',fontsize=8)
    fig.colorbar(im,ax=ax,label='Recorded pooled correlation');ax.set_title('P6 feature redundancy; weights are not runtime shares')
    emit(fig,'p6_feature_correlations',diag['interpretation']+' Original diagnostics: 1001 grid tuples, 47 selection vectors, 16 tied best tuples.', 'data/p6_diagnostics.json','pooled_total_feature_correlations')
    q=r['quantization'];fig,ax=figure()
    for key,label in [('relative_l2_percent','Int8 vs same-DAG float32'),('error_vs_complex128_percent','Int8 vs complex128')]:
        ax.plot(range(len(q)),[number(c[key]) for c in q],'o',label=label)
    ax.set_xticks(range(len(q)),labels=[c['circuit_id'] for c in q],rotation=15)
    ax.set_yscale('symlog',linthresh=1e-5);ax.set_ylim(bottom=0);ax.set(ylabel='Relative L2 error (%)',title='Software quantization characterization')
    emit(fig,'quantization_error','Software characterization only, not physical timing. Zero remains zero; symlog is linear within ±1e-5 percentage points. No post-hoc int8 quality threshold is applied.', 'data/quantization.csv','all')
    fig,ax=figure();ax.bar(range(len(q)),[number(c['nominal_compression_ratio']) for c in q])
    ax.set_xticks(range(len(q)),labels=[c['circuit_id'] for c in q],rotation=15)
    ax.set(ylabel='Logical float32 operand bytes / int8 operand bytes',title='Logical storage compression, not transfer speedup')
    emit(fig,'quantization_compression','The ratio includes recorded logical scale overhead. It is not a measured H2D/MRAM bandwidth reduction or a physical performance ratio.', 'data/quantization.csv','all')
    from matplotlib import ft2font, font_manager
    font=Path(font_manager.findfont('DejaVu Sans'))
    environment={'python':platform.python_version(),'numpy':np.__version__,'matplotlib':matplotlib.__version__,
                 'freetype':ft2font.__freetype_version__, 'font_sha256':hashlib.sha256(font.read_bytes()).hexdigest(),
                 'platform':sys.platform,'formats':['svg','png'], 'zlib_runtime':zlib.ZLIB_RUNTIME_VERSION,
                 'packages':{name:importlib.metadata.version(name) for name in ('numpy','matplotlib','pillow','fonttools','cycler','kiwisolver','packaging','pyparsing','python-dateutil','six')},
                 'determinism':'same Python/library/font/rendering environment; verified by independent full rebuild'}
    return index,environment
