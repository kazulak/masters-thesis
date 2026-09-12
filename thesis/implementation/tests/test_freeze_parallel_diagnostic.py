"""Archive verification must never follow archive-controlled filesystem links."""
import importlib.util
import io
from pathlib import Path
import sys
import tarfile

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("freeze_parallel_diagnostic", SCRIPTS / "freeze_parallel_diagnostic.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def archive(path, entries):
    with tarfile.open(path, "w:gz") as out:
        for name, kind in entries:
            member = tarfile.TarInfo(name)
            member.type = kind
            member.mode = 0o755 if kind == tarfile.DIRTYPE else 0o644
            member.linkname = "../outside"
            member.size = 1 if kind == tarfile.REGTYPE else 0
            out.addfile(member, io.BytesIO(b"x") if member.isfile() else None)


@pytest.mark.parametrize("name,kind", [
    ("../outside", tarfile.REGTYPE), ("/outside", tarfile.REGTYPE),
    ("root/link", tarfile.SYMTYPE), ("root/link", tarfile.LNKTYPE),
    ("root/fifo", tarfile.FIFOTYPE), ("root/device", tarfile.CHRTYPE),
    ("root//alias", tarfile.REGTYPE), ("root/./alias", tarfile.REGTYPE),
])
def test_preflight_rejects_unsafe_members_before_writing(tmp_path, name, kind):
    source = tmp_path / "data.tar.gz"
    archive(source, [("root/good", tarfile.REGTYPE), (name, kind)])
    with pytest.raises(ValueError):
        module._safe_extract(source, tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("entries", [
    [("root/x", tarfile.REGTYPE), ("root/x", tarfile.REGTYPE)],
    [("root/x", tarfile.REGTYPE), ("root/x/y", tarfile.REGTYPE)],
    [("root/x", tarfile.REGTYPE), ("other/x", tarfile.REGTYPE)],
    [("root", tarfile.REGTYPE)], [],
])
def test_preflight_rejects_conflicting_layout(tmp_path, entries):
    source = tmp_path / "data.tar.gz"
    archive(source, entries)
    with pytest.raises(ValueError):
        module._safe_extract(source, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_extracts_regular_archive_and_rejects_reused_destination(tmp_path):
    source = tmp_path / "data.tar.gz"
    archive(source, [("root", tarfile.DIRTYPE), ("root/file", tarfile.REGTYPE)])
    target = tmp_path / "out"
    root = module._safe_extract(source, target)
    assert (root / "file").read_bytes() == b"x"
    with pytest.raises(ValueError):
        module._safe_extract(source, target)
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError):
        module._safe_extract(source, link)
