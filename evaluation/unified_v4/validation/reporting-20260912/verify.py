#!/usr/bin/env python3
"""Verify the published local validation records without executing experiments."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def outcomes(path):
    result = {}
    for case in ET.parse(path).getroot().iter('testcase'):
        identity = (case.attrib['classname'], case.attrib['name'])
        require(identity not in result, f'duplicate test identity: {identity}')
        status = next((name for tag, name in [('failure', 'failed'), ('error', 'error'),
                                             ('skipped', 'skipped')] if case.find(tag) is not None), 'passed')
        result[identity] = status
    require(result, f'empty JUnit record: {path.name}')
    return result


def main():
    for line in (HERE / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        require(Path(name).name == name, f'unsafe package member: {name}')
        require(hashlib.sha256((HERE / name).read_bytes()).hexdigest() == digest,
                f'checksum mismatch: {name}')

    receipt = json.loads((HERE / 'CORRECTION_AUDIT.json').read_text())
    commit = receipt['corrected_commit']
    require(re.fullmatch('[0-9a-f]{40}', commit), 'invalid audited commit')
    for name, digest in receipt['reviewed_source_sha256'].items():
        data = subprocess.check_output(['git', '-C', str(REPO), 'show', f'{commit}:{name}'])
        require(hashlib.sha256(data).hexdigest() == digest, f'audited source hash mismatch: {name}')

    initial = outcomes(HERE / 'implementation-tests.xml')
    rerun = outcomes(HERE / 'durable-archive-test.xml')
    require(dict(Counter(initial.values())) == receipt['implementation_tests']['initial'],
            'initial implementation counts disagree with receipt')
    failed = {identity for identity, status in initial.items() if status == 'failed'}
    require(set(rerun) == failed and all(status == 'passed' for status in rerun.values()),
            'rerun does not resolve precisely the initially failed tests')
    require(len(rerun) == receipt['implementation_tests']['same_commit_durable_rerun']['passed'],
            'rerun count disagrees with receipt')
    resolved = {**initial, **rerun}
    require(all(status == 'passed' for status in resolved.values()), 'unresolved nonpassing test')
    require(len(resolved) == receipt['implementation_tests']['distinct_tests_resolved_passing'],
            'distinct implementation count mismatch')

    other_total = 0
    for suite, expected in receipt['other_test_suites_passed'].items():
        log = (HERE / f'{suite}.log').read_text()
        summaries = re.findall(r'^Ran (\d+) tests? in .+$', log, re.MULTILINE)
        require(summaries == [str(expected)] and re.search(r'^OK$', log, re.MULTILINE),
                f'missing or inconsistent successful suite summary: {suite}')
        require(not re.search(r'^(FAILED|ERROR:|FAIL:)', log, re.MULTILINE), f'nonpassing suite: {suite}')
        other_total += expected
    total = len(resolved) + other_total
    require(total == receipt['distinct_tests_resolved_passing_total'], 'combined distinct test count mismatch')

    hosted = json.loads((HERE / 'HOSTED_CI_STATUS.json').read_text())
    require(hosted['commit'] == commit, 'CI observation refers to a different commit')
    require(all(hosted[key] == 0 for key in ('workflow_run_count', 'check_run_count', 'commit_status_count')),
            'hosted CI observation disagrees with package description')
    print(f'Local validation receipt verified for {commit}.')
    print(f'{len(resolved):,} implementation tests resolved passing + {other_total} additional suite tests = {total:,}.')
    print('Includes one targeted rerun; no hosted CI result is claimed. No experiments executed.')


if __name__ == '__main__':
    main()
