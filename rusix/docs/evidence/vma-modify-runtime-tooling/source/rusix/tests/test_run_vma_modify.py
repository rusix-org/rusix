#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Host runner/parser/provenance negatives only; no compiler, guest or VM runs."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT/'rusix/scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('modify_runtime_tests', SCRIPTS/'run-vma-modify.py')
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
ORDINARY = ('shared_clone_write_and_exit', 'shared_clone_exec_detaches_mm', 'private_fork_cow',
            'dontfork_omits_only_advised_range', 'wipeonfork_clears_child_and_grandchild',
            'private_file_mapping_cow_and_lifetime', 'shared_file_mapping_survives_parent_unmap',
            'mprotect_middle_split_and_restore', 'fixed_mremap_preserves_unlinked_file_mapping')
NATIVE = ('merge.mprotect_unfaulted_left', 'merge.mprotect_unfaulted_right',
          'merge.mprotect_unfaulted_both', 'merge.mprotect_faulted_left_unfaulted_right',
          'merge.mprotect_unfaulted_left_faulted_right')


def console(kind):
    if kind == 'ordinary':
        return '\n'.join([*[f'RUSIX_VMA_LIFECYCLE_CASE {n} PASS' for n in ORDINARY], 'RUSIX_VMA_LIFECYCLE_PASS'])
    return '\n'.join([r.native.BEGIN, *r.native.expected_output(), r.native.END, r.native.PASS])


