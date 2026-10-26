#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Check retained-byte accounting, provenance classification, and fail-closed maps."""
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
scripts = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(scripts))
spec = importlib.util.spec_from_file_location("kernel_languages", scripts / "measure-kernel-languages.py")
measure = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = measure
spec.loader.exec_module(measure)

HEADER = "VMA LMA Size Align Out In Symbol\n"


class LanguageTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="rusix-language-tests-")
        self.addCleanup(self.scratch.cleanup)
        root = Path(self.scratch.name)
        self.source = root / "source"
        self.build = root / "output"
        self.source.mkdir()
        self.build.mkdir()

    def unit(self, name, source, compiler):
        obj = self.build / name
        obj.parent.mkdir(parents=True, exist_ok=True)
        obj.write_bytes(b"object fixture")
        cmd = obj.parent / f".{obj.name}.cmd"
        cmd.write_text(f"savedcmd_{name} := {compiler} -c {source}\n\n"
                       f"source_{name} := {source}\n")
        return obj

    def test_language_uses_compile_provenance_not_object_name(self):
        self.unit("looks_rust.o", self.source / "actual.c", "clang")
        self.unit("looks_c.o", self.source / "actual.rs", "OBJTREE=/fixture rustc")
        self.unit("boot.o", self.source / "boot.S", "clang")
        for label, expected in (("looks_rust.o", "c"), ("looks_c.o", "rust"),
                                ("boot.o", "assembly")):
            with self.subTest(label=label):
                actual, detail = measure.classify(f"vmlinux.a({label})", self.build, self.source)
                self.assertEqual(actual, expected)
                self.assertIn("command_sha256", detail)

    def test_generated_unknown_and_wrong_compiler_are_separate(self):
        (self.build / ".tmp_vmlinux2.kallsyms.o").write_bytes(b"generated")
        (self.build / ".vmlinux.export.o").write_bytes(b"generated")
        self.unit("generated.o", self.build / "generated.c", "clang")
        self.unit("mismatch.o", self.source / "module.rs", "clang")
        for label, expected in (("<internal>", "generated"),
                                (".tmp_vmlinux2.kallsyms.o", "generated"),
                                (".vmlinux.export.o", "generated"),
                                ("generated.o", "generated"), ("mismatch.o", "unknown"),
                                ("missing.o", "unknown")):
            with self.subTest(label=label):
                self.assertEqual(measure.classify(label, self.build, self.source)[0], expected)

    def test_external_rust_core_and_pi_object_copy_keep_compiled_language(self):
        self.unit("core.o", self.source.parent / "toolchain/core/lib.rs", "rustc")
        language, detail = measure.classify("core.o", self.build, self.source)
        self.assertEqual(language, "rust")
        self.assertEqual(detail["source_origin"], "external")
        self.unit("gdt.o", self.source / "gdt.c", "clang")
        obj = self.build / "gdt.pi.o"
        obj.write_bytes(b"symbol-prefixed fixture")
        cmd = self.build / ".gdt.pi.o.cmd"
        cmd.write_text("savedcmd_gdt.pi.o := llvm-objcopy --prefix-symbols=__pi_ gdt.o gdt.pi.o\n")
        language, detail = measure.classify("gdt.pi.o", self.build, self.source)
        self.assertEqual(language, "c")
        self.assertEqual(detail["original"]["object"], "gdt.o")
        cmd.write_text("savedcmd_gdt.pi.o := llvm-objcopy --prefix-symbols=__pi_ gdt.pi.o gdt.pi.o\n")
        self.assertEqual(measure.classify("gdt.pi.o", self.build, self.source)[0], "unknown")

    def test_cmd_is_data_never_shell_execution(self):
        sentinel = self.build / "must-not-exist"
        self.unit("safe.o", self.source / "safe.c", f"clang $(touch {sentinel})")
        self.assertEqual(measure.classify("safe.o", self.build, self.source)[0], "c")
        self.assertFalse(sentinel.exists())

    def test_relocated_compound_or_external_object_is_not_guessed(self):
        self.unit("partial.o", self.source / "partial.c", "ld.lld")
        self.assertEqual(measure.classify("partial.o", self.build, self.source)[0], "unknown")
        self.assertEqual(measure.classify("/outside.o", self.build, self.source)[0], "unknown")

    def test_retained_bytes_exclude_debug_and_split_bss_padding(self):
        self.unit("c.o", self.source / "c.c", "clang")
        self.unit("r.o", self.source / "r.rs", "rustc")
        sections = {
            ".text": measure.Section(".text", 0x1000, 32, 6, 1, "text-hash"),
            ".bss": measure.Section(".bss", 0x2000, 48, 3, 8, None),
            ".debug_info": measure.Section(".debug_info", 0, 4096, 0, 1, "debug-hash"),
        }
        link_map = HEADER + """1000 1000 20 16 .text
1000 1000 10 16         vmlinux.a(c.o):(.text)
1010 1010 8 1          vmlinux.a(r.o):(.text)
1018 1018 0 1         _end_symbol
2000 2000 30 16 .bss
2000 2000 20 16        vmlinux.a(c.o):(.bss)
2020 2020 10 16        vmlinux.a(r.o):(.bss)
0 0 1000 1 .debug_info
0 0 1000 1             vmlinux.a(c.o):(.debug_info)
"""
        intervals = measure.parse_map(link_map, sections)
        totals, rows, objects = measure.measure(sections, intervals, self.build, self.source)
        self.assertEqual(totals["executable"]["bytes"]["c"], 16)
        self.assertEqual(totals["executable"]["bytes"]["rust"], 8)
        self.assertEqual(totals["executable"]["bytes"]["padding_or_linker_script"], 8)
        self.assertEqual(totals["executable"]["percent"]["rust"], 25)
        self.assertEqual(totals["zero_fill"]["total_bytes"], 48)
        self.assertEqual(totals["file_backed_allocated"]["total_bytes"], 32)
        self.assertEqual(totals["allocated_memory"]["total_bytes"], 80)
        self.assertEqual(objects["vmlinux.a(c.o)"]["retained_bytes"], 48)
        self.assertEqual(len(rows), 2)

    def test_map_rejects_mismatch_missing_overlap_and_no_inputs(self):
        sections = {".text": measure.Section(".text", 0x1000, 32, 6, 1, "hash")}
        cases = (
            "1000 1000 21 16 .text\n",  # wrong output size
            "1000 1000 20 16 .other\n",  # missing allocated section
            "1000 1000 20 16 .text\n1000 1000 18 1 c.o:(.text)\n1010 1010 10 1 r.o:(.text)\n",
            "1000 1000 20 16 .text\n1010 1010 20 1 c.o:(.text)\n",  # outside section
            "1000 1000 20 16 .text\n",  # no input attribution at all
        )
        for text in cases:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    measure.parse_map(HEADER + text, sections)
        with self.assertRaises(ValueError):
            measure.parse_map("GNU map, unsupported format", sections)

    def test_postlink_removed_or_nonallocated_sections_do_not_pollute_counts(self):
        sections = {".text": measure.Section(".text", 0x1000, 16, 6, 1, "hash"),
                    ".symtab": measure.Section(".symtab", 0, 24, 0, 2, "symbols")}
        text = HEADER + """1000 1000 10 1 .text
1000 1000 10 1         c.o:(.text)
0 0 40 1 .modinfo
0 0 40 1              c.o:(.modinfo)
0 0 100 1 .symtab
0 0 100 1             <internal>:(.symtab)
"""
        intervals = measure.parse_map(text, sections)
        self.assertEqual(dict(intervals), {".text": [(0x1000, 0x1010, "c.o", ".text")]})

    def test_build_identity_binds_source_config_images_and_link_map(self):
        evidence = self.build / "evidence"
        evidence.mkdir()
        image = self.build / "arch/x86/boot/bzImage"
        image.parent.mkdir(parents=True)
        image.write_bytes(b"compressed image")
        config = self.build / ".config"
        config.write_bytes(b"CONFIG_64BIT=y\n")
        original = self.build / "vmlinux"
        original.write_bytes(b"final ELF fixture")
        measured = self.build / "relinked"
        measured.write_bytes(original.read_bytes())
        original_map = self.build / "vmlinux.map"
        original_map.write_bytes(b"map with C attribution")
        measured_map = self.build / "copied.map"
        measured_map.write_bytes(original_map.read_bytes())
        revision = "a" * 40
        (evidence / "build.exit").write_text("0\n")
        (evidence / "environment.log").write_text(revision + "\ncompiler version\n")
        (evidence / "source-after.commit").write_text(revision + "\n")
        (evidence / "source-after.status").write_text("")
        (evidence / "config").write_bytes(config.read_bytes())
        (evidence / "build.sha256").write_text("".join(
            f"{measure.sha256(path)}  {path}\n" for path in (config, image, original, original_map)))
        result = measure.build_identity(self.build, evidence, measured, measured_map)
        self.assertEqual(result["source_revision"], revision)
        manifest = evidence / "build.sha256"
        complete = manifest.read_text()
        for required in ("/vmlinux", "/vmlinux.map"):
            with self.subTest(missing_record=required):
                manifest.write_text("".join(line + "\n" for line in complete.splitlines()
                                            if not line.endswith(required)))
                with self.assertRaises(ValueError):
                    measure.build_identity(self.build, evidence, measured, measured_map)
                manifest.write_text(complete)
        for target, replacement in ((measured, b"different ELF"),
                                    (measured_map, b"same layout with Rust attribution"),
                                    (original_map, b"stale map with different attribution"),
                                    (image, b"different bzImage"),
                                    (config, b"CONFIG_64BIT=n\n"),
                                    (evidence / "source-after.status", b" M source.c\n"),
                                    (evidence / "source-after.commit", b"b" * 40),
                                    (evidence / "build.exit", b"1\n")):
            with self.subTest(target=target):
                previous = target.read_bytes()
                target.write_bytes(replacement)
                with self.assertRaises(ValueError):
                    measure.build_identity(self.build, evidence, measured, measured_map)
                target.write_bytes(previous)

    def test_elf_reader_distinguishes_file_bytes_and_zero_fill(self):
        names = b"\0.text\0.bss\0.shstrtab\0"
        header = struct.pack("<16sHHIQQQIHHHHHH", b"\x7fELF\x02\x01" + b"\0" * 10,
                             2, 62, 1, 0x1000, 0, 96, 0, 64, 0, 0, 64, 4, 3)
        payload = b"TEXT" + names
        prefix = header + payload + b"\0" * (96 - 64 - len(payload))
        table = b"\0" * 64
        table += struct.pack("<IIQQQQIIQQ", 1, 1, 6, 0x1000, 64, 4, 0, 0, 1, 0)
        table += struct.pack("<IIQQQQIIQQ", 7, 8, 3, 0x2000, 4096, 8192, 0, 0, 1, 0)
        table += struct.pack("<IIQQQQIIQQ", 12, 3, 0, 0, 68, len(names), 0, 0, 1, 0)
        path = self.build / "vmlinux"
        path.write_bytes(prefix + table)
        sections = measure.elf_sections(path)
        self.assertEqual(sections[".text"].size, 4)
        self.assertEqual(sections[".bss"].size, 8192)
        self.assertIsNone(sections[".bss"].content_sha256)
        path.write_bytes((prefix + table)[:-1])
        with self.assertRaises(ValueError):
            measure.elf_sections(path)


if __name__ == "__main__":
    unittest.main()
