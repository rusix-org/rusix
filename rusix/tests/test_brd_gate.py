#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Regression checks for BRD result acceptance and guest input construction."""
import importlib.util
from pathlib import Path
import stat
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
scripts = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(scripts))
spec = importlib.util.spec_from_file_location("brd_runner", scripts / "test-brd-vm.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class GateTests(unittest.TestCase):
    def setUp(self):
        self.lines = [f"RUSIX_BRD_PASS {case}" for case in runner.CASES]
        self.lines.append("RUSIX_BRD_SUCCESS cases=6")

    def check_rejected(self, lines, exit_code=0):
        with self.assertRaises(ValueError):
            runner.accept_console("\n".join(lines), exit_code)

    def test_exact_inventory_with_kernel_output_passes(self):
        result = runner.accept_console("Linux boot\r\n" + "\r\n".join(self.lines)
                                       + "\r\nreboot: machine restart\r\n", 0)
        self.assertEqual(result["cases"], list(runner.CASES))

    def test_missing_case(self):
        self.check_rejected(self.lines[1:])

    def test_missing_completion(self):
        self.check_rejected(self.lines[:-1])

    def test_duplicate_case(self):
        self.check_rejected([self.lines[0]] + self.lines)

    def test_duplicate_completion(self):
        self.check_rejected(self.lines + [self.lines[-1]])

    def test_unknown_case(self):
        self.check_rejected(self.lines[:-1] + ["RUSIX_BRD_PASS unknown", self.lines[-1]])

    def test_out_of_order(self):
        self.check_rejected(list(reversed(self.lines)))

    def test_wrong_count(self):
        self.check_rejected(self.lines[:-1] + ["RUSIX_BRD_SUCCESS cases=5"])

    def test_fail_or_skip_even_after_success(self):
        for marker in ("RUSIX_BRD_FAIL accounting", "RUSIX_BRD_SKIP geometry"):
            with self.subTest(marker=marker):
                self.check_rejected(self.lines + [marker])

    def test_fault_even_after_success(self):
        for fault in ("WARNING: CPU: 0", "BUG: bad page state", "Oops: 0000",
                      "Kernel panic - not syncing: test",
                      "x86 CPU feature dependency check failure: CPU0"):
            with self.subTest(fault=fault):
                self.check_rejected(self.lines + [fault])

    def test_failure_or_timeout_with_complete_output(self):
        for status in (1, 124, 137, -9):
            with self.subTest(status=status):
                self.check_rejected(self.lines, status)

    def test_prefixed_or_truncated_marker(self):
        self.check_rejected(["interleaved " + self.lines[0]] + self.lines[1:])
        self.check_rejected(self.lines[:-1] + ["RUSIX_BRD_SUCCESS cases="])


class SelectionTests(unittest.TestCase):
    def config(self, rust=False):
        lines = [f"CONFIG_{name}=y" for name in runner.REQUIRED_CONFIG]
        lines += ["CONFIG_RUSIX_BRD_RUST=y" if rust else
                  "# CONFIG_RUSIX_BRD_RUST is not set", "# CONFIG_KUNIT is not set"]
        return "\n".join(lines)

    def test_each_implementation_requires_matching_profile_and_configuration(self):
        for profile, implementation, rust in (("brd", "brd-c", False),
                                               ("brd-rust", "brd-rust", True),
                                               ("brd-ext4-c", "brd-c", False),
                                               ("brd-ext4-rust", "brd-rust", True)):
            with self.subTest(profile=profile):
                self.assertEqual(runner.validate_selection(
                    profile, f"implementation={implementation}", self.config(rust)),
                    implementation)
                with self.assertRaises(ValueError):
                    runner.validate_selection(profile, f"implementation={implementation}",
                                              self.config(not rust))
                other = "brd-c" if rust else "brd-rust"
                with self.assertRaises(ValueError):
                    runner.validate_selection(profile, f"implementation={other}",
                                              self.config(rust))

    def test_invalid_profile_and_selection(self):
        for profile, selection in (("kunit", "implementation=brd-c"),
                                   ("server", "implementation=brd-rust"),
                                   ("brd", ""), ("brd", "implementation=brd-c extra")):
            with self.subTest(profile=profile, selection=selection):
                with self.assertRaises(ValueError):
                    runner.validate_selection(profile, selection, self.config())

    def test_each_required_builtin_option_is_enforced(self):
        for name in runner.REQUIRED_CONFIG:
            for replacement in ("", f"CONFIG_{name}=m"):
                with self.subTest(name=name, replacement=replacement):
                    config = self.config().replace(f"CONFIG_{name}=y", replacement)
                    with self.assertRaises(ValueError):
                        runner.validate_selection("brd", "implementation=brd-c", config)

    def test_kunit_is_not_allowed_in_contract_guest(self):
        with self.assertRaises(ValueError):
            runner.validate_selection("brd-rust", "implementation=brd-rust",
                                      self.config(True) + "\nCONFIG_KUNIT=y")


class InputTests(unittest.TestCase):
    def test_build_evidence_requires_matching_hashes(self):
        with tempfile.TemporaryDirectory(prefix="rusix-brd-hashes-") as directory:
            root = Path(directory)
            image = root / "kernel with spaces"
            config = root / ".config"
            image.write_bytes(b"kernel")
            config.write_bytes(b"config")
            manifest = root / "build.sha256"
            manifest.write_text("".join(f"{runner.digest(p)}  {p}\n" for p in (image, config)))
            runner.check_hashes(manifest, [image, config])
            image.write_bytes(b"different kernel")
            with self.assertRaises(ValueError):
                runner.check_hashes(manifest, [image, config])

    def test_build_evidence_missing_duplicate_or_relative_record(self):
        with tempfile.TemporaryDirectory(prefix="rusix-brd-hashes-") as directory:
            root = Path(directory)
            image = root / "kernel"
            image.write_bytes(b"kernel")
            manifest = root / "build.sha256"
            record = f"{runner.digest(image)}  {image}\n"
            for content in ("", record + record, f"{runner.digest(image)}  kernel\n",
                            "not a hash record\n"):
                with self.subTest(content=content):
                    manifest.write_text(content)
                    with self.assertRaises(ValueError):
                        runner.check_hashes(manifest, [image])

    def test_newc_contains_static_init_and_only_guest_device_nodes(self):
        payload = b"ELF fixture\0with data"
        archive = runner.make_initramfs(payload)
        self.assertEqual(archive, runner.make_initramfs(payload))
        entries = {}
        offset = 0
        while True:
            self.assertEqual(archive[offset:offset + 6], b"070701")
            fields = [int(archive[offset + 6 + 8 * i:offset + 14 + 8 * i], 16)
                      for i in range(13)]
            name_start = offset + 110
            name = archive[name_start:name_start + fields[11] - 1].decode()
            data_start = (name_start + fields[11] + 3) & ~3
            data = archive[data_start:data_start + fields[6]]
            entries[name] = (fields, data)
            offset = (data_start + fields[6] + 3) & ~3
            if name == "TRAILER!!!":
                break
        self.assertEqual(set(entries), {"dev", "proc", "debug", "dev/console",
                                        "dev/ram0", "init", "TRAILER!!!"})
        self.assertEqual(entries["init"][1], payload)
        self.assertEqual(entries["init"][0][1], stat.S_IFREG | 0o755)
        self.assertEqual(entries["dev/console"][0][1], stat.S_IFCHR | 0o600)
        self.assertEqual(entries["dev/console"][0][9:11], [5, 1])
        self.assertEqual(entries["dev/ram0"][0][1], stat.S_IFBLK | 0o600)
        self.assertEqual(entries["dev/ram0"][0][9:11], [1, 0])
        for fields, _ in entries.values():
            self.assertEqual(fields[2:4], [0, 0])
            self.assertEqual(fields[5], 0)
        self.assertEqual(len(archive) % 512, 0)


if __name__ == "__main__":
    unittest.main()
