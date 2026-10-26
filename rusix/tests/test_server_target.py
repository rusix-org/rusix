#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Host-only server profile/provenance gates; no kernel build or guest execution."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
scripts = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(scripts))
import server_target as target

spec = importlib.util.spec_from_file_location("server_ext4", scripts / "test-brd-ext4-vm.py")
ext4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ext4)
SOURCE = scripts.parent / "configs/x86_64-server.config"


class ServerTargetTests(unittest.TestCase):
    def setUp(self):
        self.source = SOURCE.read_text()
        self.rust = target.derive(self.source, "server")
        self.c = target.derive(self.source, "server-c")

    def test_one_canonical_fragment_and_only_core_diff(self):
        self.assertEqual(self.rust, self.source)
        self.assertFalse((SOURCE.parent / "x86_64-server-c.config").exists())
        result = target.compare(self.source, self.rust, self.c)
        self.assertEqual(result["resolved_config_differences"], {target.CORE: ["y", "n"]})
        self.assertIn("# CONFIG_DEBUG_FS is not set", self.rust)
        self.assertIn("CONFIG_NET=y", self.rust)
        self.assertIn("CONFIG_VMLINUX_MAP=y", self.rust)

    def test_derivation_rejects_missing_duplicate_or_noncanonical_selection(self):
        for changed in (
            self.source.replace(f"{target.CORE}=y\n", ""),
            self.source + f"{target.CORE}=y\n",
            self.c,
            self.source.replace("# CONFIG_DEBUG_FS is not set", "CONFIG_DEBUG_FS=y"),
        ):
            with self.subTest(changed=changed[-40:]), self.assertRaises(ValueError):
                target.derive(changed, "server-c")
        with self.assertRaises(ValueError):
            target.derive(self.source, "server-ish")

    def test_derivation_does_not_rewrite_comments(self):
        text = f"# Example {target.CORE}=y\n" + self.source.rstrip("\n")
        derived = target.derive(text, "server-c")
        self.assertTrue(derived.startswith(f"# Example {target.CORE}=y\n"))
        self.assertEqual(target.settings(derived)[target.CORE], "n")

    def test_pair_rejects_extra_resolved_difference(self):
        with self.assertRaises(ValueError):
            target.compare(self.source, self.rust + "CONFIG_TEST_EXTRA=y\n", self.c)
        with self.assertRaises(ValueError):
            target.compare(self.source, self.c, self.rust)
        with self.assertRaises(ValueError):
            target.compare(self.source, self.rust, self.c.replace(f"# {target.CORE} is not set\n", ""))

    def test_runtime_accepts_both_directions_without_debugfs(self):
        for profile, config, core in (("server", self.rust, "rust"), ("server-c", self.c, "c")):
            self.assertEqual(ext4.validate_selection(profile, "implementation=brd-rust", config,
                f"implementation=completion-{core}"), "brd-rust")
            # Broader block suite keeps its old allowlist and DEBUG_FS gate.
            with self.assertRaises(ValueError):
                ext4._common.validate_selection(profile, "implementation=brd-rust", config,
                    f"implementation=completion-{core}")
            with self.assertRaises(ValueError):
                ext4._common.validate_selection(f"core-ext4-{core}", "implementation=brd-rust", config,
                    f"implementation=completion-{core}")

    def test_runtime_rejects_wrong_missing_core_proof_or_brd(self):
        for profile, config, core, wrong in (("server", self.rust, "rust", "c"), ("server-c", self.c, "c", "rust")):
            for proof in (None, "", f"implementation=completion-{wrong}"):
                with self.subTest(profile=profile, proof=proof), self.assertRaises(ValueError):
                    ext4.validate_selection(profile, "implementation=brd-rust", config, proof)
            with self.assertRaises(ValueError):
                ext4.validate_selection(profile, "implementation=brd-c", config,
                    f"implementation=completion-{core}")

    def test_runtime_rejects_target_drift_debugfs_kunit_modules_or_excluded_drivers(self):
        for changed in (
            self.rust.replace("CONFIG_NET=y", "# CONFIG_NET is not set"),
            self.rust.replace("# CONFIG_DEBUG_FS is not set", "CONFIG_DEBUG_FS=y"),
            self.rust.replace("# CONFIG_KUNIT is not set", "CONFIG_KUNIT=y"),
            self.rust.replace("# CONFIG_MODULES is not set", "CONFIG_MODULES=y"),
            self.rust + "CONFIG_MT7601U=y\n",
        ):
            with self.subTest(changed=changed[-40:]), self.assertRaises(ValueError):
                ext4.validate_selection("server", "implementation=brd-rust", changed,
                    "implementation=completion-rust")

    def test_provenance_rejects_tampered_input_template_metadata_and_resolved_config(self):
        for profile, config in (("server", self.rust), ("server-c", self.c)):
            with tempfile.TemporaryDirectory() as temp:
                evidence = Path(temp)
                resolved = evidence / "resolved.config"
                resolved.write_text(config)
                target.materialize(SOURCE, profile, evidence)
                target.verify(SOURCE, profile, evidence, resolved)
                with self.assertRaises(ValueError):
                    target.materialize(SOURCE, profile, evidence)
                for name in ("config-template", "config-input", "config-input.json"):
                    path = evidence / name
                    original = path.read_text()
                    if name.endswith("json"):
                        metadata = json.loads(original)
                        metadata["derivation_script_sha256"] = "0" * 64
                        path.write_text(json.dumps(metadata))
                    else:
                        path.write_text(original + "# changed\n")
                    with self.subTest(profile=profile, file=name), self.assertRaises(ValueError):
                        target.verify(SOURCE, profile, evidence, resolved)
                    path.write_text(original)
                resolved.write_text(config.replace("CONFIG_NR_CPUS=8", "CONFIG_NR_CPUS=2"))
                with self.assertRaises(ValueError):
                    target.verify(SOURCE, profile, evidence, resolved)


if __name__ == "__main__":
    unittest.main()
