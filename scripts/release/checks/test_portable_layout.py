"""Packaging checks that do not start Capri or access user devices."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import capri_dev
from capri import config
from scripts.release.smoke import run
from scripts.release.entrypoint import main as release_main


class PortableLayoutTests(unittest.TestCase):
    def test_first_config_preserves_existing_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / "config.yaml"
            target.write_text("user_name: Existing\n", encoding="utf-8")
            with patch.object(config, "ROOT", root):
                capri_dev._first_config()
            self.assertEqual(target.read_text(encoding="utf-8"), "user_name: Existing\n")

    def test_first_config_copies_portable_defaults(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(config, "ROOT", root):
                capri_dev._first_config()
            self.assertIn("edition: dev", (root / "config.yaml").read_text(encoding="utf-8"))

    def test_frozen_resources_are_separate_from_writable_home(self):
        script = """
import json, sys
sys.frozen = True
sys._MEIPASS = sys.argv[1]
from capri.config import ROOT, ASSETS
print(json.dumps([str(ROOT), str(ASSETS)]))
"""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bundle = root / "bundle"
            home = root / "home"
            env = dict(os.environ, CAPRI_HOME=str(home))
            result = subprocess.run([sys.executable, "-c", script, str(bundle)],
                                    capture_output=True, text=True, check=True, env=env)
            paths = json.loads(result.stdout)
            self.assertEqual(paths, [str(home.resolve()), str(bundle / "assets")])

    def test_smoke_requires_report_path_without_starting_gui(self):
        with patch.object(sys, "argv", ["Capri.exe", "--smoke-test"]):
            with self.assertRaises(SystemExit) as raised:
                release_main()
        self.assertEqual(raised.exception.code, 2)

    def test_smoke_refuses_to_modify_normal_user_home(self):
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / "report.json"
            env = {key: value for key, value in os.environ.items() if key != "CAPRI_HOME"}
            with patch.dict(os.environ, env, clear=True):
                self.assertEqual(run(str(report)), 1)
            result = json.loads(report.read_text(encoding="utf-8"))
            self.assertFalse(result["ok"])
            self.assertIn("isolated CAPRI_HOME", result["error"])


if __name__ == "__main__":
    unittest.main()
