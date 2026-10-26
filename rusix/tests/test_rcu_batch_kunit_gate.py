#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Strict isolated/combined RCU batch gate regression coverage."""
import copy
import importlib.util
from pathlib import Path
import unittest
import sys
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('rcu_gate', Path(__file__).resolve().parents[1] / 'scripts/validate-rcu-batch-kunit.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

def suite(name, cases=()):
    return {'name': name, 'sub_groups': [],
            'test_cases': [{'name': case, 'status': 'PASS'} for case in cases],
            'misc': {'tests': len(cases), 'passed': len(cases), 'failed': 0,
                     'crashed': 0, 'skipped': 0, 'errors': 0}}

def result(combined=False):
    inventory = dict(gate.SUITES)
    if combined:
        inventory.update(gate.lists.SUITES)
        inventory.update(gate.completion.SUITES)
        inventory.update(gate.common.SUITES)
    root = suite('KUnit Test Group')
    root['sub_groups'] = [suite(name, cases) for name, cases in inventory.items()]
    return root

class RcuGateTests(unittest.TestCase):
    def test_exact_counts(self):
        self.assertEqual(gate.validate(result()), 7)
        self.assertEqual(gate.validate(result(True), True), 93)

    def test_every_missing_duplicate_or_bad_case_rejected(self):
        for combined in (False, True):
            original = result(combined)
            for group_index, group in enumerate(original['sub_groups']):
                for index, case in enumerate(group['test_cases']):
                    for mutation in ('missing', 'duplicate', 'FAIL', 'SKIP', 'CRASH', 'UNKNOWN'):
                        changed = copy.deepcopy(original)
                        cases = changed['sub_groups'][group_index]['test_cases']
                        if mutation == 'missing': cases.pop(index)
                        elif mutation == 'duplicate': cases.append(copy.deepcopy(case))
                        else: cases[index]['status'] = mutation
                        with self.assertRaises(ValueError): gate.validate(changed, combined)

    def test_wrong_mode_unknown_suite_and_missing_suite_rejected(self):
        for wrong, combined in ((result(True),False),(result(),True)):
            with self.assertRaises(ValueError): gate.validate(wrong,combined)
        for combined in (False,True):
            original=result(combined)
            for groups in (original['sub_groups'][1:], original['sub_groups']*2,
                           original['sub_groups']+[suite('rusix_unexpected',['extra'])],
                           original['sub_groups']+[suite('rusix_unexpected')]):
                changed=copy.deepcopy(original);changed['sub_groups']=groups
                with self.assertRaises(ValueError): gate.validate(changed,combined)

    def test_unknown_case_and_bad_total_rejected(self):
        for mutation in ('name','passed','skipped'):
            changed=result()
            if mutation=='name': changed['sub_groups'][0]['test_cases'][0]['name']='unknown'
            else: changed['sub_groups'][0]['misc'][mutation]+=1
            with self.assertRaises(ValueError): gate.validate(changed)

if __name__ == '__main__': unittest.main()
