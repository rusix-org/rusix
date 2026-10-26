#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Reject wrong batch selection; modeled records are not kernel evidence."""
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]

def load(name, file):
    spec = importlib.util.spec_from_file_location(name, PROJECT / 'scripts' / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

gate = load('batch_selection', 'verify-rcu-batch-selection.py')
preprocess = load('batch_preprocessor', 'preprocess-rcu-batch.py')
CPP_C = '''static void rcu_do_batch(struct rcu_data *rdp) {
rcu_segcblist_extract_done_cbs(x,y); count++; f(rhp);
rcu_segcblist_insert_done_cbs(x,y); rcu_segcblist_add_len(x,y); }
static _Bool rcu_do_batch_check_time(long count, long tlimit, _Bool jlimit_check, unsigned long jlimit) { return local_clock() >= tlimit; }
'''
CPP_RUST = '''static void rcu_do_batch(struct rcu_data *rdp) { rusix_rcu_do_batch(rdp); }
static _Bool rcu_do_batch_check_time(long count, long tlimit, _Bool jlimit_check, unsigned long jlimit) { return rusix_rcu_batch_check_time(count, tlimit, jlimit_check, jlimit); }
'''

class BatchSelection(unittest.TestCase):
    def config(self, profile):
        values = gate.lists.config_values((PROJECT / f'configs/x86_64-{profile}.config').read_text())
        values.update(CONFIG_X86_64='y', CONFIG_RCU_NEED_SEGCBLIST='y')
        return values

    def evidence(self, root, rust=False):
        (root / 'rcu-archive.txt').write_text('/out/tree.o\n/out/rcu_batch_test.o\n' + ('/out/rcu_batch_rust.o\n' if rust else ''))
        for name, symbols in (('tree', gate.HOOKS), ('fixture', gate.FIXTURE), ('rust', gate.BRIDGES),
                              ('kernel', gate.HOOKS + gate.FIXTURE + (gate.BRIDGES if rust else ()))):
            (root / f'rcu-batch-{name}-symbols.txt').write_text(''.join('1000 T ' + s + '\n' for s in symbols))
        (root/'tree.i').write_text(CPP_RUST if rust else CPP_C)
        (root/'rcu-batch-tree-disassembly.txt').write_text(''.join(
            ' 10: e8 00 00 00 00 call 0\n 11: R_X86_64_PLT32 '+s+'-0x4\n' for s in gate.BRIDGES) if rust else '')

    def test_profiles_require_policy_fixture_and_existing_rust_dependencies(self):
        for profile in gate.PROFILES:
            original = self.config(profile)
            gate.check_config(profile, original)
            for name in ('RUSIX_RCU_BATCH_TEST', 'RUSIX_RCU_LIST_TEST', 'RUSIX_RCU_LIST_RUST',
                         'RUSIX_COMPLETION_RUST', 'RUSIX_BRD_RUST', 'KUNIT'):
                changed = dict(original); changed['CONFIG_' + name] = 'n'
                with self.assertRaises(ValueError): gate.check_config(profile, changed)
            for name in ('RCU_NOCB_CPU', 'RCU_BOOST', 'PREEMPT_RT', 'MODULES'):
                changed = dict(original); changed['CONFIG_' + name] = 'y'
                with self.assertRaises(ValueError): gate.check_config(profile, changed)
            changed=dict(original);changed['CONFIG_RUSIX_RCU_BATCH_RUST']='n' if gate.PROFILES[profile] else 'y'
            with self.assertRaises(ValueError): gate.check_config(profile, changed)
        with self.assertRaises(ValueError): gate.check_config('rcu-list-rust', self.config('rcu-batch-c'))

    def test_unchanged_original_tree_and_mutation_rejected(self):
        source = PROJECT.parent / 'kernel/rcu/tree.c'
        gate.original_policy(source)
        with tempfile.TemporaryDirectory() as directory:
            changed = Path(directory) / 'tree.c'
            changed.write_bytes(source.read_bytes().replace(b'long count = 0;', b'long count = 1;', 1))
            with self.assertRaises(ValueError): gate.original_policy(changed)

    def test_exact_object_symbol_and_relocation_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = PROJECT.parent / 'kernel/rcu/tree.c'
            for rust in (False,True):
                self.evidence(root,rust)
                profile='rcu-batch-rust' if rust else 'rcu-batch-c'
                self.assertEqual(gate.check_objects(profile, root, source, root/'tree.i')['implementation'], 'rust' if rust else 'c')
                with (root/'rcu-archive.txt').open('a') as stream:stream.write('/out/rcu_batch_test.o\n')
                with self.assertRaises(ValueError): gate.check_objects(profile,root,source,root/'tree.i')
            self.evidence(root,True)
            (root/'rcu-batch-tree-disassembly.txt').write_text('')
            with self.assertRaises(ValueError):gate.check_objects('rcu-batch-rust',root,source,root/'tree.i')
            self.evidence(root,True)
            path=root/'rcu-batch-rust-symbols.txt';path.write_text(path.read_text()+'1000 T '+gate.BRIDGES[0]+'\n')
            with self.assertRaises(ValueError):gate.check_objects('rcu-batch-rust',root,source,root/'tree.i')

    def test_preprocessor_rejects_c_leakage_wrong_and_duplicate_dispatch(self):
        gate.check_preprocessed(CPP_C,False)
        gate.check_preprocessed(CPP_RUST,True)
        for text in (CPP_C,CPP_RUST+CPP_C,CPP_RUST.replace('rusix_rcu_do_batch(rdp);','rusix_rcu_do_batch(rdp); f(rhp);'),
                     CPP_RUST.replace('rusix_rcu_do_batch(rdp);','wrong(rdp);')):
            with self.assertRaises(ValueError):gate.check_preprocessed(text,True)
        with self.assertRaises(ValueError):gate.check_preprocessed(CPP_RUST,False)
        with self.assertRaises(ValueError):gate.check_relocation('10: nop\n11: R_X86_64_PLT32 rusix_rcu_do_batch-0x4\n',True)

    def test_pairs_differ_only_in_batch_selector(self):
        for prefix in ('rcu-batch-','rcu-batch-plain-'):
            c=(PROJECT/f'configs/x86_64-{prefix}c.config').read_text()
            rust=(PROJECT/f'configs/x86_64-{prefix}rust.config').read_text()
            self.assertEqual(gate.compare_configs(c,rust)['different_settings'],['CONFIG_RUSIX_RCU_BATCH_RUST'])
            with self.assertRaises(ValueError):gate.compare_configs(c,rust+'\nCONFIG_UNEXPECTED=y\n')

    def saved(self):
        # Representative strict structure; actual command parsing was separately
        # checked read-only against the retained historical C tree.o command.
        return ('savedcmd_kernel/rcu/tree.o := clang -nostdinc '+
                ' '.join('-include '+p for p in preprocess.REQUIRED_INCLUDES)+
                ' -Wp,-MMD,kernel/rcu/.tree.o.d -c -o kernel/rcu/tree.o /src/kernel/rcu/tree.c ; '+
                ' '.join(preprocess.OBJTOOL)+'\nsource_kernel/rcu/tree.o := /src/kernel/rcu/tree.c\n')

    def test_preprocessor_record_binds_actual_command_object_and_output(self):
        with tempfile.TemporaryDirectory() as directory:
            build=Path(directory)/'build'; evidence=Path(directory)/'evidence'
            (build/'kernel/rcu').mkdir(parents=True);evidence.mkdir()
            saved=build/'kernel/rcu/.tree.o.cmd';saved.write_text(self.saved())
            source=Path(directory)/'tree.c';source.write_text('source')
            (build/'.config').write_text('config')
            (build/'kernel/rcu/tree.o').write_bytes(b'object')
            output=build/'kernel/rcu/tree.i';output.write_text(CPP_RUST)
            sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
            record={'input_sha256':{str(p):sha(p) for p in (saved,build/'.config',build/'kernel/rcu/tree.o',source)},
                    'preprocessed_sha256':sha(output),'argv':preprocess.command(saved.read_text(),output),
                    'cwd':str(build),'output':str(output),'ignored_post_compile_argv':list(preprocess.OBJTOOL)}
            path=evidence/'rcu-batch-preprocess.json';path.write_text(json.dumps(record))
            (evidence/'rcu-batch-preprocess.exit').write_text('0\n')
            (evidence/'rcu-batch-preprocess.log').write_text('')
            gate.check_preprocess_record(evidence,source,output)
            output.write_text(CPP_C)
            with self.assertRaises(ValueError):gate.check_preprocess_record(evidence,source,output)
            output.write_text(CPP_RUST)
            record['argv'].insert(1,'-DCONFIG_RUSIX_RCU_BATCH_RUST=1');path.write_text(json.dumps(record))
            with self.assertRaises(ValueError):gate.check_preprocess_record(evidence,source,output)

    def test_actual_command_parser_rejects_shell_plugins_wrong_paths(self):
        saved=self.saved()
        argv=preprocess.command(saved,Path('/out/builds/test/kernel/rcu/tree.i'))
        self.assertEqual(argv[-3:],['-E','-o','/out/builds/test/kernel/rcu/tree.i'])
        for changed in (saved.replace('clang ','sh '),saved.replace('-nostdinc','-fplugin=/tmp/x'),
                        saved.replace('-nostdinc','$(touch /tmp/x)'),saved.replace('-nostdinc','-o other.o'),
                        saved.replace(' ; ',' && '),saved.replace(' ; ',' ; echo bad ; '),
                        saved.replace('/src/kernel/rcu/tree.c','/src/kernel/rcu/other.c'),
                        saved.replace('kernel/rcu/tree.o /src','other.o /src'),
                        saved.replace('/src/include/linux/kconfig.h','/tmp/kconfig.h')):
            with self.assertRaises(ValueError):preprocess.command(changed,Path('/out/tree.i'))


if __name__ == '__main__': unittest.main()
