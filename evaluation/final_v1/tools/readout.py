#!/usr/bin/env python3
"""Deterministic, read-only synthesis of final campaign receipts. No model fitting."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

import final_eval as f


def median_mad(xs):
    m = statistics.median(xs)
    return m, statistics.median(abs(x - m) for x in xs)


def comparison(x, y, draws=10000, seed=20260911):
    import numpy as np

    a, b = np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)
    f.require(a.shape == b.shape and a.ndim == 1 and a.size > 1, 'paired vectors required')
    f.require(
        np.all(np.isfinite(a)) and np.all(np.isfinite(b)) and np.all(a > 0) and np.all(b > 0),
        'invalid time',
    )
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(a), size=(draws, len(a)))
    samples = np.median(a[indices], axis=1) / np.median(b[indices], axis=1)
    ratio = float(np.median(a) / np.median(b))
    lo, hi = np.quantile(samples, [.025, .975])
    return dict(
        ratio=ratio,
        descriptive_low=float(lo),
        descriptive_high=float(hi),
        denominator_time_reduction_percent=100 * (1 - 1 / ratio),
    )


def write_csv(path, rows, columns=None):
    if not rows:
        columns = columns or ['status']
    else:
        columns = columns or list(dict.fromkeys(k for r in rows for k in r))
    with Path(path).open('x', newline='') as fp:
        w = csv.DictWriter(fp, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)


def flatten_row(r, arm=None):
    row = {
        k: r.get(k)
        for k in (
            'experiment_id',
            'sample_id',
            'suite',
            'case_id',
            'arm_id',
            'block',
            'warmup',
            'status',
            'reason',
            'accuracy_qualified',
            'output_sha256',
            'rss_max_kib',
        )
    }
    a = r.get('arm') or arm or {}
    m = r.get('metrics', {})
    v = r.get('validation', {})
    mm = m.get('measurement', {})
    row.update(
        backend=a.get('backend'),
        dpus=a.get('dpus'),
        tasklets=a.get('tasklets'),
        threads=a.get('threads'),
        policy=a.get('policy'),
        schedule=a.get('schedule'),
        fuse=a.get('fuse'),
        job_to_state_s=m.get('job_to_state_s'),
        prepared_call_s=m.get('prepared_call_s'),
        session_inclusive_s=m.get('session_inclusive_s'),
        session_open_s=m.get('session_open_s'),
        session_close_s=m.get('session_close_s'),
        steady_s=mm.get('total_wall_s'),
        kernel_s=mm.get('kernel_s', m.get('kernel_s')),
        h2d_s=mm.get('h2d_s'),
        d2h_s=mm.get('d2h_s'),
        h2d_bytes=mm.get('h2d_bytes'),
        d2h_bytes=mm.get('d2h_bytes'),
        relative_l2=v.get('relative_l2'),
        max_abs=v.get('max_abs'),
        norm_drift=v.get('norm_drift'),
        probability_norm_drift=v.get('probability_norm_drift'),
        fidelity=v.get('fidelity_normalized'),
        same_policy_passed=m.get('same_policy_passed'),
        relative_l2_vs_float32_same_dag=m.get('error_vs_float32_same_dag', {}).get('relative_l2'),
        physical_plan_id=m.get('physical_plan_id'),
        path_id=m.get('path_id'),
    )
    for prefix, record in (
        ('measurement', mm),
        ('call', m),
        ('backend', m.get('backend_facts', {})),
        ('terminal', m.get('terminal_facts', {})),
    ):
        for key, value in sorted(record.items()):
            if value is None or isinstance(value, (str, int, float, bool)):
                row[prefix + '_' + key] = value
    return row


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--figures', action='store_true')
    a = p.parse_args()
    work = Path(a.work).resolve()
    out = Path(a.output).resolve()
    f.require(not out.exists(), 'new output directory required; preserve previous readouts')
    f.verify_freeze(work)
    b = f.read(work / 'binding.json')
    spec = b['specification']
    out.mkdir(parents=True)
    rows = []
    coverage = []
    groups = {}
    times = []
    comparisons = []
    metrics = [
        'job_to_state_s',
        'prepared_call_s',
        'session_inclusive_s',
        'steady_s',
        'kernel_s',
        'session_open_s',
        'session_close_s',
        'h2d_s',
        'd2h_s',
        'h2d_bytes',
        'd2h_bytes',
    ]
    for sp in sorted((work / 'suites').glob('*.json')):
        suite = sp.stem
        d = f.read(sp)
        root = work / 'receipts' / suite
        for e in d['entries']:
            observations = []
            cnt = Counter()
            for block in range(d['warmups'] + d['measurements']):
                file = root / f"b{block:02d}__{e['case_id']}__{e['arm_id']}.json"
                if file.exists():
                    raw = f.read(file)
                    sidecar = Path(str(file) + '.issued.json')
                    f.require(sidecar.exists(), f'missing issued sidecar: {sidecar}')
                    issued = f.read(sidecar)
                    f.require(issued.get('suite') == suite, f'issued suite mismatch: {sidecar}')
                    f.require(issued.get('case_id') == e['case_id'], f'issued case_id mismatch: {sidecar}')
                    f.require(issued.get('arm_id') == e['arm_id'], f'issued arm_id mismatch: {sidecar}')
                    f.require(issued.get('block') == block, f'issued block mismatch: {sidecar}')
                    f.require(issued.get('warmup') == (block < d['warmups']), f'issued warmup mismatch: {sidecar}')
                    r = flatten_row(raw, arm=issued.get('arm') or e.get('arm'))
                    r['suite'] = issued['suite']
                    r['case_id'] = issued['case_id']
                    r['arm_id'] = issued['arm_id']
                    r['block'] = issued['block']
                    r['warmup'] = issued['warmup']
                else:
                    r = dict(
                        suite=suite,
                        case_id=e['case_id'],
                        arm_id=e['arm_id'],
                        block=block,
                        warmup=block < d['warmups'],
                        status='not_collected',
                    )
                rows.append(r)
                if not r['warmup']:
                    cnt[r['status']] += 1
                    observations.append(r)
            complete = len(observations) == d['measurements'] and all(r['status'] == 'success' for r in observations)
            int8 = e['arm'].get('policy') == f.I8
            quality = complete and all(r.get('accuracy_qualified') is True for r in observations)
            coverage.append(
                dict(
                    suite=suite,
                    case_id=e['case_id'],
                    arm_id=e['arm_id'],
                    expected=d['measurements'],
                    success=cnt['success'],
                    unsupported=cnt['unsupported'],
                    not_attempted=cnt['not_attempted'],
                    not_collected=cnt['not_collected'],
                    timeout=cnt['timeout'],
                    memory_limit=cnt['memory_limit'],
                    failure=cnt['failure'],
                    complete=complete,
                    quality_qualified=quality,
                    int8_error_characterization_only=int8,
                )
            )
            if not complete:
                continue
            key = (suite, e['case_id'], e['arm_id'])
            groups[key] = (e['arm'], observations, quality)
            for metric in metrics:
                values = [r.get(metric) for r in observations]
                if not all(isinstance(v, (float, int)) and math.isfinite(v) for v in values):
                    continue
                m, mad = median_mad(values)
                times.append(
                    dict(
                        suite=suite,
                        case_id=e['case_id'],
                        arm_id=e['arm_id'],
                        metric=metric,
                        median=m,
                        raw_mad=mad,
                        count=len(values),
                        quality_qualified=quality,
                    )
                )

    def pair(suite, cid, numer, denom, label, resource_ratio=None, numer_may_be_int8=False):
        x = groups.get((suite, cid, numer))
        y = groups.get((suite, cid, denom))
        if not x or not y:
            return
        quant = label == 'int8_policy_tradeoff'
        if not quant and not (x[2] and y[2]):
            return
        if quant and not (x[2] and all(r.get('same_policy_passed') is True for r in y[1])):
            return
        for metric in ('job_to_state_s', 'prepared_call_s', 'session_inclusive_s'):
            if metric == 'session_inclusive_s' and (x[0]['backend'] != 'upmem' or y[0]['backend'] != 'upmem'):
                continue
            xs = [r.get(metric) for r in x[1]]
            ys = [r.get(metric) for r in y[1]]
            if not all(isinstance(v, (int, float)) and v > 0 for v in xs + ys):
                continue
            c = dict(
                suite=suite,
                case_id=cid,
                comparison=label,
                numerator=numer,
                denominator=denom,
                metric=metric,
                **comparison(xs, ys, spec['bootstrap_draws'], spec['seed']),
                paired_blocks=len(xs),
                equal_quality_claim=not quant,
            )
            if resource_ratio:
                c['parallel_efficiency'] = c['ratio'] / resource_ratio
            comparisons.append(c)

    suites = {p.stem: f.read(p) for p in (work / 'suites').glob('*.json')}
    for name, d in suites.items():
        for cid in sorted({e['case_id'] for e in d['entries']}):
            entries = [e for e in d['entries'] if e['case_id'] == cid]
            if name == 'T':
                base = f.arm_id(f.up(1, 1, 'serial_nodes_v1', False))
                for e in entries:
                    pair(name, cid, base, e['arm_id'], 'tasklet_scaling', e['arm']['tasklets'])
            elif name == 'D':
                for e in entries:
                    arm = e['arm']
                    base = f.arm_id(f.up(1, arm['tasklets']))
                    pair(name, cid, base, e['arm_id'], 'dpu_scaling', arm['dpus'])
            elif name == 'A':
                ordered = [
                    f.up(1, 1, 'serial_nodes_v1', False),
                    f.up(1, 8, 'serial_nodes_v1', False),
                    f.up(4, 8, 'serial_nodes_v1', False),
                    f.up(4, 8, 'serial_nodes_v1', True),
                    f.up(4, 8),
                ]
                labels = ['tasklets', 'dpus', 'complex_fusion', 'dag_concurrency']
                for left, right, label in zip(ordered, ordered[1:], labels):
                    pair(name, cid, f.arm_id(left), f.arm_id(right), label)
                pair(name, cid, f.arm_id(ordered[0]), f.arm_id(ordered[-1]), 'matched_combined_executor')
            elif name == 'Q':
                for nd in sorted({e['arm']['dpus'] for e in entries}):
                    pair(name, cid, f.arm_id(f.up(nd, 8)), f.arm_id(f.up(nd, 8, policy=f.I8)), 'int8_policy_tradeoff')
            elif name == 'W':
                for e in entries:
                    if e['arm']['backend'] == 'upmem':
                        for cpu in entries:
                            if cpu['arm']['backend'] != 'upmem':
                                pair(name, cid, cpu['arm_id'], e['arm_id'], 'cpu_vs_upmem')

    write_csv(out / 'observations.csv', rows)
    write_csv(out / 'coverage.csv', coverage)
    write_csv(out / 'times.csv', times)
    write_csv(out / 'comparisons.csv', comparisons)
    case_rows = []
    geometry = []
    features = []
    for p in sorted((work / 'case_records').glob('*.json')):
        c = f.read(p)
        if c['role'] in ('qualification', 'resource_qualification'):
            continue
        rec = f.read(work / 'plans' / p.name)
        row = {
            **c,
            **{
                k: rec.get(k)
                for k in (
                    'tensor_count',
                    'node_count',
                    'gate_depth',
                    'largest_intermediate_elements',
                    'sum_intermediate_elements',
                    'working_bound_bytes',
                    'full_state_c64_bytes',
                    'full_state_c128_bytes',
                    'path_id',
                    'logical_plan_id',
                )
            },
        }
        row['gate_counts'] = json.dumps(rec.get('gate_counts', {}), sort_keys=True)
        row['optimized_flops'] = rec.get('planner', {}).get('optimized_flops')
        row['planner_status'] = rec.get('status', 'completed' if 'path' in rec else 'unavailable')
        case_rows.append(row)
        ad = f.read(work / 'admission' / p.name)
        for g in ad.get('geometry', []):
            geometry.append({'case_id': c['case_id'], **g})
        for aid, record in ad.get('arms', {}).items():
            totals = record.get('totals', {})
            features.append(
                dict(
                    case_id=c['case_id'],
                    arm_id=aid,
                    status=record['status'],
                    plan_facts_json=json.dumps(record, sort_keys=True, separators=(',', ':')),
                )
            )
    write_csv(out / 'circuits.csv', case_rows)
    write_csv(out / 'contractions.csv', geometry)
    write_csv(out / 'plan_facts.csv', features)

    largest = []
    bycase = {r['case_id']: r for r in case_rows}
    for aid in sorted({r['arm_id'] for r in coverage if r['suite'] == 'W'}):
        for family in spec['primary_families']:
            eligible = [
                bycase[r['case_id']]['n']
                for r in coverage
                if r['suite'] == 'W'
                and r['arm_id'] == aid
                and r['quality_qualified']
                and bycase[r['case_id']]['family'] == family
                and bycase[r['case_id']]['role'] == 'width'
            ]
            largest.append(
                dict(
                    family=family,
                    arm_id=aid,
                    largest_fully_measured_qubits=max(eligible) if eligible else '',
                    claim='largest qualified point in declared grid, not maximum supported circuit',
                )
            )
    write_csv(out / 'largest_tested.csv', largest)

    digest_inputs = {
        p.relative_to(work).as_posix(): f.digest(p)
        for p in sorted((work / 'receipts').rglob('*'))
        if p.is_file()
    }
    f.write(
        out / 'provenance.json',
        dict(
            source_commit=f.FROZEN,
            freeze_sha256=f.digest(work / 'freeze.json'),
            receipt_sha256=digest_inputs,
            readout_sha256=f.digest(__file__),
            statistics='ratio_of_medians_paired_block_percentile_bootstrap',
            draws=spec['bootstrap_draws'],
            seed=spec['seed'],
            historical_data_not_pooled=True,
        ),
    )
    (out / 'README.md').write_text(
        '# Final evaluation readout\n\n'
        'New measurements only; no historical or P6 observations were replaced. '
        'Start with coverage.csv before interpreting times or speedups. '
        'Rows missing complete measured blocks have no completed-group speedup. '
        'FP32 comparisons require numerical qualification. Int8 ratios are performance/error trade-offs, not equal-quality speedups. '
        'Bootstrap intervals are conditional timing summaries. Raw session-inclusive timers are not compared across CPU engines. '
        'Historical mechanism and P6 evidence are provided separately.\n'
    )
    if a.figures:
        figures(out, times, coverage, bycase, rows)
    with (out / 'SHA256SUMS').open('x') as fp:
        for path in sorted(out.rglob('*')):
            if path.is_file() and path.name != 'SHA256SUMS':
                fp.write(f'{f.digest(path)}  {path.relative_to(out).as_posix()}\n')
    print(out)


def figures(out, times, coverage, bycase, rows):
    import matplotlib

    matplotlib.use('Agg')
    matplotlib.rcParams['svg.hashsalt'] = 'masters-thesis-final-evaluation-v2'
    import matplotlib.pyplot as plt

    folder = out / 'figures'
    folder.mkdir()
    okay = {(r['suite'], r['case_id'], r['arm_id']) for r in coverage if r['quality_qualified']}
    for family in sorted({c['family'] for c in bycase.values() if c['role'] == 'width'}):
        fig, ax = plt.subplots(figsize=(7, 4.5))
        for aid in sorted({r['arm_id'] for r in times if r['suite'] == 'W'}):
            rs = [
                r
                for r in times
                if r['suite'] == 'W'
                and r['metric'] == 'job_to_state_s'
                and bycase[r['case_id']]['family'] == family
                and bycase[r['case_id']]['role'] == 'width'
                and ('W', r['case_id'], aid) in okay
                and r['arm_id'] == aid
            ]
            if not rs:
                continue
            rs.sort(key=lambda r: bycase[r['case_id']]['n'])
            ax.scatter([bycase[r['case_id']]['n'] for r in rs], [r['median'] for r in rs], label=aid, s=20)
        ax.set_xlabel('Total allocated qubits')
        ax.set_ylabel('Median job-to-state time (s)')
        ax.set_yscale('log')
        ax.set_title(f'{family}: complete statevector, fixed greedy TN path rule')
        if ax.get_legend_handles_labels()[0]:
            ax.legend(fontsize=6)
        fig.tight_layout()
        fig.savefig(folder / f'width_{family}.svg', metadata={'Date': None, 'Creator': 'masters-thesis final evaluation v2'})
        fig.savefig(folder / f'width_{family}.png', dpi=180)
        plt.close(fig)

    for suite, xfield, label in [('T', 'tasklets', 'Tasklets (one DPU)'), ('D', 'dpus', 'DPUs (one rank)')]:
        for cid in sorted({r['case_id'] for r in times if r['suite'] == suite}):
            fig, ax = plt.subplots(figsize=(7, 4.5))
            for tasklets in ([None] if suite == 'T' else [8, 24]):
                rs = []
                for r in times:
                    if r['suite'] != suite or r['case_id'] != cid or r['metric'] != 'prepared_call_s':
                        continue
                    if (suite, cid, r['arm_id']) not in okay:
                        continue
                    fields = r['arm_id'].split('_')
                    d = int(fields[1][1:])
                    t = int(fields[2][1:])
                    if tasklets is not None and t != tasklets:
                        continue
                    rs.append((t if suite == 'T' else d, r['median'], r['raw_mad']))
                if rs:
                    rs.sort()
                    ax.errorbar(
                        [r[0] for r in rs],
                        [r[1] for r in rs],
                        yerr=[r[2] for r in rs],
                        marker='o',
                        label='T sweep' if tasklets is None else f'T{tasklets}',
                    )
            ax.set_xlabel(label)
            ax.set_ylabel('Prepared-call median ± raw MAD (s)')
            ax.set_title(cid)
            if ax.get_legend_handles_labels()[0]:
                ax.legend()
            fig.tight_layout()
            fig.savefig(folder / f'{suite}_{cid}.svg', metadata={'Date': None, 'Creator': 'masters-thesis final evaluation v2'})
            fig.savefig(folder / f'{suite}_{cid}.png', dpi=180)
            plt.close(fig)

    for cid in sorted({r['case_id'] for r in times if r['suite'] == 'A'}):
        fig, ax = plt.subplots(figsize=(7, 4.5))
        order = [
            f.arm_id(a)
            for a in (
                f.up(1, 1, 'serial_nodes_v1', False),
                f.up(1, 8, 'serial_nodes_v1', False),
                f.up(4, 8, 'serial_nodes_v1', False),
                f.up(4, 8, 'serial_nodes_v1', True),
                f.up(4, 8),
            )
        ]
        labels = ['A0', 'A1', 'A2', 'A3', 'A4']
        xs = []
        ys = []
        es = []
        for i, aid in enumerate(order):
            match = [
                r
                for r in times
                if r['suite'] == 'A'
                and r['case_id'] == cid
                and r['arm_id'] == aid
                and r['metric'] == 'prepared_call_s'
                and ('A', cid, aid) in okay
            ]
            if match:
                xs.append(i)
                ys.append(match[0]['median'])
                es.append(match[0]['raw_mad'])
        ax.bar(xs, ys, yerr=es)
        ax.set_xticks(range(5), labels)
        ax.set_ylabel('Prepared-call median ± raw MAD (s)')
        ax.set_title(cid + ' — matched ablations')
        fig.tight_layout()
        fig.savefig(folder / f'A_{cid}.svg', metadata={'Date': None, 'Creator': 'masters-thesis final evaluation v2'})
        fig.savefig(folder / f'A_{cid}.png', dpi=180)
        plt.close(fig)
    for svg in folder.glob('*.svg'):
        lines = svg.read_text(encoding='utf-8').splitlines()
        svg.write_text('\n'.join(line.rstrip() for line in lines) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
