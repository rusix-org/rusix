#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Fresh-build ordering checks; never invoke a kernel build."""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]

def check_order(text):
    configure = text.index('KCONFIG_ALLCONFIG="$config" allnoconfig')
    saved = text.index('cp "$out/.config" "$evidence/config"')
    before = text.index('> "$evidence/copy-vma-config-before.json"')
    build = text.index('-j2 bzImage')
    after = text.index('> "$evidence/copy-vma-config-after.json"')
    preprocess = text.index('"$RUSIX_PROJECT/scripts/preprocess-copy-vma.py"')
    selection = text.index('> "$evidence/copy-vma-selection.json"')
    if not configure < saved < before < build < after < preprocess < selection:
        raise ValueError('Copy-VMA checks precede required build inputs')

class Tests(unittest.TestCase):
    def test_fresh_config_and_object_order(self):
        check_order((ROOT/'scripts/build-kernel.sh').read_text())

    def test_preconfiguration_check_rejected(self):
        text=(ROOT/'scripts/build-kernel.sh').read_text()
        marker='> "$evidence/copy-vma-config-before.json"'
        changed=marker+'\n'+text.replace(marker, '> "$evidence/removed-check.json"')
        with self.assertRaises(ValueError):
            check_order(changed)

    def test_pair_keeps_teardown_and_only_copy_axis(self):
        c=(ROOT/'configs/x86_64-copy-vma-c.config').read_text()
        rust=(ROOT/'configs/x86_64-copy-vma-rust.config').read_text()
        self.assertIn('CONFIG_RUSIX_EXIT_MMAP_RUST=y', c)
        self.assertEqual(c.replace('# CONFIG_RUSIX_COPY_VMA_RUST is not set',
                                   'CONFIG_RUSIX_COPY_VMA_RUST=y'), rust)

if __name__ == '__main__':
    unittest.main()
