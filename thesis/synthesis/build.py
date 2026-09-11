#!/usr/bin/env python3
"""Read frozen Git objects; verify evidence; build publication artifacts. No execution API."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import shutil
import statistics
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
FAMILIES = ('bb84', 'bv', 'edc', 'hs', 'qrng', 'xor')
METRICS = ('job_to_state_s', 'prepared_call_s', 'session_inclusive_s', 'steady_s',
           'kernel_s', 'session_open_s', 'session_close_s', 'h2d_s', 'd2h_s',
           'h2d_bytes', 'd2h_bytes')
RESOURCE_CASES = ('hs_n18', 'stress_n16_l2')
ABLATION_CASES = ('edc_n17', 'hs_n18', 'stress_n16_l2')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def number(value, optional=False):
    if value is None or value == '':
        require(optional, 'missing numeric value')
        return None
    require(not isinstance(value, bool), 'boolean supplied as number')
    out = float(value)
    require(math.isfinite(out), f'nonfinite number: {value!r}')
    return out


def integer(value):
    require(not isinstance(value, bool), 'boolean supplied as integer')
    out = int(value)
    require(str(out) == str(value), f'noncanonical integer: {value!r}')
    return out


def boolean(value):
    if value is True or value == 'True' or value == 'true':
        return True
    if value is False or value == 'False' or value == 'false':
        return False
    raise ValueError(f'missing or invalid boolean: {value!r}')


def close(a, b, description):
    require(math.isclose(float(a), float(b), rel_tol=2e-10, abs_tol=1e-12),
            f'{description}: {a!r} != {b!r}')


def median_mad(values):
    m = statistics.median(values)
    return m, statistics.median(abs(x - m) for x in values)


def bootstrap(x, y, draws, seed):
    """Exact final-campaign verification algorithm; not a new inferential design."""
    import numpy as np
    a, b = np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)
    require(a.shape == b.shape and a.ndim == 1 and len(a) > 1, 'paired blocks required')
    require(bool(np.isfinite(a).all() and np.isfinite(b).all() and (a > 0).all() and (b > 0).all()),
            'invalid paired timing')
    idx = np.random.default_rng(seed).integers(0, len(a), size=(draws, len(a)))
    values = np.median(a[idx], axis=1) / np.median(b[idx], axis=1)
    return tuple(float(v) for v in np.quantile(values, [.025, .975]))


def ratio_fields(ratio):
    require(ratio > 0 and math.isfinite(ratio), 'ratio must be finite and positive')
    return {'time_reduction_pct': 100 * (1 - 1 / ratio),
            'denominator_time_increase_pct': 100 * (1 / ratio - 1)}


def csv_rows(data, source_id):
    reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig'), newline=''))
    require(reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames)),
            f'{source_id}: empty/duplicate CSV header')
    rows = []
    for line, row in enumerate(reader, 2):
        require(None not in row and all(v is not None for v in row.values()),
                f'{source_id}:{line}: malformed CSV record')
        rows.append({**row, 'input_source_id': source_id, 'source_row': line})
    return rows


def unique(rows, keys):
    result = {}
    for row in rows:
        key = tuple(row[k] for k in keys)
        require(key not in result, f'duplicate {keys}: {key}')
        result[key] = row
    return result


def safe_path(path):
    p = PurePosixPath(path)
    require(path and not p.is_absolute() and '..' not in p.parts and ':' not in path,
            f'unsafe source path {path!r}')
    return path


class GitSources:
    def __init__(self, repo, specification):
        self.repo = Path(repo).resolve()
        self.spec = specification
        self.cache = {}
        self.used = {}
        self.package_checks = []
        subprocess.run(['git', '-C', str(self.repo), 'cat-file', '-e',
                        specification['evidence_commit'] + '^{commit}'], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def read(self, ref, path):
        require(re.fullmatch(r'[0-9a-f]{40}', ref) is not None, 'full immutable commit required')
        safe_path(path)
        key = ref + ':' + path
        if key not in self.cache:
            p = subprocess.run(['git', '-C', str(self.repo), 'show', key],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            require(p.returncode == 0, f'missing frozen Git object {key}: {p.stderr.decode(errors="replace")}')
            self.cache[key] = p.stdout
            self.used[key] = {'ref': ref, 'path': path, 'sha256': sha(p.stdout),
                              'bytes': len(p.stdout),
                              'url': f'https://github.com/{self.spec["repository"]}/blob/{ref}/{path}'}
        return self.cache[key]

    def verify_packages(self):
        ref = self.spec['evidence_commit']
        for root in self.spec['checksum_packages']:
            manifest = self.read(ref, root + '/SHA256SUMS').decode('utf-8')
            seen = set()
            for line in manifest.splitlines():
                match = re.fullmatch(r'([0-9a-f]{64})  (.+)', line)
                require(match is not None, f'invalid checksum line in {root}')
                digest, rel = match.groups()
                safe_path(rel)
                require(rel not in seen, f'duplicate manifest member: {rel}')
                seen.add(rel)
                require(sha(self.read(ref, root + '/' + rel)) == digest,
                        f'checksum mismatch in frozen package: {root}/{rel}')
            self.package_checks.append({'path': root, 'ref': ref, 'verified_members': len(seen)})

    def load(self):
        self.verify_packages()
        data = {}
        for key, src in self.spec['inputs'].items():
            raw = self.read(src['ref'], src['path'])
            data[key] = csv_rows(raw, key) if src['path'].endswith('.csv') else json.loads(raw)
        # Historical narrative is read from old Git objects only, never restored.
        data['historical_bindings'] = {}
        for item in data['history_sources']:
            raw = self.read(item['ref'], item['path'])
            data['historical_bindings'][item['id']] = {
                **item, 'sha256': sha(raw),
                'url': f'https://github.com/{self.spec["repository"]}/blob/{item["ref"]}/{item["path"]}'}
        return data


def derive(data, config, verify_intervals=True):
    """Pure numerical synthesis. All checks precede publication output."""
    expected = config['expected']
    for key, countkey in [('final_observations', 'attempts'), ('final_coverage', 'cells'),
                          ('final_times', 'times'), ('final_comparisons', 'comparisons'),
                          ('p6_methods', 'p6_methods'), ('p6_contrasts', 'p6_contrasts'),
                          ('p6_aggregates', 'p6_aggregates'), ('p6_search', 'p6_search'),
                          ('mechanisms', 'mechanisms')]:
        require(len(data[key]) == expected[countkey], f'{key}: count does not match frozen specification')
    cases = {r['case_id']: r for r in data['final_circuits']}
    require(len(cases) == len(data['final_circuits']), 'duplicate case metadata')
    groups, definitions = defaultdict(list), {}
    for suite in ('T', 'D', 'A', 'W'):
        spec = data['suite_' + suite]
        for entry in spec['entries']:
            key = (suite, entry['case_id'], entry['arm_id'])
            require(key not in definitions, f'duplicate planned cell {key}')
            definitions[key] = (entry['arm'], int(spec['warmups']), int(spec['measurements']))
    seen = set()
    counts = Counter()
    for row in data['final_observations']:
        key = (row['suite'], row['case_id'], row['arm_id'])
        require(key in definitions, f'unplanned observation: {key}')
        arm, nw, nm = definitions[key]
        block = integer(row['block'])
        require(0 <= block < nw + nm, f'out-of-range block: {key}/{block}')
        require((*key, block) not in seen, f'duplicate observation: {key}/{block}')
        seen.add((*key, block))
        warm = boolean(row['warmup'])
        require(warm == (block < nw), f'warmup mismatch: {key}/{block}')
        require(row['status'] in ('success', 'unsupported'), f'unexpected campaign status: {row["status"]}')
        for field in ('backend', 'dpus', 'tasklets', 'threads', 'policy', 'schedule', 'fuse'):
            if field not in arm:
                continue
            if field == 'fuse':
                require(boolean(row[field]) is bool(arm[field]), f'arm mismatch: {key}/{field}')
            else:
                require(str(row.get(field)) == str(arm[field]), f'arm mismatch: {key}/{field}')
        if row['status'] == 'success':
            require(boolean(row['accuracy_qualified']), f'unqualified successful output: {key}/{block}')
            for field, bound in (('relative_l2','fp32_relative_l2_max'), ('norm_drift','fp32_norm_drift_max')):
                value = number(row[field])
                require(0 <= value <= data['scope']['validation'][bound],
                        f'recorded error exceeds frozen scalar bound: {key}/{field}')
            require(number(row['max_abs']) >= 0, 'negative absolute error')
            for metric in ('job_to_state_s', 'prepared_call_s'):
                require(number(row[metric]) > 0, f'nonpositive timing: {key}/{metric}')
        groups[key].append(row)
        counts['attempts'] += 1
        counts['warmups' if warm else 'measured'] += 1
        counts[row['status']] += 1
        if not warm:
            counts['measured_' + row['status']] += 1
    for key in ('attempts', 'warmups', 'measured', 'success', 'unsupported', 'measured_success', 'measured_unsupported'):
        require(counts[key] == expected[key], f'campaign accounting mismatch: {key}: {counts[key]}')
    published_coverage = unique(data['final_coverage'], ('suite', 'case_id', 'arm_id'))
    require(set(groups) == set(definitions) == set(published_coverage), 'cell sets differ')
    published_times = unique(data['final_times'], ('suite', 'case_id', 'arm_id', 'metric'))
    recomputed_times, measured, cells, accuracy, lifecycle = {}, {}, [], [], []
    for key in sorted(definitions):
        arm, nw, nm = definitions[key]
        rows = sorted(groups[key], key=lambda r: integer(r['block']))
        require({integer(r['block']) for r in rows} == set(range(nw + nm)), f'missing blocks in {key}')
        obs = [r for r in rows if not boolean(r['warmup'])]
        measured[key] = obs
        cov = published_coverage[key]
        cnt = Counter(r['status'] for r in obs)
        complete = len(obs) == nm and cnt['success'] == nm
        quality = complete and all(boolean(r['accuracy_qualified']) for r in obs)
        for name in ('success', 'unsupported', 'not_attempted', 'not_collected', 'timeout', 'memory_limit', 'failure'):
            require(integer(cov[name]) == cnt[name], f'coverage mismatch: {key}/{name}')
        require(integer(cov['expected']) == nm and boolean(cov['complete']) == complete
                and boolean(cov['quality_qualified']) == quality, f'coverage flags differ: {key}')
        case = cases[key[1]]
        cell = {'suite': key[0], 'case_id': key[1], 'family': case['family'], 'n': integer(case['n']),
                'arm_id': key[2], **arm, 'warmups': nw, 'measurements': nm,
                'success': cnt['success'], 'unsupported': cnt['unsupported'],
                'complete': complete, 'quality_qualified': quality,
                'observation_source_rows': ';'.join(str(r['source_row']) for r in obs),
                'source_id': 'final_coverage', 'source_row': cov['source_row']}
        if quality:
            err = {k: [number(r.get(k), optional=True) for r in obs] for k in
                   ('relative_l2', 'max_abs', 'norm_drift', 'probability_norm_drift', 'fidelity')}
            accuracy.append({'suite': key[0], 'case_id': key[1], 'family': case['family'],
                             'n': integer(case['n']), 'arm_id': key[2], **arm,
                             **{k + ('_min' if k == 'fidelity' else '_max'):
                                ((min if k == 'fidelity' else max)(vs) if all(v is not None for v in vs) else None)
                                for k, vs in err.items()},
                             'actual_multithreading_records': ';'.join(sorted({r.get('call_actual_multithreading', '') for r in obs})),
                             'source_rows': cell['observation_source_rows']})
        if quality and arm['backend'] == 'upmem':
            fractions = {part: [] for part in ('session_open_s', 'steady_s', 'session_close_s')}
            for record in obs:
                total = number(record['session_inclusive_s'])
                parts = {part: number(record[part]) for part in fractions}
                close(sum(parts.values()), total, 'sample-level lifecycle identity')
                for part, value in parts.items():
                    fractions[part].append(value / total)
            for part, values in fractions.items():
                m, mad = median_mad(values)
                lifecycle.append({'suite': key[0], 'case_id': key[1], 'arm_id': key[2], **arm,
                                  'component': part, 'median_per_sample_share': m,
                                  'raw_mad_share': mad, 'source_rows': cell['observation_source_rows']})
        if complete:
            for metric in METRICS:
                values = [number(r.get(metric), optional=True) for r in obs]
                if any(v is None for v in values):
                    continue
                m, mad = median_mad(values)
                tkey = (*key, metric)
                require(tkey in published_times, f'missing published summary: {tkey}')
                pub = published_times[tkey]
                close(m, number(pub['median']), f'median {tkey}')
                close(mad, number(pub['raw_mad']), f'MAD {tkey}')
                require(integer(pub['count']) == nm and boolean(pub['quality_qualified']) == quality,
                        f'summary qualification mismatch: {tkey}')
                recomputed_times[tkey] = {**pub, 'median': m, 'raw_mad': mad, 'count': nm,
                                         'quality_qualified': quality}
                cell[metric] = m
                cell[metric + '_mad'] = mad
        cells.append(cell)
    require(set(recomputed_times) == set(published_times), 'unverified/extra summary rows')
    require(sum(c['complete'] for c in cells) == expected['complete_cells'], 'complete cell total differs')
    unsupported = [c for c in cells if not c['complete']]
    require(sorted(c['case_id'] for c in unsupported) == sorted(config['unsupported_cases'])
            and all(c['suite'] == 'W' and c['backend'] == 'upmem' for c in unsupported),
            'unsupported frontier set differs')
    cellmap = {(c['suite'], c['case_id'], c['arm_id']): c for c in cells}
    comparisons = []
    unique(data['final_comparisons'], ('suite', 'case_id', 'comparison', 'numerator', 'denominator', 'metric'))
    for row in data['final_comparisons']:
        kx = (row['suite'], row['case_id'], row['numerator'])
        ky = (row['suite'], row['case_id'], row['denominator'])
        require(kx in cellmap and ky in cellmap and cellmap[kx]['quality_qualified']
                and cellmap[ky]['quality_qualified'], 'comparison includes incomplete/unqualified cell')
        metric = row['metric']
        require(metric in ('prepared_call_s', 'job_to_state_s', 'session_inclusive_s'), 'unexpected comparison scope')
        if metric == 'session_inclusive_s':
            require(cellmap[kx]['backend'] == cellmap[ky]['backend'] == 'upmem', 'invalid cross-engine session ratio')
        x, y = measured[kx], measured[ky]
        require([r['block'] for r in x] == [r['block'] for r in y], 'unpaired block identity')
        xs, ys = [number(r[metric]) for r in x], [number(r[metric]) for r in y]
        ratio = statistics.median(xs) / statistics.median(ys)
        close(ratio, number(row['ratio']), 'accepted comparison ratio')
        require(integer(row['paired_blocks']) == len(xs) and boolean(row['equal_quality_claim']), 'comparison qualification')
        lo, hi = number(row['descriptive_low']), number(row['descriptive_high'])
        require(0 < lo <= hi, 'invalid interval')
        if verify_intervals:
            vlo, vhi = bootstrap(xs, ys, data['scope']['bootstrap_draws'], data['scope']['seed'])
            close(lo, vlo, 'accepted final bootstrap lower')
            close(hi, vhi, 'accepted final bootstrap upper')
        fields = ratio_fields(ratio)
        close(fields['time_reduction_pct'], number(row['denominator_time_reduction_percent']), 'reduction conversion')
        eff = number(row.get('parallel_efficiency'), optional=True)
        if row['suite'] in ('T', 'D'):
            divisor = cellmap[ky]['tasklets' if row['suite'] == 'T' else 'dpus']
            require(eff is not None, 'missing scaling efficiency')
            close(eff, ratio / divisor, 'parallel efficiency')
        comparisons.append({**row, 'ratio': ratio, 'descriptive_low': lo, 'descriptive_high': hi,
                            'parallel_efficiency': eff, **fields, 'paired_blocks': len(xs),
                            'family': cases[row['case_id']]['family'], 'n': integer(cases[row['case_id']]['n'])})
    cmpmap = {(r['suite'], r['case_id'], r['numerator'], r['denominator'], r['metric']): r for r in comparisons}
    best = []
    for suite in ('T', 'D'):
        for cid in RESOURCE_CASES:
            for t in ([None] if suite == 'T' else [8, 24]):
                selected = [c for c in cells if c['suite'] == suite and c['case_id'] == cid
                            and (t is None or c['tasklets'] == t) and c['quality_qualified']]
                field = 'tasklets' if suite == 'T' else 'dpus'
                require(selected, 'missing resource group')
                chosen = min(selected, key=lambda c: (c['prepared_call_s'], c[field]))
                base = min(selected, key=lambda c: c[field])
                endpoint = max(selected, key=lambda c: c[field])
                best.append({'suite': suite, 'case_id': cid, 'fixed_tasklets': t,
                             'best_observed_resource': chosen[field], 'endpoint': endpoint[field],
                             'best_prepared_s': chosen['prepared_call_s'],
                             'best_ratio_vs_one': base['prepared_call_s'] / chosen['prepared_call_s'],
                             'endpoint_ratio_vs_one': base['prepared_call_s'] / endpoint['prepared_call_s'],
                             'endpoint_efficiency': (base['prepared_call_s'] / endpoint['prepared_call_s']) / endpoint[field],
                             'claim_limit': 'Descriptive minimum median in measured grid; not an independent optimum confirmation.',
                             'source_rows': chosen['observation_source_rows']})
    circuits = []
    geometry = defaultdict(list)
    for r in data['final_contractions']:
        b, m, k, n = [integer(r[v]) for v in ('B', 'M', 'K', 'N')]
        require(integer(r['real_macs']) == 4 * b * m * k * n, 'geometry MAC formula mismatch')
        geometry[r['case_id']].append(r)
    for row in data['final_circuits']:
        n = integer(row['n'])
        require(integer(row['full_state_c64_bytes']) == 8 * 2**n, 'statevector byte formula mismatch')
        counts_gates = json.loads(row['gate_counts'])
        circuits.append({**row, 'n': n, 'gate_count': sum(counts_gates.values()),
                         'statevector_mib': 8 * 2**n / 2**20,
                         'real_macs': sum(integer(g['real_macs']) for g in geometry[row['case_id']]),
                         'data_qubits': (n + 1)//2 if row['family'] == 'edc' else n-1 if row['family'] in ('bv','xor') else n,
                         'ancilla_qubits': (n - 1)//2 if row['family'] == 'edc' else 1 if row['family'] in ('bv','xor') else 0})
    planfacts = {(r['case_id'], r['arm_id']): json.loads(r['plan_facts_json']) for r in data['final_plan_facts']}
    frontiers = []
    for r in data['final_largest_tested']:
        candidates = [c for c in cells if c['suite'] == 'W' and c['family'] == r['family'] and c['arm_id'] == r['arm_id']]
        require(candidates, 'missing frontier group')
        reached = max(c['n'] for c in candidates if c['quality_qualified'])
        require(integer(r['largest_fully_measured_qubits']) == reached, 'frontier disagrees with coverage')
        bad = [c for c in candidates if not c['quality_qualified']]
        reasons = []
        for c in bad:
            fact = planfacts.get((c['case_id'], c['arm_id']), {})
            reasons.append({'case_id': c['case_id'], 'status': fact.get('status'),
                            'reason': fact.get('reason'), 'capability': fact.get('capability')})
        frontiers.append({**r, 'largest_fully_measured_qubits': reached,
                          'largest_planned_qubits': max(c['n'] for c in candidates),
                          'unqualified_points': ';'.join(str(c['n']) for c in sorted(bad, key=lambda x:x['n'])),
                          'admission_records': json.dumps(reasons, sort_keys=True, separators=(',', ':')),
                          'boundary': 'observed admission boundary' if bad else 'declared grid ended'})
    # Preserve accepted P6 inference. Check point estimates but do not refit or re-bootstrap P6.
    pm = unique(data['p6_methods'], ('cell_id', 'method'))
    p6c = []
    for r in data['p6_contrasts']:
        a, b = r['contrast'].split('/')
        x, y = pm[(r['cell_id'], a)], pm[(r['cell_id'], b)]
        ratio = number(x[r['metric'] + '_median']) / number(y[r['metric'] + '_median'])
        close(ratio, number(r['ratio_of_medians']), 'P6 contrast vs accepted medians')
        close(100*(1-1/ratio), number(r['denominator_time_reduction_pct']), 'P6 percent conversion')
        require(boolean(r['same_selected_path']) == (x['path_id'] == y['path_id']), 'P6 alias mismatch')
        require(0 < number(r['paired_bootstrap_low']) <= number(r['paired_bootstrap_high']), 'invalid accepted P6 interval')
        p6c.append({**r, 'ratio': ratio, **ratio_fields(ratio)})
    p6a = []
    for r in data['p6_aggregates']:
        parts = [x for x in p6c if x['contrast'] == r['contrast'] and x['metric'] == r['metric']
                 and (r['group'] == 'all' or x['topology_id'] == r['group'])]
        grouped = defaultdict(list)
        for part in parts:
            grouped[part['family']].append(math.log(part['ratio']))
        require(len(parts) == integer(r['cells']) and len(grouped) == integer(r['families']), 'P6 aggregate coverage')
        geo = math.exp(statistics.mean(statistics.mean(vs) for vs in grouped.values()))
        close(geo, number(r['family_balanced_geometric_ratio']), 'P6 geometric point estimate')
        require(0 < number(r['paired_bootstrap_low']) <= number(r['paired_bootstrap_high']), 'invalid P6 aggregate interval')
        p6a.append({**r, 'ratio': number(r['family_balanced_geometric_ratio']), **ratio_fields(geo)})
    quant = []
    for r in data['quantization']:
        compression = number(r['logical_float32_operand_bytes'])/number(r['logical_int8_operand_bytes'])
        close(compression, number(r['nominal_compression_ratio']), 'logical compression')
        quant.append({**r, 'relative_l2_percent': 100*number(r['relative_l2_vs_float32_same_dag']),
                      'error_vs_complex128_percent': 100*number(r['relative_l2_vs_complex128']),
                      'evidence_class': 'software characterization; not physical timing'})
    mechanisms = []
    for r in data['mechanisms']:
        binding = data.get('historical_bindings', {}).get(r['source_id'], {})
        mechanisms.append({**r, 'history_url': binding.get('url', ''),
                           'history_sha256': binding.get('sha256', ''),
                           'synthesis_treatment': 'unverified context transcription; do not use as a new measured numeric claim'
                           if 'chat_context' in r['provenance_class'] else 'reported historical finding; not raw-data recomputation'})
    results = {'cells': cells, 'comparisons': comparisons, 'times': list(recomputed_times.values()),
               'tasklets': [c for c in cells if c['suite'] == 'T'],
               'dpus': [c for c in cells if c['suite'] == 'D'],
               'ablations': [c for c in cells if c['suite'] == 'A'],
               'width': [c for c in cells if c['suite'] == 'W'],
               'cpu_comparison': [r for r in comparisons if r['suite'] == 'W'],
               'frontiers': frontiers, 'accuracy': accuracy, 'circuits': circuits,
               'best_resources': best, 'lifecycle': lifecycle, 'p6_aggregates': p6a, 'p6_cells': p6c,
               'p6_methods': data['p6_methods'], 'p6_search': data['p6_search'],
               'quantization': quant, 'mechanisms': mechanisms,
               'contractions': data['final_contractions'], 'plan_facts': data['final_plan_facts']}
    results['accounting'] = []
    for suite in ('T', 'D', 'A', 'W'):
        rs = [r for r in data['final_observations'] if r['suite'] == suite]
        cs = [c for c in cells if c['suite'] == suite]
        results['accounting'].append({'suite': suite, 'cells': len(cs), 'attempts': len(rs),
             'warmups': sum(boolean(r['warmup']) for r in rs),
             'measured_success': sum(not boolean(r['warmup']) and r['status']=='success' for r in rs),
             'measured_unsupported': sum(not boolean(r['warmup']) and r['status']=='unsupported' for r in rs),
             'complete_cells': sum(c['complete'] for c in cs)})
    results['claims'] = make_claims(results)
    return results, {'accounting': dict(sorted(counts.items())), 'cells_verified': len(cells),
                     'summary_rows_verified': len(recomputed_times),
                     'paired_comparisons_verified': len(comparisons),
                     'final_bootstrap_intervals_reproduced': verify_intervals,
                     'p6_intervals': 'imported unchanged; no new inference',
                     'numerical_qualification': 'recorded flag and available scalar bounds checked; statevectors and elementwise tolerance not re-evaluated',
                     'native_archive_verification': 'not performed by synthesis; Git package checksums only'}


def make_claims(results):
    rows = []
    def add(cid, text, dataset, selection, limit):
        rows.append({'claim_id': cid, 'statement': text, 'dataset': dataset, 'row_selector': selection,
                     'limitation': limit})
    for b in results['best_resources']:
        add(f'{b["suite"]}-{b["case_id"]}-{b["fixed_tasklets"]}',
            f'Lowest observed prepared-call median at {b["best_observed_resource"]} '
            f'{"tasklets" if b["suite"]=="T" else "DPUs"}; endpoint speedup {b["endpoint_ratio_vs_one"]:.4f}x.',
            'best_resources.csv', json.dumps({k:b[k] for k in ('suite','case_id','fixed_tasklets')},sort_keys=True),
            b['claim_limit'])
    for c in results['comparisons']:
        if c['suite'] != 'A' or c['metric'] != 'prepared_call_s':
            continue
        add('A-'+c['case_id']+'-'+c['comparison'],
            f'{c["comparison"]}: baseline/alternative {c["ratio"]:.4f}x; '
            f'descriptive interval [{c["descriptive_low"]:.4f}, {c["descriptive_high"]:.4f}].',
            'comparisons.csv',json.dumps({k:c[k] for k in ('suite','case_id','comparison','metric')},sort_keys=True),
            'Matched final-source cell. Interval is not an equivalence test; A0 already uses the panel kernel.')
    for f in results['frontiers']:
        add('F-'+f['family']+'-'+f['arm_id'],
            f'Largest qualified tested point: {f["largest_fully_measured_qubits"]} total qubits.',
            'frontiers.csv',json.dumps({k:f[k] for k in ('family','arm_id')},sort_keys=True),
            f'{f["boundary"]}; not an absolute supported-size maximum.')
    for family in FAMILIES:
        rs = [r for r in results['cpu_comparison'] if r['family']==family and r['numerator']=='quest32_p8'
              and r['metric']=='job_to_state_s']
        if rs:
            wins = sum(r['ratio']>1 for r in rs)
            add('CPU-'+family, f'UPMEM had lower median job-to-state time than QuEST P8 at {wins}/{len(rs)} mutually qualified widths.',
                'cpu_comparison.csv',family+' / quest32_p8 / job_to_state_s',
                'Fixed greedy D64/T24 UPMEM; QuEST is a conventional reference, not a proven SOTA optimum. Missing UPMEM points excluded from ratios, not coverage.')
    for r in results['p6_aggregates']:
        if r['group']=='all' and r['metric']=='session_inclusive_s':
            add('P6-'+r['contrast'],f'Accepted family-balanced {r["contrast"]}: {r["ratio"]:.6f}x.',
                'p6_aggregates.csv','all / '+r['contrast']+' / session_inclusive_s',
                'Original P6 only; no pooling with new campaign. R/U near one does not establish equivalence or justify retroactive method rejection.')
    regressions = [r for r in results['p6_cells'] if r['contrast']=='G/U'
                   and r['metric']=='session_inclusive_s' and r['ratio'] < 1]
    if regressions:
        worst = min(regressions, key=lambda r:r['ratio'])
        add('P6-regressions',
            f'U was slower than G in {len(regressions)}/12 cells; worst G/U={worst["ratio"]:.6f}x '
            f'({worst["denominator_time_increase_pct"]:.2f}% more time for U).',
            'p6_cells.csv',worst['cell_id'],
            'Original inclusive measurement; not proof of an arithmetic slowdown or a causal attribution to one function.')
    add('QUANT', 'Shared-scale int8 has circuit-dependent numerical error; software compression is not physical transfer reduction.',
        'quantization.csv','all','Software characterization and historical physical timing are distinct; no universal int8 tolerance is invented.')
    return rows


def csv_write(path, rows):
    require(rows, f'refusing an empty publication dataset: {path}')
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open('w', encoding='utf-8', newline='') as out:
        writer = csv.DictWriter(out, fieldnames=keys, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def json_write(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def code_hashes():
    paths = ['build.py','plots.py','tables.py','verify.py','SOURCES.json','requirements.txt','README.md']
    paths += [p.relative_to(HERE).as_posix() for p in sorted((HERE/'tests').rglob('*')) if p.is_file() and '__pycache__' not in p.parts]
    return {p: sha((HERE/p).read_bytes()) for p in paths}


def file_hashes(root):
    return {p.relative_to(root).as_posix(): sha(p.read_bytes()) for p in sorted(Path(root).rglob('*'))
            if p.is_file() and p.relative_to(root).as_posix() != 'SHA256SUMS'}


def generate(results, data, out, audit, provenance):
    from plots import render
    from tables import render_tables
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    (out/'data').mkdir()
    for name, rows in results.items():
        csv_write(out/'data'/(name+'.csv'), rows)
    json_write(out/'data/p6_diagnostics.json',data['p6_diagnostics'])
    json_write(out/'LIMITATIONS.json', {
        'historical_numeric_coverage': 'Mechanism ledger is inherited reported context, not new raw-data reconstruction. Unverified context transcriptions are explicitly identified.',
        'physical_quantization': 'No route-by-route physical int8 timing CSV is consumed by this synthesis. Physical outcomes are historical narrative; numerical plots use software-characterization CSV only.',
        'historical_baseline': 'The historical sequential document defines its diagnostic control but is not a raw timing table. A0 is a separately measured final-source baseline, already using WRAM panels.',
        'new_campaign': 'Fixed greedy UPMEM D64/T24 width arm, not post-selected best resource/path. No extrapolation beyond the declared grid.',
        'archive_access': 'Native raw archives are not fetched or re-executed. Source verification covers pinned Git objects and accepted compact-package checksums.'})
    json_write(out/'data/environment_record.json',{
        key: data['binding'].get(key) for key in ('host','system','cpu_cpus','numa_node','governors','lscpu','packages','capacity','rank_inventory')})
    figs, renderer = render(results, data, out)
    tabs = render_tables(results, out)
    csv_write(out/'FIGURES.csv', figs)
    csv_write(out/'TABLES.csv', tabs)
    json_write(out/'VALIDATION.json', audit)
    json_write(out/'PROVENANCE.json', {**provenance, 'renderer': renderer})
    lines = ['# Thesis synthesis', '',
             'Frozen evidence is unchanged. All final-campaign summaries were checked against its measurement CSV.',
             'Ratios are numerator time / denominator time; values above one favour the denominator.',
             'Final campaign intervals reproduce the existing paired-block calculation; P6 intervals are imported.', '',
             '## Accounting', '',
             '| Suite | Cells | Attempts | Warmups | Measured success | Measured unsupported |',
             '|---|---:|---:|---:|---:|---:|']
    for a in results['accounting']:
        lines.append(f'| {a["suite"]} | {a["cells"]} | {a["attempts"]} | {a["warmups"]} | {a["measured_success"]} | {a["measured_unsupported"]} |')
    lines += ['', '## Findings', '']
    for c in results['claims']:
        if c['claim_id'].startswith(('T-','D-','CPU-','P6-')) or 'matched_combined_executor' in c['claim_id']:
            lines.append(f'- **{c["claim_id"]}:** {c["statement"]} {c["limitation"]}')
    lines += ['', '## Historical and numerical evidence', '',
              'The 32-entry mechanism ledger preserves positive, negative, mixed and exploratory findings.',
              'Historical narrative transcriptions are not reconstructed observations. Entries marked as chat-context transcriptions remain unverified numeric context.',
              'Quantization plots use the software-characterization CSV, not new physical measurements. Physical int8 replay and topology findings remain historical.', '',
              '## Use', '',
              'Use FIGURES.csv and TABLES.csv for captions, source datasets and limitations. SVG is the vector format for Typst; PNG is for inspection.',
              'Typst fragments use local formatting and require no third-party Typst package. Include tables from tables/*.typ; gallery.typ is a standalone inspection document.',
              'Source references and per-input hashes are in PROVENANCE.json. Full observation receipts and original native archives are not revalidated by this synthesis.',
              'No GPU, energy, new circuit, new benchmark, path search, threshold change or model refit is included.', '']
    (out/'RESULTS.md').write_text('\n'.join(lines),encoding='utf-8')
    hashes = file_hashes(out)
    (out/'SHA256SUMS').write_text(''.join(f'{h}  {p}\n' for p,h in hashes.items()),encoding='utf-8')


def build(repo, destination):
    config = json.loads((HERE/'SOURCES.json').read_text())
    loader = GitSources(repo, config)
    data = loader.load()
    results, audit = derive(data, config)
    audit['package_checks'] = loader.package_checks
    provenance = {'schema':'thesis_synthesis_provenance_v1',
                  'evidence_commit':config['evidence_commit'],
                  'implementation_commit':config['implementation_commit'],
                  'synthesis_code_sha256':code_hashes(),
                  'sources':dict(sorted(loader.used.items()))}
    target = Path(destination).resolve()
    require(not target.exists(), f'output exists; preserve it and choose a new path: {target}')
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.synthesis-build-',dir=target.parent))
    try:
        generate(results, data, stage/'result', audit, provenance)
        (stage/'result').rename(target)
    finally:
        shutil.rmtree(stage)
    print(f'Built {len(file_hashes(target))} checksummed artifacts in {target}')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',default=str(HERE.parents[1]))
    p.add_argument('--output',default=str(HERE/'generated'))
    a = p.parse_args()
    build(a.repo, a.output)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, subprocess.CalledProcessError) as exc:
        print('SYNTHESIS STOP: '+str(exc),file=sys.stderr)
        raise SystemExit(1)
