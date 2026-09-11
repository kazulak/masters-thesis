#!/usr/bin/env python3
"""Verify a generated synthesis and independently rebuild it without changing any evidence."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

from build import HERE, build, file_hashes, require, sha


def check_directory(root):
    root=Path(root).resolve()
    require(root.is_dir(),'missing generated output')
    require(not any(p.is_symlink() for p in root.rglob('*')),'symlink in generated output')
    expected={}
    for line in (root/'SHA256SUMS').read_text().splitlines():
        m=re.fullmatch(r'([0-9a-f]{64})  (.+)',line)
        require(m is not None,'invalid generated checksum line')
        h,p=m.groups()
        require(p not in expected and not Path(p).is_absolute() and '..' not in Path(p).parts,'unsafe checksum member')
        expected[p]=h
    require(expected==file_hashes(root),'generated file set or checksum mismatch')
    for name in ('FIGURES.csv','TABLES.csv'):
        with (root/name).open(newline='') as fp: rows=list(csv.DictReader(fp))
        require(rows,'empty artifact index')
        for row in rows:
            for dataset in row['source_dataset'].split(';'):
                rel=Path(dataset.strip())
                require(not rel.is_absolute() and '..' not in rel.parts and (root/rel).is_file(),
                        'artifact index has a missing/unsafe dataset: '+str(rel))
            for key in (('svg','png') if name=='FIGURES.csv' else ('typst',)):
                path=root/row[key]
                require(path.is_file() and path.stat().st_size>100,'missing/empty artifact: '+str(path))
                if key=='svg':
                    document=ET.parse(path)
                    require(document.getroot().tag.endswith('svg'),'invalid SVG')
                elif key=='png':
                    require(path.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'),'invalid PNG')
                else:
                    text=path.read_text()
                    require('table.header(repeat: true' in text and '#{' in text,'invalid table template')
                    require('\\begin{' not in text,'unexpected LaTeX')
    return expected


def compile_typst(root, binary, output):
    require(shutil.which(binary) is not None or Path(binary).is_file(),'Typst compiler missing; do not label this gate passed')
    version=subprocess.check_output([binary,'--version'],text=True).strip()
    subprocess.run([binary,'compile',str(Path(root)/'gallery.typ'),str(output)],check=True)
    require(Path(output).is_file() and Path(output).stat().st_size>1000,'Typst output missing')
    return version


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',default=str(HERE.parents[1]))
    p.add_argument('--output',default=str(HERE/'generated'))
    p.add_argument('--typst',help='Compiler path/name; required for the publication operator gate')
    p.add_argument('--typst-proof',help='PDF proof path outside canonical generated output')
    args=p.parse_args()
    hashes=check_directory(args.output)
    with tempfile.TemporaryDirectory(prefix='thesis-synthesis-independent-') as tmp:
        fresh=Path(tmp)/'rebuilt'
        build(args.repo,fresh)
        other=check_directory(fresh)
        require(hashes==other,'independent rebuild differs; inspect renderer/source identities; do not overwrite')
        require((Path(args.output)/'SHA256SUMS').read_bytes()==(fresh/'SHA256SUMS').read_bytes(),'manifest differs')
    if args.typst:
        require(args.typst_proof,'supply --typst-proof outside generated/; avoid polluting checked output')
        proof=Path(args.typst_proof).resolve();root=Path(args.output).resolve()
        require(root not in proof.parents,'Typst proof must be outside generated output')
        require(not proof.exists(),'do not overwrite Typst proof')
        print('Typst compiled:',compile_typst(root,args.typst,proof))
    else:
        print('Typst compilation: NOT RUN (static template/SVG checks passed only)')
    print(f'PASS: {len(hashes)} artifacts; hashes and independent full rebuild identical.')


if __name__=='__main__':
    try:main()
    except (ValueError,subprocess.CalledProcessError) as exc:
        print('VERIFICATION STOP: '+str(exc),file=sys.stderr);raise SystemExit(1)
