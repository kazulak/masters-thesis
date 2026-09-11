#!/usr/bin/env python3
"""Verify and copy the already accepted P6 readout; do not refit or recalculate it."""
import argparse
from pathlib import Path
import shutil
import final_eval as f


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();source=Path(a.source).resolve();out=Path(a.output).resolve();f.check_source(source)
    package=source/'thesis/implementation/thesis_results/upmem_cost_guided_path_v1'
    f.require(not out.exists(),'new P6 readout destination required')
    for line in (package/'SHA256SUMS').read_text().splitlines():
        checksum,path=line.split('  ',1)
        target=(package/path).resolve()
        f.require(package in target.parents,'invalid P6 checksum path')
        f.require(f.digest(target)==checksum,'P6 package checksum mismatch')
    out.mkdir(parents=True)
    for path in sorted((package/'readout').iterdir()):
        if path.is_file():shutil.copyfile(path,out/path.name)
    f.write(out/'SOURCE.json',dict(original_results_commit='8df2ebac61bacd08309ea490309be5a8dcb943b2',
        current_source_commit=f.FROZEN,original_package_manifest_sha256=f.digest(package/'SHA256SUMS'),
        copied_without_recalculation=True))
    print(out)


if __name__=='__main__':main()
