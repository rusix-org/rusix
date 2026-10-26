#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Production RCU integration profiles and evidence continuity rejection tests."""
import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.dont_write_bytecode = True
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'scripts'))
import server_target


def load(name):
    spec = importlib.util.spec_from_file_location(name, PROJECT / 'scripts' / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


selection = load('verify-rcu-list-selection.py')
continuity = load('verify-rcu-list-continuity.py')
common = load('test-brd-vm.py')
ext4 = load('test-brd-ext4-vm.py')
parameters = load('test-brd-fixed-parameters-vm.py')
partitions = load('test-brd-partitions-vm.py')


def config(profile):
    if profile in server_target.RCU_PROFILES:
        text = server_target.derive((PROJECT / 'configs/x86_64-server.config').read_text(), profile)
    else:
        text = (PROJECT / f'configs/x86_64-{profile}.config').read_text()
    # Model only architecture-derived settings for host policy tests; no claim
    # that this substitutes for a real Kconfig resolution or kernel build.
    return text + 'CONFIG_X86_64=y\nCONFIG_TREE_RCU=y\nCONFIG_RCU_NEED_SEGCBLIST=y\nCONFIG_HAVE_ARCH_TRACEHOOK=y\n'


class IntegrationTests(unittest.TestCase):
    def test_pairs_and_production_selectors(self):
        for family in ('ext4', 'server'):
            prefix = f'rcu-list-{family}-'
            selection.compare_configs(config(prefix+'c'), config(prefix+'rust'))
            for side in ('c', 'rust'):
                profile = prefix + side
                selection.check_config(profile, selection.config_values(config(profile)))

    def test_kernel_fixture_and_unrelated_axes_rejected(self):
        for profile in selection.PRODUCTION_PROFILES:
            good = selection.config_values(config(profile))
            for name, value in (('KUNIT', 'y'), ('RUSIX_RCU_LIST_TEST', 'y'),
                                ('RUSIX_COMPLETION_RUST', 'n'), ('RUSIX_BRD_RUST', 'n'),
                                ('MODULES', 'y'), ('RCU_NOCB_CPU', 'y')):
                changed = dict(good); changed['CONFIG_'+name] = value
                with self.assertRaises(ValueError): selection.check_config(profile, changed)
            changed = dict(good)
            changed['CONFIG_RUSIX_RCU_LIST_RUST'] = 'n' if profile.endswith('rust') else 'y'
            with self.assertRaises(ValueError): selection.check_config(profile, changed)

    def test_production_requires_no_fixture_objects(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            symbols = ''.join(f'00000000 T {symbol}\n' for symbol in selection.SYMBOLS)
            for filename in ('rcu-object-symbols.txt', 'rcu-kernel-symbols.txt'):
                (root / filename).write_text(symbols)
            for profile in selection.PRODUCTION_PROFILES:
                obj = 'rcu_segcblist_rust.o' if profile.endswith('rust') else 'rcu_segcblist.o'
                good = '/build/kernel/rcu/' + obj + '\n'
                (root / 'rcu-archive.txt').write_text(good)
                selection.check_objects(profile, root)
                for bad in (good+'/build/kernel/rcu/rcu_list_test.o\n', good+good, ''):
                    (root / 'rcu-archive.txt').write_text(bad)
                    with self.assertRaises(ValueError): selection.check_objects(profile, root)

    def test_server_axis_is_explicit_and_declared_source_unchanged(self):
        source = (PROJECT / 'configs/x86_64-server.config').read_text()
        rust = server_target.derive(source, 'rcu-list-server-rust')
        c = server_target.derive(source, 'rcu-list-server-c')
        result = server_target.compare(source, rust, c, 'rcu-list')
        self.assertEqual(result['resolved_config_differences'], {server_target.RCU: ['y','n']})
        self.assertEqual(server_target.derive(source,'server'), source)
        with self.assertRaises(ValueError): server_target.compare(source,rust,c)
        with self.assertRaises(ValueError): server_target.compare(source,rust+'CONFIG_UNEXPECTED=y\n',c,'rcu-list')

    def test_all_ext4_workloads_require_rust_core_and_correct_policy(self):
        for side in ('c', 'rust'):
            profile = 'rcu-list-ext4-' + side
            for runner in (common, ext4, parameters, partitions):
                self.assertEqual(runner.validate_selection(profile,'implementation=brd-rust',config(profile),'implementation=completion-rust'),'brd-rust')
                with self.assertRaises(ValueError): runner.validate_selection(profile,'implementation=brd-rust',config(profile),'implementation=completion-c')
                with self.assertRaises(ValueError): runner.validate_selection(profile,'implementation=brd-c',config(profile),'implementation=completion-rust')
        for profile in server_target.RCU_PROFILES:
            ext4.validate_selection(profile,'implementation=brd-rust',config(profile),'implementation=completion-rust')
            with self.assertRaises(ValueError): common.validate_selection(profile,'implementation=brd-rust',config(profile),'implementation=completion-rust')

    def test_missing_runtime_rcu_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            with self.assertRaises(FileNotFoundError):
                common.validate_rcu_evidence('rcu-list-ext4-rust',config('rcu-list-ext4-rust'),Path(name))

    def test_runtime_proof_rehashes_each_dependency(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            obj = root / 'kernel/rcu/rcu_segcblist_rust.o'
            obj.parent.mkdir(parents=True)
            obj.write_bytes(b'fixture object bytes')
            dependency = root / 'rust/bindings/bindings_generated.rs'
            dependency.parent.mkdir(parents=True)
            dependency.write_bytes(b'fixture dependency')
            (root / 'rcu-archive.txt').write_text(str(obj)+'\n')
            symbols = ''.join(f'00000000 T {symbol}\n' for symbol in selection.SYMBOLS)
            for filename in ('rcu-object-symbols.txt', 'rcu-kernel-symbols.txt'):
                (root / filename).write_text(symbols)
            proof = selection.check_objects('rcu-list-ext4-rust', root)
            (root / 'rcu-list-selection.json').write_text(json.dumps(proof))
            (root / 'rcu-list-reference.diff').write_text('')
            paths = [obj, dependency] + [PROJECT.parent / relative for relative in (
                'kernel/rcu/rcu_segcblist.c', 'kernel/rcu/rcu_segcblist_rust.rs',
                'kernel/rcu/rcu_segcblist.h', 'include/linux/rcu_segcblist.h',
                'rust/helpers/rcu_list.c', 'rust/helpers/rcu_list_test.c',
                'kernel/rcu/rcu_list_test.c', 'kernel/rcu/Kconfig', 'kernel/rcu/Makefile',
                'rust/bindings/bindings_helper.h', 'rusix/scripts/verify-rcu-list-selection.py',
                'rusix/configs/x86_64-rcu-list-ext4-rust.config')]
            hashes = ''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p)+'\n' for p in paths)
            (root / 'rcu-list-inputs.sha256').write_text(hashes)
            common.validate_rcu_evidence('rcu-list-ext4-rust',config('rcu-list-ext4-rust'),root)
            (root / 'rcu-list-inputs.sha256').write_text('\n'.join(hashes.splitlines()[:-1])+'\n')
            with self.assertRaises(ValueError):
                common.validate_rcu_evidence('rcu-list-ext4-rust',config('rcu-list-ext4-rust'),root)
            (root / 'rcu-list-inputs.sha256').write_text(hashes)
            dependency.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                common.validate_rcu_evidence('rcu-list-ext4-rust',config('rcu-list-ext4-rust'),root)

    def test_continuity_rejects_kernel_and_fixture_changes(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            def git(*args):
                return subprocess.check_output(['git','-C',name,*args],stderr=subprocess.DEVNULL).decode().strip()
            git('init');git('config','user.name','Test fixture');git('config','user.email','fixture@example.invalid')
            paths = ['kernel/rcu/rcu_list_test.c','kernel/rcu/rcu_segcblist_rust.rs','rusix/scripts/build-kernel.sh']
            paths += [f'rusix/configs/x86_64-{p}.config' for p in continuity.KUNIT_PROFILES]
            paths += ['rusix/scripts/'+p for p in ('boot-kunit.sh','validate-brd-kunit.py','validate-completion-kunit.py','validate-rcu-kunit.py')]
            for path in paths:
                p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('baseline\n')
            git('add','.');git('commit','-m','fixture baseline');baseline=git('rev-parse','HEAD')
            (root/'rusix/scripts/build-kernel.sh').write_text('reviewed integration tooling\n')
            git('add','.');git('commit','-m','fixture tooling')
            self.assertEqual(continuity.verify(root,baseline,'HEAD')['status'],'PASS')
            tooling=git('rev-parse','HEAD')
            for path in ('kernel/rcu/rcu_list_test.c','kernel/rcu/rcu_segcblist_rust.rs'):
                (root/path).write_text('changed\n');git('add','.');git('commit','-m','forbidden fixture change')
                with self.assertRaises(ValueError): continuity.verify(root,baseline,'HEAD')
                git('reset','--hard',tooling)


if __name__ == '__main__': unittest.main()
