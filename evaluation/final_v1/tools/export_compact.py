#!/usr/bin/env python3
"""Export replayable raw timing rows, frozen specifications and manifests, not large arrays."""
import argparse
from pathlib import Path
import shutil
import final_eval as f


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work',required=True);p.add_argument('--readout',required=True)
    p.add_argument('--p6',required=True);p.add_argument('--p6-figures',required=True);p.add_argument('--retention',required=True)
    p.add_argument('--output',required=True)
    a=p.parse_args();work=Path(a.work);out=Path(a.output)
    f.require(not out.exists(),'new export destination required');f.verify_freeze(work);out.mkdir(parents=True)
    for fn in ('binding.json','prepared.json','qualified.json','freeze.json'):
        shutil.copyfile(work/fn,out/fn)
    for sub in ('cases','case_records','plans','reference_records','arms','suites','admission'):
        dest=out/sub;dest.mkdir()
        for item in sorted((work/sub).iterdir()):
            if item.is_file() and item.suffix in ('.json','.qasm'):
                shutil.copyfile(item,dest/item.name)
    shutil.copytree(a.readout,out/'readout')
    shutil.copytree(a.p6,out/'original_p6_readout')
    shutil.copytree(a.p6_figures,out/'original_p6_figures')
    shutil.copytree(a.retention,out/'retention')
    for filename in ('scope.json','historical_sources.json','historical_results.csv'):
        shutil.copyfile(f.PACKAGE/filename,out/filename)
    (out/'README.md').write_text('# Final evaluation evidence\n\n'
        'Source: f6b570a98a610d41b5b16401a42ce12a94042d38. New campaign data and original P6 data are separate. '
        'readout/observations.csv preserves individual new measurement rows; coverage.csv identifies incomplete or unqualified cells. '
        'The full native receipts and full reference arrays are retained in the independently checksummed archives listed under retention/. '
        'Historical mechanism entries are transcribed from cited records, not reconstructed raw observations. '
        'See evaluation/final_v1 for the measurement/readout code and specification.\n')
    for item in out.rglob('*'):
        f.require(not item.is_symlink(),'symlink in compact export')
        if item.is_file():f.require(item.stat().st_size<50*1024**2,f'oversized Git file: {item}')
    with (out/'SHA256SUMS').open('x') as fp:
        for item in sorted(out.rglob('*')):
            if item.is_file() and item != out/'SHA256SUMS':fp.write(f'{f.digest(item)}  {item.relative_to(out).as_posix()}\n')
    print(out)


if __name__=='__main__':main()
