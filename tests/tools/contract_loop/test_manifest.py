import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.contract_loop.manifest import Manifest


class TestManifest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.out = Path(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_dir_hash(self):
        # Create some files
        d = self.out / "subdir"
        d.mkdir()
        (d / "a.txt").write_text("hello", encoding="utf-8")
        (d / "b.txt").write_text("world", encoding="utf-8")

        # Create manifest
        m = Manifest(self.out, ["cmd"], None)
        h1 = m._hash_dir(d)

        # Same content, different timestamps -> should match if we only hash content
        (d / "a.txt").touch()
        h2 = m._hash_dir(d)
        self.assertEqual(h1, h2)

        # Change content
        (d / "a.txt").write_text("hello2", encoding="utf-8")
        h3 = m._hash_dir(d)
        self.assertNotEqual(h1, h3)

    def test_add_attempt(self):
        d = self.out / "out_artifacts"
        d.mkdir()
        (d / "file.txt").write_text("stuff")

        m = Manifest(self.out, ["cmd"], None)
        m.add_step_attempt("step1", 1, "success", 0.5, ["out_artifacts"])

        with open(self.out / "manifest.json") as f:
            data = json.load(f)

        self.assertEqual(data["command_line"], ["cmd"])
        step = data["steps"][0]
        self.assertEqual(step["step"], "step1")
        self.assertEqual(step["status"], "success")
        self.assertIsNotNone(step["output_hash"])
        self.assertEqual(step["artifacts"], ["out_artifacts"])


if __name__ == "__main__":
    unittest.main()
