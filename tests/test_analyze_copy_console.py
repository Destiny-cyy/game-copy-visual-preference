import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AnalyzeCopyConsoleTest(unittest.TestCase):
    def test_cp936_console_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ)
            env["PYTHONIOENCODING"] = "cp936"
            command = [
                sys.executable,
                "skills/ad-material-review/scripts/analyze_copy.py",
                "--config", "examples/config.demo.json",
                "--planning", "examples/copy_planning.sample.csv",
                "--labels", "examples/copy_labels.sample.json",
                "--master", "examples/copy_master.sample.csv",
                "--tagged", "examples/copy_tagged.sample.csv",
                "--index", "examples/copy_index.sample.csv",
                "--out-base", str(Path(tmp) / "copy_base.csv"),
                "--out-json", str(Path(tmp) / "copy_results.json"),
            ]
            result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True)
            self.assertEqual(0, result.returncode, result.stderr.decode("cp936", errors="replace"))


if __name__ == "__main__":
    unittest.main()
