#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Source/config routing regressions; no Kconfig resolution or VM execution."""
import ast
import copy
import importlib.util
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'rusix/scripts'))
def load(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/'rusix/scripts'/file)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
G=load('exit_routing_gate','verify-exit-mmap.py')
VM=load('exit_ordinary_vm','test-exit-mmap-vm.py')
TARGET=G.config_values((ROOT/'rusix/configs/x86_64-server.config').read_text())
def config(profile):
    # Canonical derived architecture symbols normally supplied by Kconfig.
    return G.config_values((ROOT/f'rusix/configs/x86_64-{profile}.config').read_text()) | {
        'CONFIG_X86_64':'y','CONFIG_THREAD_INFO_IN_TASK':'y','CONFIG_MMU':'y','CONFIG_PER_VMA_LOCK':'y'}

class Routing(unittest.TestCase):
    def test_exact_new_pair_and_ordinary_delta(self):
        pair=[config('exit-mmap-kunit-'+s) for s in ('c','rust')]
        self.assertEqual(G.compare(*pair),[G.SELECTOR])
        expected={'CONFIG_KUNIT','CONFIG_RUNTIME_TESTING_MENU','CONFIG_KUNIT_DEFAULT_ENABLED',
                  'CONFIG_KUNIT_AUTORUN_ENABLED','CONFIG_KUNIT_DEFAULT_TIMEOUT','CONFIG_RUSIX_EXIT_MMAP_TEST'}
        for side,new in zip(('c','rust'),pair):
            old=config('exit-mmap-'+side)
            self.assertEqual({k for k in old.keys()|new.keys() if old.get(k,'n')!=new.get(k,'n')},expected)
            G.check_config('exit-mmap-'+side,old,TARGET)
            G.check_config('exit-mmap-kunit-'+side,new,TARGET)
        with self.assertRaises(ValueError):G.compare(pair[0],pair[1]|{'CONFIG_DEBUG_LIST':'n'})

    def test_only_kunit_projected_and_input_immutable(self):
        values=config('exit-mmap-kunit-rust');original=copy.deepcopy(values)
        projected=G.vma.dup.copy.policy_config(values,G.TEST_CONTEXT)
        self.assertEqual(values,original)
        self.assertEqual({k for k in values if values[k]!=projected[k]},{'CONFIG_KUNIT'})
        self.assertEqual(projected['CONFIG_KUNIT'],'n')

    def test_unknown_context_and_incomplete_flags_rejected_at_each_layer(self):
        values=config('exit-mmap-kunit-rust')
        layers=[(G.vma,'vma-lifecycle-rust'),(G.vma.dup,'mm-dup-mmap-rust'),(G.vma.dup.copy,'mm-copy-rust')]
        for gate,profile in layers:
            gate.check_config(profile,values,TARGET,test_context=G.TEST_CONTEXT)
            for context in (None,'exit-mmap-kunit-v2',True,{},lambda:True):
                with self.subTest(profile=profile,context=context),self.assertRaises(ValueError):
                    gate.check_config(profile,values,TARGET,test_context=context)
        for key in ('KUNIT','KUNIT_DEFAULT_ENABLED','KUNIT_AUTORUN_ENABLED','RUNTIME_TESTING_MENU',
                    'KUNIT_DEFAULT_TIMEOUT','RUSIX_EXIT_MMAP_TEST','RUSIX_BRD_RUST'):
            bad=values.copy();bad.pop('CONFIG_'+key)
            with self.subTest(key=key),self.assertRaises(ValueError):G.check_config('exit-mmap-kunit-rust',bad,TARGET)
        for key in ('RUSIX_MM_RELEASE_TEST','RUSIX_RCU_SYNC_TEST'):
            with self.assertRaises(ValueError):G.check_config('exit-mmap-kunit-rust',values|{'CONFIG_'+key:'y'},TARGET)

    def test_ordinary_profiles_and_guest_never_accept_kunit(self):
        values=config('exit-mmap-kunit-rust')
        for profile in ('exit-mmap-c','exit-mmap-rust'):
            with self.assertRaises(ValueError):G.check_config(profile,values,TARGET)
        for profile in G.KUNIT_PROFILES:
            with self.assertRaises(ValueError):VM.validate_config(profile,'','')
        ordinary=config('exit-mmap-rust')
        with self.assertRaises(ValueError):G.check_config('exit-mmap-rust',ordinary|{'CONFIG_KUNIT':'y'},TARGET)

    def test_real_build_order_and_selection_routes(self):
        text=(ROOT/'rusix/scripts/build-kernel.sh').read_text()
        configure=text.index('allnoconfig')
        before=text.index('> "$evidence/exit-mmap-config-before.json"')
        build=text.index('bzImage',before)
        self.assertLess(configure,before);self.assertLess(before,build)
        self.assertIn('"$profile" == exit-mmap-kunit-c || "$profile" == exit-mmap-kunit-rust',text)
        self.assertIn('Teardown fixture selected outside its explicit KUnit profiles.',text)
        self.assertLess(text.index('preprocess-exit-mmap.py'),text.index('> "$evidence/exit-mmap-selection.json"'))
        for path in ('rusix/ci/run.sh','rusix/ci/run-container.sh'):
            script=(ROOT/path).read_text()
            for profile in G.KUNIT_PROFILES:self.assertIn(profile,script)

    def test_two_distinct_boots_and_ordinary_route(self):
        text=(ROOT/'rusix/ci/run.sh').read_text()
        start=text.index('elif [[ "$profile" == exit-mmap-kunit-c')
        end=text.index('elif [[',start+1);branch=text[start:end]
        self.assertEqual(branch.count('boot-kunit.sh'),2)
        self.assertIn('--exit-mmap-combined',branch);self.assertIn('--exit-mmap \\',branch)
        self.assertIn('"ci-$profile-exit-mmap"',branch)
        self.assertNotIn('test-exit-mmap-vm.py',branch)
        self.assertIn('test-exit-mmap-vm.py',text)

    def test_boot_filters_requirements_and_dependencies(self):
        text=(ROOT/'rusix/scripts/boot-kunit.sh').read_text()
        start=text.index('    --exit-mmap|');end=text.index('    --brd)',start);branch=text[start:end]
        for token in ('filter=rusix_exit_mmap',"filter='rusix_*'",'validate-exit-mmap-kunit.py','baseline=(--combined)',
                      'RUSIX_EXIT_MMAP_TEST','RUSIX_BRD_RUST','RUSIX_VMA_LIFECYCLE_RUST','cpus=2'):
            self.assertIn(token,branch)
        self.assertIn('Unrelated fixture enabled in teardown KUnit boot.',text)
        for name in ('validate-brd-kunit.py','validate-completion-kunit.py'):self.assertIn(name,text)
        self.assertIn('"$mode" == mm-release* || "$mode" == exit-mmap*',text)

    def test_nested_selection_context_is_recorded(self):
        for filename in ('verify-exit-mmap.py','verify-vma-lifecycle.py','verify-dup-mmap.py','verify-mm-copy.py'):
            text=(ROOT/'rusix/scripts'/filename).read_text()
            returns=[node.value for node in ast.walk(ast.parse(text)) if isinstance(node,ast.Return) and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id=='dict']
            self.assertTrue(any(any(k.arg=='test_context' for k in value.keywords) for value in returns),filename)
        paths=G.input_paths(Path('/out/builds/a'),Path('/src'),True,kunit=True)
        self.assertIn(Path('/src/rusix/configs/x86_64-exit-mmap-kunit-rust.config'),paths)
        for name in ('boot-kunit.sh','validate-exit-mmap-kunit.py','validate-completion-kunit.py','validate-brd-kunit.py'):
            self.assertIn(Path('/src/rusix/scripts')/name,paths)

if __name__=='__main__':unittest.main()
