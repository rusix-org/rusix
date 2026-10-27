#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Four real compiler units with an explicit merge source closure."""
import importlib.util
from pathlib import Path
import vma_merge_source
spec=importlib.util.spec_from_file_location('merge_pre_exit',Path(__file__).with_name('preprocess-exit-mmap.py'))
exit_pre=importlib.util.module_from_spec(spec)
spec.loader.exec_module(exit_pre)
def inputs(build,source):
    return exit_pre.inputs(build,source,source_extension=vma_merge_source.ID)
def record(build,source):
    return exit_pre.record(build,source,source_extension=vma_merge_source.ID)
if __name__=='__main__':exit_pre.main(source_extension=vma_merge_source.ID)
