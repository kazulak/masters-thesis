#!/usr/bin/env python3
"""Verify downloaded archive bytes and every member without extracting untrusted paths."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile
import final_eval as f


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive',required=True);p.add_argument('--manifest',required=True)
    p.add_argument('--receipt',required=True)
    a=p.parse_args();record=f.read(a.manifest)
    f.require(f.digest(a.archive)==record['archive_sha256'],'outer archive digest mismatch')
    seen={};prefix=PurePosixPath(record['relative_root'])
    with tarfile.open(a.archive,'r:gz') as tar:
        for member in tar:
            name=PurePosixPath(member.name)
            f.require(not name.is_absolute() and '..' not in name.parts,'unsafe archive member path')
            f.require(not (member.issym() or member.islnk() or member.isdev()),'unsafe archive member type')
            if member.isdir():continue
            f.require(member.isfile(),'unexpected archive member')
            rel=name.relative_to(prefix).as_posix() if str(prefix)!='.' else name.as_posix()
            f.require(rel not in seen,'duplicate archive member')
            stream=tar.extractfile(member);h=hashlib.sha256()
            for part in iter(lambda:stream.read(1024*1024),b''):h.update(part)
            seen[rel]=h.hexdigest()
    f.require(seen==record['files'],'archive member hashes/set differ')
    f.write(a.receipt,dict(schema='thesis_final_retention_receipt_v1',archive_sha256=record['archive_sha256'],
            member_count=len(seen),passed=True))
    print(f'{len(seen)} members verified; archive {record["archive_sha256"]}')


if __name__=='__main__':main()