class RunnerTests(unittest.TestCase):
    def test_exact_nine_and_five(self):
        for kind, names in (('ordinary', ORDINARY), ('native', NATIVE)):
            self.assertEqual(r.accept_console(kind, console(kind), 0)['cases'], list(names))

    def test_timeout_failure_foreign_and_unknown_rejected(self):
        for kind in ('ordinary', 'native'):
            for status in (1, 124, 125, 137, 143, -9):
                with self.subTest(kind=kind, status=status), self.assertRaises(ValueError):
                    r.accept_console(kind, console(kind), status)
            for foreign in ('RUSIX_COPY_VMA_PASS', 'RUSIX_OTHER_PASS', console('native' if kind=='ordinary' else 'ordinary')):
                with self.assertRaises(ValueError):r.accept_console(kind, console(kind)+'\n'+foreign, 0)
        with self.assertRaises(ValueError):r.accept_console('unknown', console('native'), 0)

    def test_missing_duplicate_skip_extra_and_diagnostics_rejected(self):
        native = console('native')
        for text in (native.replace('1..5', '1..4'), native+'\nok 6 extra',
                     native.replace('skip:0', 'skip:1'), native+'\n'+r.native.PASS,
                     native.replace('ok 2 ', 'not ok 2 ')):
            with self.assertRaises(ValueError):r.accept_console('native', text, 0)
        with self.assertRaises(ValueError):r.accept_console('ordinary', console('ordinary').replace(ORDINARY[0], ORDINARY[1]), 0)
        for kind in ('ordinary', 'native'):
            for diagnostic in ('warning: bad', 'BUG: bad', 'Kernel panic', 'ACPI BIOS Error: bad'):
                with self.assertRaises(ValueError):r.accept_console(kind, console(kind)+'\n'+diagnostic, 0)

    def test_exact_guard_and_vm_bounds(self):
        for kind, token in (('ordinary', 'rusix.vma_lifecycle_probe=1'), ('native', 'rusix.vma_modify_probe=1')):
            argv = r.qemu_command(Path('/kernel'), Path('/initramfs'), kind)
            self.assertEqual(argv[:4], ['/usr/bin/timeout', '--kill-after=5s', '180s', '/usr/bin/qemu-system-x86_64'])
            for flag, value in (('-accel','kvm'),('-machine','q35'),('-m','512M'),('-smp','2'),('-nic','none')):
                self.assertEqual(argv[argv.index(flag)+1], value)
            self.assertEqual([word for word in argv[-1].split() if word.startswith('rusix.')], [token])

    def test_config_uses_explicit_new_profile_not_ancestor_alias(self):
        config='\n'.join('CONFIG_'+name+'=y' for name in (*r.ordinary.REQUIRED_CONFIG,'MEMFD_CREATE'))+'\n# CONFIG_KUNIT is not set\n'
        with patch.object(r.selection,'check_config') as check:
            self.assertEqual(r.validate_config('vma-modify-rust',config,''),'rust')
            self.assertEqual(check.call_args.args[0],'vma-modify-rust')
            for profile in ('copy-vma-rust','exit-mmap-rust','vma-lifecycle-rust'):
                with self.assertRaises(ValueError):r.validate_config(profile,config,'')
            for text in (config.replace('CONFIG_MEMFD_CREATE=y','CONFIG_MEMFD_CREATE=n'),config+'CONFIG_KUNIT=y\n'):
                with self.assertRaises(ValueError):r.validate_config('vma-modify-c',text,'')

    def test_seven_actual_baseline_sources_and_exact_native_filters(self):
        record = r.upstream_identity(ROOT)
        self.assertEqual(len(record['files']),7)
        self.assertEqual(record['required_cases'],list(NATIVE))
        self.assertEqual(record['argv'],[arg for case in NATIVE for arg in ('-r',case)])
        self.assertEqual(r.NATIVE_UNITS,('merge','vm_util','thp_settings'))
        self.assertEqual(r.EXPECTED_NATIVE_DEPENDENCIES,187)
        for changed in (record | {'required_cases':list(NATIVE[:-1])},record | {'argv':['-r',NATIVE[0]]}):
            with patch.object(r.json,'loads',return_value=changed),self.assertRaises(ValueError):r.upstream_identity(ROOT)

    def test_dependency_target_source_and_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);unit=root/r.NATIVE_FILES[0];unit.parent.mkdir(parents=True);unit.write_text('source')
            header=root/r.NATIVE_FILES[2];header.write_text('header');target=root/'probe.o'
            text=str(target)+': '+str(unit)+' \\\n '+str(header)+'\n'
            records=r.dependency_records(text,target,unit,root);r.unchanged_dependencies(records)
            for bad in (text.replace(str(target),str(root/'other.o'),1),text.replace(str(unit)+' ',''),text+str(unit)):
                with self.assertRaises(ValueError):r.dependency_records(bad,target,unit,root)
            header.write_text('changed')
            with self.assertRaises(ValueError):r.unchanged_dependencies(records)
            other=root/'unreviewed.h';other.write_text('other')
            with self.assertRaises(ValueError):r.dependency_records(str(target)+': '+str(unit)+' '+str(other),target,unit,root)

    def test_generated_guest_binaries_cannot_be_host_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.object(r.subprocess,'run') as run:
                for program in (str(root/'init'),str(root/'probe'),'/usr/bin/bash','/usr/bin/qemu-system-x86_64'):
                    with self.assertRaises(ValueError):r.record_command('bad',[program],root,root)
                run.assert_not_called()

    def test_failed_compile_preserves_diagnostics_and_removes_execute_bits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);artifact=root/'probe'
            def failed(*args,**kwargs):
                artifact.write_bytes(b'model artifact');artifact.chmod(0o755)
                return SimpleNamespace(returncode=1,stdout='',stderr='compiler failure')
            with patch.object(r.subprocess,'run',side_effect=failed),self.assertRaises(ValueError):
                r.record_command('compile',['/usr/bin/gcc','-o',str(artifact)],root,root)
            self.assertEqual(artifact.stat().st_mode & 0o777,0o644)
            self.assertEqual((root/'compile.exit').read_text(),'1\n')
            self.assertEqual((root/'compile.stderr').read_text(),'compiler failure')

    def test_nested_build_records_must_match_top_level(self):
        copy_mm={'status':'PASS'};dup={'mm_copy_selection':copy_mm};vma={'dup_mmap_selection':dup}
        teardown={'vma_lifecycle_selection':vma};copy={'exit_mmap_selection':teardown};selected={'copy_vma_selection':copy}
        records={'vma-modify-copy-selection.json':copy,'copy-vma-exit-selection.json':teardown,
                 'exit-mmap-vma-selection.json':vma,'vma-lifecycle-dup-selection.json':dup,
                 'dup-mmap-mm-copy-selection.json':copy_mm}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name,value in records.items():(root/name).write_text(json.dumps(value))
            self.assertEqual(len(r.nested_build_proofs(root,selected)),5)
            (root/'dup-mmap-mm-copy-selection.json').write_text('{}')
            with self.assertRaises(ValueError):r.nested_build_proofs(root,selected)

    def test_explicit_dispatch_preserves_arguments_and_default_profile_gate(self):
        with patch.object(r.ordinary,'load',return_value=SimpleNamespace(main=lambda:17)) as load:
            with patch.object(sys,'argv',['test-vma-lifecycle-vm.py','--vma-modify','/build','label','--build-evidence','/proof']):
                self.assertEqual(r.ordinary.main(),17)
                self.assertEqual(sys.argv[1:],['/build','label','--build-evidence','/proof'])
            load.assert_called_once_with('vma_modify_runtime','run-vma-modify.py')
        with self.assertRaises(ValueError):r.ordinary.validate_config('vma-modify-c','','')

    def test_real_local_routes_and_per_boot_actual_proof(self):
        ci=(ROOT/'rusix/ci/run.sh').read_text();start=ci.index('elif [[ "$profile" == vma-modify-c');end=ci.index('elif ',start+6);route=ci[start:end]
        self.assertIn('test-vma-lifecycle-vm.py" --vma-modify',route)
        self.assertIn('--build-evidence "${evidence[0]}"',route)
        self.assertLess(ci.index('scripts/build-kernel.sh'),start)
        wrapper=(ROOT/'rusix/ci/run-container.sh').read_text();self.assertIn('vma-modify-c|vma-modify-rust',wrapper)
        text=(SCRIPTS/'run-vma-modify.py').read_text();start=text.index('def compile_and_boot(');end=text.index('\ndef run(',start);body=text[start:end]
        self.assertLess(body.index('recheck_for_boot('),body.index("record_command('init-compile'"))
        self.assertLess(body.index("ordinary.static_elf(elf)"),body.index('guest = subprocess.run'))
        self.assertIn("selected['source_context'] == 'vma-modify-v1'",text)

if __name__=='__main__':unittest.main()
