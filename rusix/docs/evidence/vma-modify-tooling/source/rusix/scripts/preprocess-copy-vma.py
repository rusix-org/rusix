#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Four actual compiler units with the explicit reviewed copy-VMA extension."""
import importlib.util
from pathlib import Path
import copy_vma_source
spec=importlib.util.spec_from_file_location('copy_vma_pre_exit',Path(__file__).with_name('preprocess-exit-mmap.py'))
exit_pre=importlib.util.module_from_spec(spec);spec.loader.exec_module(exit_pre)

def inputs(build,source):
    return exit_pre.inputs(build,source,source_extension=copy_vma_source.ID)

def record(build,source):
    return exit_pre.record(build,source,source_extension=copy_vma_source.ID)

if __name__=='__main__':exit_pre.main(source_extension=copy_vma_source.ID)
