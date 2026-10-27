import subprocess
import tempfile
import unittest
from pathlib import Path

from ponyexpress.core import CapsuleError, assemble, publish, verify_capsule


def git(directory: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=directory, check=True, text=True,
                          capture_output=True).stdout.strip()


def source_repository(tmp_path: Path) -> Path:
    repo = tmp_path / "source"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.email", "pony@example.test")
    git(repo, "config", "user.name", "Pony")
    (repo / "bin").mkdir()
    executable = repo / "bin" / "run"
    executable.write_text("#!/bin/sh\necho pony\n")
    executable.chmod(0o755)
    (repo / "linked").symlink_to("bin/run")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "initial")
    return repo


class CapsuleTests(unittest.TestCase):
    def test_publish_verify_and_assemble_preserves_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            source = source_repository(tmp_path)
            capsules = tmp_path / "capsules"
            manifest_path = publish(str(source), "HEAD", capsules, 64 * 1024, "example")
            manifest = verify_capsule(manifest_path, manifest_path.parent)
            self.assertEqual(manifest["source"]["commit"], git(source, "rev-parse", "HEAD"))

            output = tmp_path / "assembled"
            assemble(manifest_path, manifest_path.parent, output)
            self.assertEqual((output / "bin" / "run").read_text(), "#!/bin/sh\necho pony\n")
            self.assertTrue((output / "bin" / "run").stat().st_mode & 0o111)
            self.assertTrue((output / "linked").is_symlink())
            self.assertEqual((output / "linked").readlink(), Path("bin/run"))

    def test_verify_rejects_tampered_chunk(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            source = source_repository(tmp_path)
            manifest_path = publish(str(source), "HEAD", tmp_path / "capsules", 64 * 1024, "example")
            chunk = next((manifest_path.parent / "chunks").iterdir())
            chunk.write_text("corrupted\n")
            with self.assertRaisesRegex(CapsuleError, "SHA-256"):
                verify_capsule(manifest_path, manifest_path.parent)
