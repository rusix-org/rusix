#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Parameter VM marker, selection and boot-variant regression checks."""
import importlib.util
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
scripts = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(scripts))
spec = importlib.util.spec_from_file_location("parameters", scripts / "test-brd-parameters-vm.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class ParameterTests(unittest.TestCase):
    def setUp(self):
        self.lines = ["RUSIX_BRD_PARAMETERS_START"]
        self.lines += [f"RUSIX_BRD_PARAMETERS_PASS {case}" for case in runner.CASES]
        self.lines += ["RUSIX_BRD_PARAMETERS_SUCCESS cases=5"]
        self.config = "\n".join(f"CONFIG_{name}=y" for name in runner.common.REQUIRED_CONFIG)
        self.config += "\nCONFIG_SYSFS=y\nCONFIG_BLK_DEV_RAM_COUNT=1\nCONFIG_BLK_DEV_RAM_SIZE=65536\n"

    def reject(self, lines, status=0):
        with self.assertRaises(ValueError):
            runner.accept_console("\n".join(lines), status)

    def test_complete_pass(self):
        self.assertEqual(runner.accept_console("\r\n".join(self.lines), 0)["cases"], list(runner.CASES))

    def test_each_missing_or_duplicate_marker(self):
        for index in range(len(self.lines)):
            self.reject(self.lines[:index] + self.lines[index + 1:])
            self.reject(self.lines[:index] + [self.lines[index]] + self.lines[index:])

    def test_order_unknown_and_truncation(self):
        self.reject(list(reversed(self.lines)))
        self.reject(self.lines + ["RUSIX_BRD_PARAMETERS_PASS extra"])
        self.reject(self.lines[:-1] + ["RUSIX_BRD_PARAMETERS_SUCCESS cases=4"])
        self.reject(["prefix " + self.lines[0]] + self.lines[1:])

    def test_fail_skip_fault_or_nonzero_exit(self):
        for line in ("RUSIX_BRD_PARAMETERS_FAIL test", "RUSIX_BRD_PARAMETERS_SKIP test",
                     "WARNING: kernel", "BUG: bad", "Oops: bad", "Kernel panic",
                     "CPU feature dependency check failure", "Buffer I/O error"):
            self.reject(self.lines + [line])
        for status in (1, 124, 137, -9):
            self.reject(self.lines, status)

    def test_selection_supports_both_driver_profiles_only(self):
        for profile, rust in (("brd", False), ("brd-rust", True),
                              ("brd-ext4-c", False), ("brd-ext4-rust", True)):
            impl = "brd-rust" if rust else "brd-c"
            config = self.config + ("CONFIG_RUSIX_BRD_RUST=y\n" if rust else "")
            self.assertEqual(runner.validate_selection(profile, f"implementation={impl}", config), impl)
            with self.assertRaises(ValueError):
                runner.validate_selection(profile, "implementation=wrong", config)
        for profile in ("server", "kunit", "brd-kunit"):
            with self.assertRaises(ValueError):
                runner.validate_selection(profile, "implementation=brd-c", self.config)
        with self.assertRaises(ValueError):
            runner.validate_selection("brd", "implementation=brd-c", self.config.replace("CONFIG_SYSFS=y", ""))

    def test_five_boot_inputs_and_expected_normalization(self):
        variants = runner.variants(self.config)
        self.assertEqual([(v["name"], v["rd_nr"], v["rd_size"], v["max_part"]) for v in variants],
                         [("defaults", 1, 65536, 1), ("on_demand", 0, 4096, 1),
                          ("spacing_roundup", 1, 4096, 4), ("spacing_clamp", 1, 4096, 256),
                          ("legacy_octal", 1, 4096, 1)])
        self.assertFalse(variants[0]["options"])
        self.assertIn("brd.max_part=3", variants[2]["options"])
        self.assertIn("brd.max_part=257", variants[3]["options"])
        self.assertIn("ramdisk_size=010000", variants[4]["options"])
        self.assertFalse(any(o.startswith("brd.rd_size=") for o in variants[4]["options"]))
        for variant in variants:
            cmd = runner.command_line(variant).split()
            self.assertIn("rusix.brd_parameters=1", cmd)
            for field in ("rd_nr", "rd_size", "max_part"):
                self.assertEqual(sum(t.startswith(f"rusix.expect_{field}=") for t in cmd), 1)

    def test_bad_default_config_rejected(self):
        for config in ("", self.config + "CONFIG_BLK_DEV_RAM_COUNT=2\n",
                       self.config.replace("COUNT=1", "COUNT=33"),
                       self.config.replace("SIZE=65536", "SIZE=1")):
            with self.assertRaises(ValueError):
                runner.variants(config)


if __name__ == "__main__":
    unittest.main()
