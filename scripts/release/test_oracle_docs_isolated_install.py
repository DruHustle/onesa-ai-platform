"""Run the actual installed import closure in a separate isolated interpreter."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import oracle_install as installer


class IsolatedInstalledDocsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        source = Path(__file__).resolve().parents[2]
        for installed, relative in installer.DOCS_ALLOWED.items():
            target = self.root / installed
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / relative, target)
        self.runner = self.root / "runners/oracle_docs_runner.py"

    def load(self):
        return subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                "import runpy,sys;runpy.run_path(sys.argv[1],run_name='__import_contract__');print('ISOLATED_INSTALLED_DOCS_IMPORTS_READY_NOT_EXECUTED')",
                str(self.runner),
            ],
            cwd=self.root,
            env={"PATH": os.defpath, "LANG": "C.UTF-8"},
            capture_output=True,
            timeout=15,
            check=False,
        )

    def test_actual_installed_layout_loads_without_inherited_python_paths(self):
        result = self.load()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(
            result.stdout, b"ISOLATED_INSTALLED_DOCS_IMPORTS_READY_NOT_EXECUTED\n"
        )

    def test_old_startup_path_reproduces_missing_sibling_module(self):
        text = self.runner.read_text()
        start = text.index("sys.path[:0] = [")
        end = text.index("\n]", start) + 2
        self.runner.write_text(
            text[:start]
            + "sys.path.insert(0, str(Path(__file__).resolve().parent.parent))"
            + text[end:]
        )
        result = self.load()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"No module named 'oracle_docs_build'", result.stderr)
        self.assertEqual(result.stdout, b"")


if __name__ == "__main__":
    unittest.main()
