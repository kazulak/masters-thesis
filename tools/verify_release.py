#!/usr/bin/env python3
"""Read-only compact/raw evidence verification. No campaign execution or extraction."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile

BASELINE = "c7c6cac0b55bdff2f4c24b70397b36f89bedc45f"
RESULTS = "thesis/implementation/thesis_results"
GZIP_MANIFESTS = {
    f"{RESULTS}/upmem_cost_guided_path_v1/readout/SHA256SUMS",
    f"{RESULTS}/final_evaluation_v1/original_p6_readout/SHA256SUMS",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def stream_sha256(stream):
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
    return digest.hexdigest()


def file_sha256(path):
    with Path(path).open("rb") as stream:
        return stream_sha256(stream)


def safe_name(name):
    path = PurePosixPath(name)
    require(bool(path.parts) and not path.is_absolute() and ".." not in path.parts
            and "\\" not in name, f"unsafe relative path: {name}")
    return path.as_posix()


def checksum_entries(path):
    entries = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, name = line.split("  ", 1)
        name = safe_name(name)
        require(re.fullmatch(r"[0-9a-f]{64}", digest) is not None, "invalid SHA-256")
        require(name not in entries, f"duplicate checksum name: {name}")
        entries[name] = digest
    require(entries, f"empty checksum manifest: {path}")
    return entries


def verify_checksum_manifest(manifest, root=None, allow_gzip=False):
    root = (Path(root) if root else Path(manifest).parent).resolve()
    entries = checksum_entries(manifest)
    decompressed = []
    for name, expected in entries.items():
        path = root / name
        require(path.resolve().is_relative_to(root), f"checksum escapes root: {name}")
        if not path.exists() and allow_gzip and name == "accepted_evaluation_rows.json":
            path = path.with_suffix(path.suffix + ".gz")
            require(path.resolve().is_relative_to(root), "gzip escapes root")
            with gzip.open(path, "rb") as stream:
                actual = stream_sha256(stream)
            decompressed.append(name)
        else:
            require(path.is_file() and not path.is_symlink(), f"missing regular file: {name}")
            actual = file_sha256(path)
        require(actual == expected, f"checksum mismatch: {name}")
    return len(entries), decompressed


def verify_archive(path, expected, inventory):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), f"missing archive: {path.name}")
    require(path.stat().st_size == expected["size_bytes"], f"archive size mismatch: {path.name}")
    require(file_sha256(path) == expected["sha256"], f"archive digest mismatch: {path.name}")
    wanted = checksum_entries(inventory)
    seen = set()
    payload = 0
    # Stream member bytes. Never materialize archive-controlled paths on disk.
    with tarfile.open(path, "r|gz") as archive:
        for member in archive:
            require(member.isfile() or member.isdir(), f"unsafe member type: {member.name}")
            if member.isdir() and member.name in (".", "./"):
                continue
            name = safe_name(member.name)
            if member.isdir():
                continue
            require(name in wanted and name not in seen, f"unexpected/duplicate member: {name}")
            with archive.extractfile(member) as stream:
                actual = stream_sha256(stream)
            require(actual == wanted[name], f"member digest mismatch: {name}")
            seen.add(name)
            payload += member.size
    require(seen == set(wanted), f"missing archive members: {path.name}")
    require(len(seen) == expected["file_count"], "archive member count mismatch")
    require(payload == expected["payload_bytes"], "archive payload size mismatch")
    return dict(name=path.name, sha256=expected["sha256"], files=len(seen), payload_bytes=payload)


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def verify(repo, archives=None):
    repo = Path(repo).resolve()
    require(git(repo, "rev-parse", "--is-shallow-repository") == "false", "full Git history is required")
    git(repo, "cat-file", "-e", BASELINE + "^{commit}")
    inventory = repo / "release/evidence-files.sha256"
    wanted = checksum_entries(inventory)
    baseline_names = set(git(repo, "ls-tree", "-r", "--name-only", BASELINE, "--", RESULTS).splitlines())
    baseline_names.discard(RESULTS + "/README.md")
    require(set(wanted) == baseline_names, "frozen package inventory changed")
    count, _ = verify_checksum_manifest(inventory, repo)
    manifests, representations = 0, []
    for name in sorted(wanted):
        if name.endswith("/SHA256SUMS"):
            _, decompressed = verify_checksum_manifest(repo / name, allow_gzip=name in GZIP_MANIFESTS)
            manifests += 1
            if decompressed:
                representations.append(name)

    provenance = json.loads((repo / "release/provenance.json").read_text())
    for commit in provenance["cited_git_commits"]:
        git(repo, "cat-file", "-e", commit + "^{commit}")
        require(subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", commit, "HEAD"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
                or any(subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", commit, tag],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
                       for tag in provenance["scientific_tags"]),
                f"unanchored scientific commit: {commit}")
    for tag, commit in provenance["scientific_tags"].items():
        require(git(repo, "rev-parse", tag + "^{commit}") == commit, f"moved scientific tag: {tag}")

    sys.path.insert(0, str(repo / "evaluation/unified_v4"))
    spec = importlib.util.spec_from_file_location("release_v4_readout", repo / "evaluation/unified_v4/readout.py")
    readout = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(readout)
    data = repo / RESULTS / "unified_final_v4"
    def load(name):
        return json.loads((data / name).read_text())
    accounting = readout.derive_accounting(*(load(p) for p in (
        "manifest/manifest.json", "final_manifest.json", "calibration_rows.json",
        "final_rows.json", "path_records.json", "retention.json")))
    require(accounting == load("readout/accounting.json"), "accounting differs from frozen ledger")

    index = json.loads((repo / "release/raw-archives.json").read_text())["assets"]
    require(len(index) == 11 and len({e["name"] for e in index}) == 11, "expected eleven unique raw assets")
    for entry in index:
        require(safe_name(entry["name"]) == Path(entry["name"]).name, "archive name must be a basename")
        source = json.loads((repo / safe_name(entry["source_record"])).read_text())
        if entry["kind"] == "path-study":
            record = source["stages"][entry["stage"]]
            require(entry["sha256"] == record["archive_sha256"] and entry["size_bytes"] == record["size_bytes"],
                    "path archive differs from accepted digest")
        elif entry["kind"] == "historical-final-v1":
            require(entry["sha256"] == source["archive_sha256"], "historical archive differs from accepted digest")
        elif entry["kind"] == "unified-v4":
            require(entry["file_count"] == source["archive_files_count"] == 8288, "unified archive count mismatch")
        else:
            raise ValueError("unknown archive kind")
        require(len(checksum_entries(repo / safe_name(entry["inventory"]))) == entry["file_count"], "inventory count mismatch")

    raw_results = []
    if archives is not None:
        for entry in index:
            raw_results.append(verify_archive(Path(archives) / entry["name"], entry,
                                              repo / safe_name(entry["inventory"])))
    return dict(source_commit=git(repo, "rev-parse", "HEAD"), source_tree=git(repo, "rev-parse", "HEAD^{tree}"),
                compact="PASS", frozen_files=count, package_checksum_manifests=manifests,
                historical_gzip_representations=representations, final=accounting["final"],
                physical=accounting["physical"], paths=accounting["paths"],
                raw="PASS" if archives is not None else "NOT CHECKED", archives=raw_results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--archives", type=Path, help="directory containing the eleven downloaded raw assets")
    parser.add_argument("--output", type=Path, help="optional JSON receipt outside accepted evidence")
    args = parser.parse_args()
    try:
        if args.output:
            require(not args.output.resolve().is_relative_to((args.repo / RESULTS).resolve()),
                    "receipt output must not be inside accepted evidence")
        result = verify(args.repo, args.archives)
        text = json.dumps(result, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text)
        print(text, end="")
    except (ValueError, OSError, subprocess.CalledProcessError, tarfile.TarError, EOFError) as exc:
        parser.exit(1, f"Verification failed: {exc}\n")


if __name__ == "__main__":
    main()
