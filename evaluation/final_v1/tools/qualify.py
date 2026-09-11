#!/usr/bin/env python3
"""Once-only qualification of the new bridge/resource grid; never a speedup dataset."""
import argparse
import fcntl
from pathlib import Path
import sys
import final_eval as fe


def qualification_arms(spec, capacity):
    # Every tasklet build, every selected DPU count at T8, and the T24 endpoint.
    resources={(1,t) for t in spec['tasklets']}
    resources |= {(d,8) for d in fe.dpu_grid(capacity,spec)} | {(capacity,24)}
    return [fe.up(d,t,policy=p) for d,t in sorted(resources) for p in (fe.F32,fe.I8)]


def fixture_cases():
    small=[dict(case_id='qual_'+fe.case_id(f,5 if f=='edc' else 4),family=f,
                n=5 if f=='edc' else 4,layers=1,width_slot=4,role='qualification')
           for f in ('bb84','bv','edc','hs','qrng','xor','ghz')]
    for layers in (1,2,4,8):
        small.append(dict(case_id=f'qual_stress_n04_l{layers}',family='stress',n=4,
                    layers=layers,width_slot=4,role='qualification'))
    for f in ('ghz','stress'):
        small.append(dict(case_id=f'qual_{f}_n06',family=f,n=6,layers=2 if f=='stress' else 1,
                    width_slot=6,role='resource_qualification'))
    return small


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True);p.add_argument('--work',required=True)
    p.add_argument('--allow-physical',action='store_true')
    a=p.parse_args()
    fe.require(a.allow_physical,'explicit --allow-physical is required')
    source,work=Path(a.source).resolve(),Path(a.work).resolve()
    b=fe.verify_binding(source,work);spec=b['specification'];fe.host_checks(spec,b['cpu_cpus'])
    directory=work/'qualification'
    fe.require(not directory.exists() and not (work/'qualified.json').exists(),
               'qualification already attempted; no implicit rerun')
    directory.mkdir();fe.imports(source)
    fixtures=fixture_cases();arms=qualification_arms(spec,b['capacity'])
    fe.require(len(arms)*2 <= 200,'qualification physical limit exceeded')
    write=fe.write
    for c in fixtures:
        cid=c['case_id'];cp=work/'case_records'/(cid+'.json')
        (work/'cases'/(cid+'.qasm')).write_bytes(fe.qasm_for(c));write(cp,c)
        result=fe.call_worker(source,work,'plan',cp,work/'plans'/(cid+'.json'),cpus=[b['cpu_cpus'][0]])
        fe.require('path' in result, f'qualification planner failed: {cid}')
        result=fe.call_worker(source,work,'reference',cp,work/'reference_records'/(cid+'.json'),
                            cpus=[b['cpu_cpus'][0]],quest64=b['quest64'])
        fe.require(result.get('status')=='success',f'double QuEST / complex128 semantic check failed: {cid}')
    for c in fixtures:
        for threads in sorted({1,len(b['cpu_cpus'])}):
            arm=dict(backend='quest32',threads=threads);ap=directory/(fe.arm_id(arm)+'.arm.json')
            if not ap.exists():write(ap,arm)
            result=fe.call_worker(source,work,'cpu',work/'case_records'/(c['case_id']+'.json'),
                    directory/(c['case_id']+'__'+fe.arm_id(arm)+'.json'),arm=ap,
                    cpus=b['cpu_cpus'] if threads>1 else [b['cpu_cpus'][0]],quest32=b['quest32'])
            fe.require(result.get('status')=='success' and result.get('accuracy_qualified') is True,
                       'single precision QuEST bridge qualification failed')
    # All resource combinations also pass the SDK simulator, but simulator time is not evidence.
    for mode in ('simulator','physical'):
        lockpath=Path.home()/'evidence/upmem-experiment.lock';lockpath.parent.mkdir(parents=True,exist_ok=True)
        with lockpath.open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            fe.rank_free()
            for arm in arms:
                aid=fe.arm_id(arm);ap=directory/(aid+'.arm.json')
                if not ap.exists():write(ap,arm)
                for c in fixtures[-2:]:
                    fe.rank_free()
                    out=directory/(mode+'__'+c['case_id']+'__'+aid+'.json')
                    write(str(out)+'.issued.json',dict(mode=mode,case_id=c['case_id'],arm=arm))
                    r=fe.call_worker(source,work,mode,work/'case_records'/(c['case_id']+'.json'),out,
                                     arm=ap,cpus=[b['cpu_cpus'][0]])
                    fe.rank_free()
                    fe.require(r.get('status')=='success',f'{mode} resource qualification failed: {out}')
                    fe.require(r['metrics'].get('same_policy_passed') is True,'missing replay qualification')
                    if arm['policy']==fe.F32:
                        fe.require(r.get('accuracy_qualified') is True,'float32 qualification error')
    # Binding identifies actual binaries, source, environment and full evaluation package.
    receipts={p.relative_to(work).as_posix():fe.digest(p) for p in sorted(directory.rglob('*')) if p.is_file()}
    write(work/'qualified.json',dict(schema='thesis_final_qualification_v1',passed=True,
         binding_sha256=fe.digest(work/'binding.json'),physical_attempts=len(arms)*2,
         simulator_attempts=len(arms)*2,reference_cases=len(fixtures),receipt_sha256=receipts,
         qualification_not_performance=True))
    print('Qualification passed; no simulator/qualification timings enter benchmark tables.')


if __name__=='__main__':
    main()
