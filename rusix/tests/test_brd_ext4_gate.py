#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Host-only gate/staging tests. Never execute any guest utility or disk operation."""
import importlib.util
from pathlib import Path
import stat
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
scripts = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(scripts))
spec = importlib.util.spec_from_file_location("ext4_runner", scripts / "test-brd-ext4-vm.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class GateTests(unittest.TestCase):
    def setUp(self):
        self.lines = ["RUSIX_EXT4_START"] + [f"RUSIX_EXT4_PASS {case}" for case in runner.CASES]
        self.lines += ["RUSIX_EXT4_SUCCESS cases=6"]

    def rejected(self, lines, status=0):
        with self.assertRaises(ValueError):
            runner.accept_console("\n".join(lines), status)

    def test_exact_inventory(self):
        result = runner.accept_console("Linux boot\r\n" + "\r\n".join(self.lines) + "\r\nreboot\r\n", 0)
        self.assertEqual(result["cases"], list(runner.CASES))

    def test_every_missing_or_duplicate_marker(self):
        for index in range(len(self.lines)):
            with self.subTest(index=index):
                self.rejected(self.lines[:index] + self.lines[index + 1:])
                self.rejected(self.lines[:index] + [self.lines[index]] + self.lines[index:])

    def test_reordered_or_prefixed_markers(self):
        self.rejected(list(reversed(self.lines)))
        self.rejected(["interleaved " + self.lines[0]] + self.lines[1:])
        self.rejected(self.lines[:-1] + ["RUSIX_EXT4_SUCCESS cases=5"])

    def test_fail_skip_unknown_and_kernel_fault_after_success(self):
        for extra in ("RUSIX_EXT4_FAIL reboot", "RUSIX_EXT4_SKIP fsck", "RUSIX_EXT4_PASS unknown",
                      "WARNING: CPU: 0", "BUG: page", "Oops: bad", "Kernel panic",
                      "CPU feature dependency check failure", "EXT4-fs warning (device ram0)",
                      "EXT4-fs error (device ram0)", "Buffer I/O error on dev ram0"):
            with self.subTest(extra=extra):
                self.rejected(self.lines + [extra])

    def test_timeout_nonzero_or_signal_even_with_all_markers(self):
        for status in (1, 124, 137, -9):
            self.rejected(self.lines, status)


class SelectionTests(unittest.TestCase):
    def config(self, rust=False):
        lines = [f"CONFIG_{name}=y" for name in runner.REQUIRED_CONFIG]
        if rust:
            lines += ["CONFIG_RUSIX_BRD_RUST=y"]
        return "\n".join(lines)

    def test_c_and_rust_provenance(self):
        for suffix, implementation, rust in (("c", "brd-c", False), ("rust", "brd-rust", True)):
            self.assertEqual(runner.validate_selection(f"brd-ext4-{suffix}",
                             f"implementation={implementation}", self.config(rust)), implementation)
            with self.assertRaises(ValueError):
                runner.validate_selection(f"brd-ext4-{suffix}", f"implementation={implementation}", self.config(not rust))

    def test_ext4_and_every_required_builtin_are_enforced(self):
        for setting in runner.REQUIRED_CONFIG:
            for replacement in ("", f"CONFIG_{setting}=m"):
                with self.subTest(setting=setting, replacement=replacement):
                    with self.assertRaises(ValueError):
                        runner.validate_selection("brd-ext4-c", "implementation=brd-c",
                            self.config().replace(f"CONFIG_{setting}=y", replacement))

    def test_kunit_wrong_profile_and_selection_rejected(self):
        for profile, proof, config in (("brd", "implementation=brd-c", self.config()),
                                      ("brd-ext4-c", "implementation=brd-rust", self.config()),
                                      ("brd-ext4-c", "implementation=brd-c", self.config() + "\nCONFIG_KUNIT=y")):
            with self.assertRaises(ValueError):
                runner.validate_selection(profile, proof, config)


class DependencyTests(unittest.TestCase):
    def test_inventory_binds_installed_image_and_tracked_versions(self):
        runner.validate_inventory("pkg\t1\tamd64\n", "pkg\t1\tamd64\n", "pkg\t1\tamd64\n")
        for values in (("new", "new", "old"), ("new", "old", "new"),
                       ("old", "new", "new"), ("", "", "")):
            with self.assertRaises(ValueError):
                runner.validate_inventory(*values)

    def test_elf_interpreter_and_dependencies(self):
        elf = "Machine: Advanced Micro Devices X86-64\n[Requesting program interpreter: /lib64/ld-linux-x86-64.so.2]\n 0x01 (NEEDED) Shared library: [libc.so.6]\n"
        self.assertEqual(runner.parse_elf(elf), ("/lib64/ld-linux-x86-64.so.2", ["libc.so.6"]))
        with self.assertRaises(ValueError):
            runner.parse_elf("Machine: AArch64")

    def test_ldd_closure(self):
        output = " linux-vdso.so.1 (0x1000)\n libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0x2000)\n /lib64/ld-linux-x86-64.so.2 (0x3000)\n"
        self.assertEqual(runner.parse_ldd(output, ["libc.so.6"]), [Path("/lib/x86_64-linux-gnu/libc.so.6")])

    def test_loader_as_needed_direct_path(self):
        self.assertEqual(runner.parse_ldd(" /lib64/ld-linux-x86-64.so.2 (0x3000)\n",
                         ["ld-linux-x86-64.so.2"]), [Path("/lib64/ld-linux-x86-64.so.2")])

    def test_missing_relative_or_ambiguous_dependency_rejected(self):
        for output in (" libc.so.6 => not found\n", " libc.so.6 => ./libc.so.6 (0x10)\n",
                       "", " libc.so.6 => /lib/a (0x1)\n libc.so.6 => /lib/b (0x2)\n"):
            with self.subTest(output=output):
                with self.assertRaises(ValueError):
                    runner.parse_ldd(output, ["libc.so.6"])

    def test_guest_paths_reject_relative_or_traversal(self):
        for path in ("relative", "/../etc/passwd", "/usr/../init", "/"):
            with self.assertRaises(ValueError):
                runner.guest_path(path)

    def test_untrusted_installed_source_rejected(self):
        with tempfile.TemporaryDirectory(prefix="rusix-ext4-trust-") as directory:
            path = Path(directory) / "fake-lib.so"
            path.write_bytes(b"not ELF")
            with self.assertRaises(ValueError):
                runner.trusted_path(path)

    def test_archive_determinism_nodes_and_source_mutation(self):
        with tempfile.TemporaryDirectory(prefix="rusix-ext4-cpio-") as directory:
            file = Path(directory) / "init"
            file.write_bytes(b"guest ELF fixture")
            rootfs = runner.Rootfs()
            rootfs.add("/init", file)
            rootfs.add("/lib64/loader.so", file)
            rootfs.verify_sources()
            archive = rootfs.archive()
            self.assertEqual(archive, rootfs.archive())
            entries, offset = {}, 0
            while True:
                self.assertEqual(archive[offset:offset + 6], b"070701")
                fields = [int(archive[offset + 6 + 8*i:offset + 14 + 8*i], 16) for i in range(13)]
                start = offset + 110
                name = archive[start:start + fields[11] - 1].decode()
                data_start = (start + fields[11] + 3) & ~3
                entries[name] = fields
                offset = (data_start + fields[6] + 3) & ~3
                if name == "TRAILER!!!":
                    break
            self.assertEqual(entries["dev/ram0"][1], stat.S_IFBLK | 0o600)
            self.assertEqual(entries["dev/ram0"][9:11], [1, 0])
            self.assertEqual(entries["dev/console"][9:11], [5, 1])
            self.assertEqual(entries["tmp"][1], stat.S_IFDIR | 0o1777)
            self.assertIn("lib64", entries)
            file.write_bytes(b"changed")
            with self.assertRaises(ValueError):
                rootfs.verify_sources()

    def test_rootfs_file_directory_collision(self):
        with tempfile.TemporaryDirectory(prefix="rusix-ext4-collision-") as directory:
            file = Path(directory) / "input"
            file.write_bytes(b"x")
            rootfs = runner.Rootfs()
            rootfs.add("/usr", file)
            rootfs.add("/usr/bin/tool", file)
            with self.assertRaises(ValueError):
                rootfs.archive()


if __name__ == "__main__":
    unittest.main()
