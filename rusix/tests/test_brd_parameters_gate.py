#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Parameter VM marker, selection and boot-variant regression checks."""
import importlib.util
from pathlib import Path
import sys
import stat
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
        self.config += "\nCONFIG_SYSFS=y\nCONFIG_BLOCK_LEGACY_AUTOLOAD=y\nCONFIG_BLK_DEV_RAM_COUNT=1\nCONFIG_BLK_DEV_RAM_SIZE=65536\n"

    def test_informational_pci_bug_reporting_hint_is_not_a_fault(self):
        hint = 'PCI: Using host bridge windows from ACPI; if necessary, use "pci=nocrs" and report a bug'
        result = runner.accept_console("\n".join([hint] + self.lines), 0)
        self.assertEqual(result["status"], "PASS")

    def test_acpi_diagnostics_even_after_success(self):
        for diagnostic in ("ACPI Error: AE_NOT_FOUND", "ACPI Warning: invalid table",
                           "ACPI BIOS Error (bug): Could not resolve symbol",
                           "ACPI BIOS Warning: invalid table", "ACPI Exception: AE_ERROR",
                           "ACPI: Unable to load the System Description Tables"):
            with self.subTest(diagnostic=diagnostic):
                self.reject(self.lines + [diagnostic])

    def reject(self, lines, status=0):
        with self.assertRaises(ValueError):
            runner.accept_console("\n".join(lines), status)

    def test_archive_stages_guest_kmsg_device_and_atomic_console_options(self):
        archive = runner.make_initramfs(b"static ELF fixture")
        offset = 0
        entries = {}
        while True:
            self.assertEqual(archive[offset:offset + 6], b"070701")
            fields = [int(archive[offset + 6 + 8 * i:offset + 14 + 8 * i], 16)
                      for i in range(13)]
            start = offset + 110
            name = archive[start:start + fields[11] - 1].decode()
            entries[name] = fields
            data_start = (start + fields[11] + 3) & ~3
            offset = (data_start + fields[6] + 3) & ~3
            if name == "TRAILER!!!":
                break
        self.assertEqual(entries["dev/kmsg"][1], stat.S_IFCHR | 0o600)
        self.assertEqual(entries["dev/kmsg"][9:11], [1, 11])
        self.assertEqual(entries["dev/console"][9:11], [5, 1])
        for variant in runner.variants(self.config):
            tokens = runner.command_line(variant).split()
            self.assertEqual(tokens.count("printk.devkmsg=on"), 1)
            self.assertEqual(tokens.count("printk.time=0"), 1)
            self.assertEqual(tokens.count("loglevel=7"), 1)

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
                     "CPU feature dependency check failure", "ACPI Error: AE_BAD_PARAMETER",
                      "ACPI BIOS Error: missing handler", "Buffer I/O error"):
            self.reject(self.lines + [line])
        for status in (1, 124, 137, -9):
            self.reject(self.lines, status)

    def test_only_pristine_c_profiles_retain_historical_expectations(self):
        for profile in ("brd", "brd-ext4-c"):
            self.assertEqual(runner.validate_selection(profile, "implementation=brd-c", self.config), "brd-c")
            for flag in ("RUSIX_BRD_RUST", "RUSIX_BRD_C_PARAMETER_FIX"):
                with self.assertRaises(ValueError):
                    runner.validate_selection(profile, "implementation=brd-c", self.config + f"CONFIG_{flag}=y\n")
        for profile in ("brd-rust", "brd-ext4-rust", "core-ext4-c", "core-ext4-rust",
                        "brd-fixed-c", "brd-ext4-fixed-c", "server", "kunit", "brd-kunit"):
            with self.assertRaises(ValueError):
                runner.validate_selection(profile, "implementation=brd-c", self.config)

    def test_sysfs_and_legacy_autoload_are_independently_required(self):
        for name in ("SYSFS", "BLOCK_LEGACY_AUTOLOAD"):
            for replacement in ("", f"CONFIG_{name}=m", f"# CONFIG_{name} is not set"):
                with self.subTest(name=name, replacement=replacement):
                    config = self.config.replace(f"CONFIG_{name}=y", replacement)
                    with self.assertRaises(ValueError):
                        runner.validate_selection("brd", "implementation=brd-c", config)

    def test_five_boot_inputs_and_expected_normalization(self):
        variants = runner.variants(self.config)
        self.assertEqual([(v["name"], v["rd_nr"], v["rd_size"], v["max_part"]) for v in variants[:5]],
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

    def test_high_positive_boot_input_and_signed_expectation(self):
        variants = runner.variants(self.config)
        self.assertEqual(len(variants), 6)
        variant = variants[-1]
        self.assertEqual((variant["name"], variant["rd_nr"], variant["max_part"]),
                         ("spacing_high_positive", 0, -2147483648))
        command = runner.command_line(variant).split()
        for token in ("brd.rd_nr=0", "brd.max_part=1073741824",
                      "rusix.expect_max_part=-2147483648", "rusix.parameters_mode=high_positive"):
            self.assertIn(token, command)
        self.assertEqual(sum(t.startswith("rusix.parameters_mode=") for t in command), 1)

    def test_high_positive_inventory_is_separate_and_strict(self):
        lines = ["RUSIX_BRD_PARAMETERS_START"]
        lines += [f"RUSIX_BRD_PARAMETERS_PASS {case}" for case in runner.HIGH_POSITIVE_CASES]
        lines += ["RUSIX_BRD_PARAMETERS_SUCCESS cases=5"]
        result = runner.accept_console("\n".join(lines), 0, "high_positive")
        self.assertEqual(result["cases"], list(runner.HIGH_POSITIVE_CASES))
        for index in range(len(lines)):
            for altered in (lines[:index] + lines[index + 1:],
                            lines[:index] + [lines[index]] + lines[index:]):
                with self.subTest(index=index, altered=altered):
                    with self.assertRaises(ValueError):
                        runner.accept_console("\n".join(altered), 0, "high_positive")
        for console, status, mode in ((self.lines, 0, "high_positive"),
                                      (lines, 0, "normal"), (lines, 0, "unknown"),
                                      (lines, 124, "high_positive"),
                                      (list(reversed(lines)), 0, "high_positive"),
                                      (lines + ["RUSIX_BRD_PARAMETERS_FAIL open"], 0, "high_positive"),
                                      (lines + ["RUSIX_BRD_PARAMETERS_SKIP open"], 0, "high_positive"),
                                      (lines + ["WARNING: kernel"], 0, "high_positive")):
            with self.subTest(status=status, mode=mode):
                with self.assertRaises(ValueError):
                    runner.accept_console("\n".join(console), status, mode)

    def test_bad_default_config_rejected(self):
        for config in ("", self.config + "CONFIG_BLK_DEV_RAM_COUNT=2\n",
                       self.config.replace("COUNT=1", "COUNT=33"),
                       self.config.replace("SIZE=65536", "SIZE=1")):
            with self.assertRaises(ValueError):
                runner.variants(config)


if __name__ == "__main__":
    unittest.main()
