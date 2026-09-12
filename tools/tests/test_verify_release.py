import gzip
import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("verify_release", Path(__file__).resolve().parents[1] / "verify_release.py")
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


class ReleaseVerificationTests(unittest.TestCase):
    def test_missing_json_can_use_declared_gzip_without_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = b'{"accepted": true}\n'
            (root / "accepted_evaluation_rows.json.gz").write_bytes(gzip.compress(payload))
            sums = root / "SHA256SUMS"
            sums.write_text(hashlib.sha256(payload).hexdigest() + "  accepted_evaluation_rows.json\n")
            with self.assertRaises(ValueError):
                verify.verify_checksum_manifest(sums)
            self.assertEqual(verify.verify_checksum_manifest(sums, allow_gzip=True)[1], ["accepted_evaluation_rows.json"])
            self.assertFalse((root / "accepted_evaluation_rows.json").exists())
            (root / "accepted_evaluation_rows.json.gz").write_bytes(gzip.compress(b"changed"))
            with self.assertRaises(ValueError):
                verify.verify_checksum_manifest(sums, allow_gzip=True)

    def test_checksum_paths_and_duplicates_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "SHA256SUMS"
            for names in (["../outside"], ["/outside"], ["a", "./a"]):
                with self.subTest(names=names):
                    path.write_text("".join("0" * 64 + "  " + n + "\n" for n in names))
                    with self.assertRaises(ValueError):
                        verify.checksum_entries(path)

    def test_raw_archive_members_and_outer_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "evidence.tar.gz"
            with tarfile.open(path, "w:gz") as archive:
                member = tarfile.TarInfo("run/a.json")
                member.size = 2
                archive.addfile(member, io.BytesIO(b"{}"))
            inventory = root / "inventory.sha256"
            inventory.write_text(hashlib.sha256(b"{}").hexdigest() + "  run/a.json\n")
            expected = dict(size_bytes=path.stat().st_size, sha256=verify.file_sha256(path), file_count=1, payload_bytes=2)
            self.assertEqual(verify.verify_archive(path, expected, inventory)["files"], 1)
            self.assertFalse((root / "run").exists())
            inventory.write_text("0" * 64 + "  run/a.json\n")
            with self.assertRaises(ValueError):
                verify.verify_archive(path, expected, inventory)
            path.write_bytes(b"tampered")
            with self.assertRaises(ValueError):
                verify.verify_archive(path, expected, inventory)

    def test_links_are_rejected_even_with_matching_outer_checksum(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "evidence.tar.gz"
            with tarfile.open(path, "w:gz") as archive:
                member = tarfile.TarInfo("run/link")
                member.type = tarfile.SYMTYPE
                member.linkname = "../../outside"
                archive.addfile(member)
            inventory = root / "inventory.sha256"
            inventory.write_text("0" * 64 + "  run/link\n")
            expected = dict(size_bytes=path.stat().st_size, sha256=verify.file_sha256(path), file_count=1, payload_bytes=0)
            with self.assertRaises(ValueError):
                verify.verify_archive(path, expected, inventory)


if __name__ == "__main__":
    unittest.main()
