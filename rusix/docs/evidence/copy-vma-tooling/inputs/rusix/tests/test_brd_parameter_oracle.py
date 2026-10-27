#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Host-only oracle generation/rejection checks; never compile or execute a guest."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "rusix/scripts/generate-brd-parameter-oracle.py"
REFERENCE = ROOT / "rusix/reference/brd-parameter-fix"
SOURCE = ROOT / "drivers/block/brd.c"
spec = importlib.util.spec_from_file_location("brd_oracle", SCRIPT)
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


class OracleTests(unittest.TestCase):
    def setUp(self):
        self.source = SOURCE.read_bytes()
        self.patch = (REFERENCE / "baseline.patch").read_bytes()
        self.manifest = json.loads((REFERENCE / "manifest.json").read_text())

    def test_exact_output_and_coordinate_only_adaptation(self):
        result = oracle.materialize(SOURCE, REFERENCE / "manifest.json")
        self.assertEqual(oracle.digest(result), self.manifest["output_sha256"])
        self.assertIn(b"if (unlikely(max_part <= 0))", result)
        self.assertLess(result.index(b"if (max_part > DISK_MAX_PARTS)"),
                        result.index(b"if ((1U << MINORBITS) % max_part"))
        self.assertEqual(oracle.adapt_coordinates((REFERENCE / "upstream-proposal.patch").read_bytes()), self.patch)

    def test_original_coordinates_are_not_silently_relocated(self):
        with self.assertRaises(ValueError):
            oracle.apply_exact(self.source, (REFERENCE / "upstream-proposal.patch").read_bytes())

    def test_reject_extra_file_binary_rename_mode_and_missing_newline(self):
        for patch in (
            self.patch + b"diff --git a/extra b/extra\n",
            self.patch + b"GIT binary patch\n",
            self.patch.replace(b"+++ b/drivers/block/brd.c", b"+++ b/elsewhere"),
            self.patch.replace(b"100644", b"100755"),
            self.patch.rstrip(b"\n"),
        ):
            with self.subTest(patch=patch[-50:]), self.assertRaises(ValueError):
                oracle.apply_exact(self.source, patch)

    def test_reject_context_and_hunk_counts(self):
        for patch in (
            self.patch.replace(b"unlikely(!max_part)", b"unlikely(max_part == 0)"),
            self.patch.replace(b"@@ -372,9", b"@@ -372,8"),
            self.patch.replace(b"@@ -382,11", b"@@ -372,11"),
        ):
            with self.subTest(patch=patch[:100]), self.assertRaises(ValueError):
                oracle.apply_exact(self.source, patch)

    def test_every_input_and_output_hash_is_required(self):
        for field in ("baseline_sha256", "proposal_sha256", "patch_sha256", "output_sha256"):
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary)
                for name in ("baseline.patch", "upstream-proposal.patch"):
                    (path / name).write_bytes((REFERENCE / name).read_bytes())
                changed = dict(self.manifest, **{field: "0" * 64})
                (path / "manifest.json").write_text(json.dumps(changed))
                with self.subTest(field=field), self.assertRaises(ValueError):
                    oracle.materialize(SOURCE, path / "manifest.json")

    def test_cli_check_does_not_write_and_failed_generation_preserves_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            output = path / "brd_parameter_fixed.c"
            command = [sys.executable, str(SCRIPT), "--source", str(SOURCE),
                       "--manifest", str(REFERENCE / "manifest.json"), "--output", str(output)]
            subprocess.run(command, check=True, capture_output=True)
            before = output.stat().st_mtime_ns
            subprocess.run(command + ["--check"], check=True, capture_output=True)
            self.assertEqual(output.stat().st_mtime_ns, before)
            good = output.read_bytes()
            wrong_source = path / "source.c"
            wrong_source.write_bytes(self.source + b"/* drift */\n")
            changed = command.copy()
            changed[changed.index("--source") + 1] = str(wrong_source)
            self.assertNotEqual(subprocess.run(changed, capture_output=True).returncode, 0)
            self.assertEqual(output.read_bytes(), good)
            output.write_bytes(b"tampered\n")
            self.assertNotEqual(subprocess.run(command + ["--check"], capture_output=True).returncode, 0)
            self.assertEqual(output.read_bytes(), b"tampered\n")


if __name__ == "__main__":
    unittest.main()
