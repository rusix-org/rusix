#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Partition VM marker, selection and boot-input regression checks."""
import importlib.util
from pathlib import Path
import sys
import stat
import unittest

sys.dont_write_bytecode = True
scripts = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(scripts))
spec = importlib.util.spec_from_file_location("parameters", scripts / "test-brd-partitions-vm.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class PartitionTests(unittest.TestCase):
    def test_core_profiles_require_completion_config_and_symbol_proof(self):
        for suffix in ("c", "rust"):
            profile = f"core-ext4-{suffix}"
            setting = ("CONFIG_RUSIX_COMPLETION_RUST=y" if suffix == "rust" else
                       "# CONFIG_RUSIX_COMPLETION_RUST is not set")
            config = (self.config + "CONFIG_RUSIX_BRD_RUST=y\n") + "\n# CONFIG_MODULES is not set\n" + setting
            proof = f"implementation=completion-{suffix}"
            self.assertEqual(runner.validate_selection(profile, "implementation=brd-rust",
                                                       config, proof), "brd-rust")
            for wrong in (None, "", "implementation=completion-" + ("c" if suffix == "rust" else "rust")):
                with self.subTest(profile=profile, proof=wrong):
                    with self.assertRaises(ValueError):
                        runner.validate_selection(profile, "implementation=brd-rust", config, wrong)
            for wrong_config in (config.replace(setting, ""), config + "\nCONFIG_MODULES=y",
                                 config.replace("# CONFIG_MODULES is not set", ""),
                                 config + "\n" + setting):
                with self.assertRaises(ValueError):
                    runner.validate_selection(profile, "implementation=brd-rust", wrong_config, proof)
            with self.assertRaises(ValueError):
                runner.validate_selection(profile, "implementation=brd-c", config, proof)

    def setUp(self):
        self.lines = ["RUSIX_BRD_PARTITIONS_START"]
        self.lines += [f"RUSIX_BRD_PARTITIONS_PASS {case}" for case in runner.CASES]
        self.lines += ["RUSIX_BRD_PARTITIONS_SUCCESS cases=5"]
        self.config = "\n".join(f"CONFIG_{name}=y" for name in runner.common.REQUIRED_CONFIG)
        self.config += "\nCONFIG_SYSFS=y\nCONFIG_MSDOS_PARTITION=y\nCONFIG_BLK_DEV_RAM_COUNT=1\nCONFIG_BLK_DEV_RAM_SIZE=65536\n"

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
        self.reject(self.lines + ["RUSIX_BRD_PARTITIONS_PASS extra"])
        self.reject(self.lines[:-1] + ["RUSIX_BRD_PARTITIONS_SUCCESS cases=4"])
        self.reject(["prefix " + self.lines[0]] + self.lines[1:])

    def test_fail_skip_fault_or_nonzero_exit(self):
        for line in ("RUSIX_BRD_PARTITIONS_FAIL test", "RUSIX_BRD_PARTITIONS_SKIP test",
                     "WARNING: kernel", "BUG: bad", "Oops: bad", "Kernel panic",
                     "CPU feature dependency check failure", "ACPI Error: AE_BAD_PARAMETER",
                      "ACPI BIOS Error: missing handler", "Buffer I/O error"):
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

    def test_sysfs_and_msdos_parser_are_independently_required(self):
        for name in ("SYSFS", "MSDOS_PARTITION"):
            for replacement in ("", f"CONFIG_{name}=m", f"# CONFIG_{name} is not set"):
                with self.subTest(name=name, replacement=replacement):
                    config = self.config.replace(f"CONFIG_{name}=y", replacement)
                    with self.assertRaises(ValueError):
                        runner.validate_selection("brd", "implementation=brd-c", config)

    def test_single_bounded_primary_partition_boot(self):
        variants = runner.variants(self.config)
        self.assertEqual(variants, [{"name": "primary_partition", "rd_nr": 2,
                                     "rd_size": 4096, "max_part": 4}])
        tokens = runner.command_line(variants[0]).split()
        for token in ("rusix.brd_partitions=1", "brd.rd_nr=2", "brd.rd_size=4096",
                      "brd.max_part=4", "kunit.enable=0"):
            self.assertEqual(tokens.count(token), 1)


if __name__ == "__main__":
    unittest.main()
