#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Approved normalization has a separate exact inventory and literal boot matrix."""
import importlib.util
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
scripts = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(scripts))
spec = importlib.util.spec_from_file_location("fixed_parameters", scripts / "test-brd-fixed-parameters-vm.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class FixedParametersTests(unittest.TestCase):
    def setUp(self):
        self.cases = ["parameters", "major_registered", "initial_devices",
                      "on_demand_mapping", "independent_io", "capacity"]
        self.lines = ["RUSIX_BRD_FIXED_PARAMETERS_START"]
        self.lines += [f"RUSIX_BRD_FIXED_PARAMETERS_PASS {case}" for case in self.cases]
        self.lines += ["RUSIX_BRD_FIXED_PARAMETERS_SUCCESS cases=6"]
        self.config = "\n".join(f"CONFIG_{name}=y" for name in runner.common.REQUIRED_CONFIG)
        self.config += "\nCONFIG_SYSFS=y\nCONFIG_BLOCK_LEGACY_AUTOLOAD=y\nCONFIG_BLK_DEV_RAM_COUNT=1\nCONFIG_BLK_DEV_RAM_SIZE=65536\n"

    def reject(self, lines, status=0):
        with self.assertRaises(ValueError):
            runner.accept_console("\n".join(lines), status)

    def test_exact_inventory(self):
        self.assertEqual(runner.accept_console("\r\n".join(self.lines), 0)["cases"], self.cases)
        for i in range(len(self.lines)):
            self.reject(self.lines[:i] + self.lines[i + 1:])
            self.reject(self.lines[:i] + [self.lines[i]] + self.lines[i:])
        for extra in ("PASS unknown", "FAIL io", "SKIP io", "SUCCESS cases=5"):
            self.reject(self.lines + ["RUSIX_BRD_FIXED_PARAMETERS_" + extra])
        self.reject(self.lines + ["RUSIX_BRD_PARAMETERS_SUCCESS cases=5"])
        self.reject(list(reversed(self.lines)))
        self.reject([line.replace("FIXED_", "") for line in self.lines])
        self.reject(["prefix " + self.lines[0]] + self.lines[1:])
        with self.assertRaises(ValueError):
            runner.accept_console("\n".join(self.lines), 0, "high_positive")

    def test_diagnostics_and_exit_fail_after_success(self):
        for diagnostic in ("WARNING: lockdep", "BUG: bad", "Oops: bad", "Kernel panic",
                           "ACPI BIOS Error: bad", "ACPI Warning: bad", "Buffer I/O error",
                           "I/O error, dev ram0", "CPU feature dependency check failure"):
            self.reject(self.lines + [diagnostic])
        for status in (1, 124, 137, -9):
            self.reject(self.lines, status)

    def test_literal_boundary_cross_product(self):
        requested = [-2147483648, -1, 0, 1, 2, 3, 128, 129, 256, 257, 1073741824, 2147483647]
        effective = [1, 1, 1, 1, 2, 4, 128, 256, 256, 256, 256, 256]
        variants = runner.variants(self.config)
        self.assertEqual(len(variants), 26)
        self.assertEqual(len({v["name"] for v in variants}), 26)
        for count, rows in ((0, variants[:12]), (2, variants[12:24])):
            self.assertEqual([v["requested_max_part"] for v in rows], requested)
            self.assertEqual([v["max_part"] for v in rows], effective)
            for v in rows:
                self.assertEqual((v["rd_nr"], v["rd_size"]), (count, 4096))
                tokens = runner.command_line(v).split()
                for exact in ("rusix.brd_fixed_parameters=1", f"brd.rd_nr={count}",
                              "brd.rd_size=4096", f"brd.max_part={v['requested_max_part']}",
                              f"rusix.expect_max_part={v['max_part']}"):
                    self.assertEqual(tokens.count(exact), 1)
                for prefix in ("brd.max_part=", "brd.rd_nr=", "brd.rd_size=", "rusix.expect_max_part="):
                    self.assertEqual(sum(t.startswith(prefix) for t in tokens), 1)

    def test_unchanged_default_and_legacy_boot_inputs(self):
        defaults, legacy = runner.variants(self.config)[24:]
        self.assertEqual(defaults, {"name": "defaults", "rd_nr": 1, "rd_size": 65536,
                                    "max_part": 1, "options": []})
        self.assertEqual((legacy["name"], legacy["rd_nr"], legacy["rd_size"], legacy["max_part"]),
                         ("legacy_octal", 1, 4096, 1))
        tokens = runner.command_line(legacy).split()
        self.assertEqual(tokens.count("ramdisk_size=010000"), 1)
        self.assertFalse(any(t.startswith("brd.rd_size=") for t in tokens))
        self.assertFalse(any(t.startswith("brd.") for t in runner.command_line(defaults).split()))
        maximum = runner.variants(self.config.replace("COUNT=1", "COUNT=32"))[24]
        self.assertEqual(maximum["rd_nr"], 32)
        for config in ("", self.config + "CONFIG_BLK_DEV_RAM_COUNT=2\n",
                       self.config.replace("COUNT=1", "COUNT=33"),
                       self.config.replace("SIZE=65536", "SIZE=1")):
            with self.assertRaises(ValueError):
                runner.variants(config)

    def test_fixed_and_rust_selection_are_exclusive(self):
        for profile, impl, flag in (("brd-fixed-c", "brd-c-parameter-fix", "RUSIX_BRD_C_PARAMETER_FIX"),
                                   ("brd-ext4-fixed-c", "brd-c-parameter-fix", "RUSIX_BRD_C_PARAMETER_FIX"),
                                   ("brd-rust", "brd-rust", "RUSIX_BRD_RUST"),
                                   ("brd-ext4-rust", "brd-rust", "RUSIX_BRD_RUST")):
            config = self.config + f"CONFIG_{flag}=y\n"
            proof = f"implementation={impl}"
            self.assertEqual(runner.validate_selection(profile, proof, config), impl)
            other = "RUSIX_BRD_RUST" if flag.endswith("FIX") else "RUSIX_BRD_C_PARAMETER_FIX"
            for bad in (self.config, config + f"CONFIG_{other}=y\n", config + f"CONFIG_{flag}=y\n",
                        config.replace(f"CONFIG_{flag}=y", f"CONFIG_{flag}=m")):
                with self.assertRaises(ValueError):
                    runner.validate_selection(profile, proof, bad)
            with self.assertRaises(ValueError):
                runner.validate_selection(profile, "implementation=brd-c", config)
        for profile in ("brd", "brd-ext4-c", "server", "server-c", "kunit"):
            with self.assertRaises(ValueError):
                runner.validate_selection(profile, "implementation=brd-c", self.config)

    def test_core_profiles_still_require_core_selection(self):
        for suffix in ("c", "rust"):
            setting = ("CONFIG_RUSIX_COMPLETION_RUST=y" if suffix == "rust" else
                       "# CONFIG_RUSIX_COMPLETION_RUST is not set")
            config = self.config + "CONFIG_RUSIX_BRD_RUST=y\n# CONFIG_MODULES is not set\n" + setting
            profile = f"core-ext4-{suffix}"
            proof = f"implementation=completion-{suffix}"
            self.assertEqual(runner.validate_selection(profile, "implementation=brd-rust", config, proof), "brd-rust")
            with self.assertRaises(ValueError):
                runner.validate_selection(profile, "implementation=brd-rust", config)

    def test_required_guest_interfaces(self):
        for flag in ("SYSFS", "BLOCK_LEGACY_AUTOLOAD"):
            with self.assertRaises(ValueError):
                runner.validate_selection("brd-rust", "implementation=brd-rust",
                                          (self.config + "CONFIG_RUSIX_BRD_RUST=y").replace(f"CONFIG_{flag}=y", ""))


if __name__ == "__main__":
    unittest.main()
