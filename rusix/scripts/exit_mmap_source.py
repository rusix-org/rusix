#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exact opt-in restoration of the three reviewed teardown selectors."""
import hashlib
import copy_vma_source as copy_extension
ID = 'exit-mmap-v1'
MERGE_ID = 'vma-merge-v1'
MERGE_EXTRA = ('mm/vma_merge.h', 'mm/vma_merge_impl.h', 'mm/vma_merge_rust.rs',
               'rusix/scripts/vma_merge_source.py', 'rusix/scripts/verify-vma-merge.py',
               'rusix/scripts/preprocess-vma-merge.py')
MODIFY_ID = 'vma-modify-v1'
MODIFY_EXTRA = ('mm/vma_modify.h', 'mm/vma_modify_impl.h', 'mm/vma_modify_rust.rs',
                'rusix/scripts/vma_modify_source.py', 'rusix/scripts/verify-vma-modify.py',
                'rusix/scripts/preprocess-vma-modify.py')
START = '#ifdef CONFIG_RUSIX_EXIT_MMAP_RUST\n'
END = '#endif /* CONFIG_RUSIX_EXIT_MMAP_RUST */\n'
REGIONS = {'mm/mmap.c': ('#include "exit_mmap_impl.h"\nextern void rusix_exit_mmap(struct mm_struct *mm, struct rusix_exit_context *ctx);\nvoid exit_mmap(struct mm_struct *mm)\n{\n\tstruct mmu_gather tlb;\n\tVMA_ITERATOR(vmi, mm, 0);\n\tstruct rusix_exit_context ctx = { .vmi = &vmi, .tlb = &tlb };\n\n\trusix_exit_mmap(mm, &ctx);\n}\n#else\n', '302d70f436d72da9ebb999eaca9f748d607136b707748d0861eef297da78e05b'), 'mm/vma.c': ('#include "remove_vma_impl.h"\n#else\n', '7f77e1d0dfaa9afa9e6bb553393b5943da5f7470e6659f2742bec85238c4c252'), 'mm/internal.h': ('void rusix_vma_close(struct vm_area_struct *vma);\nstatic inline void vma_close(struct vm_area_struct *vma)\n{\n\trusix_vma_close(vma);\n}\n#else\n', 'bd74d6ddc2d55d8f5f9c3654e2e9ab80a2551189bc42f30cdcbe58767754d4f2')}

EXTRA = ('mm/mmap.c','mm/vma.c','mm/internal.h','mm/exit_mmap_impl.h',
         'mm/remove_vma_impl.h','mm/exit_mmap_rust.rs',
         'rusix/scripts/exit_mmap_source.py','rusix/scripts/copy_vma_source.py','rusix/scripts/verify-exit-mmap.py')

def paths(source, extension):
    if extension not in (ID, copy_extension.ID, MODIFY_ID, MERGE_ID): raise ValueError('Unknown source extension')
    return [source/name for name in EXTRA + (copy_extension.EXTRA if extension in (copy_extension.ID, MODIFY_ID, MERGE_ID) else ()) + (MODIFY_EXTRA if extension in (MODIFY_ID, MERGE_ID) else ()) + (MERGE_EXTRA if extension == MERGE_ID else ())]

def restore(name, text):
    if name not in REGIONS: raise ValueError('Unreviewed source region')
    if text.count(START)!=1 or text.count(END)!=1:
        raise ValueError('Missing/ambiguous teardown guards')
    before, rest = text.split(START)
    shim, expected = REGIONS[name]
    if not rest.startswith(shim): raise ValueError('Changed teardown shim')
    original, after = rest[len(shim):].split(END)
    restored = before+original+after
    if hashlib.sha256(restored.encode()).hexdigest()!=expected:
        raise ValueError('Changed original source or teardown boundary: '+name)
    return restored

def validate(source, extension):
    paths(source, extension)
    raw, restored, hashes = {}, {}, {}
    for name in REGIONS:
        data=(source/name).read_bytes(); raw[name]=hashlib.sha256(data).hexdigest()
        text=data.decode()
        if extension == MERGE_ID and name == 'mm/vma.c':
            import vma_merge_source
            vma_merge_source.source_policy(source, source_context=extension)
            text=vma_merge_source.restore(text, source_context=extension)
        if extension in (MODIFY_ID, MERGE_ID) and name == 'mm/vma.c':
            import vma_modify_source
            if extension == MODIFY_ID:
                vma_modify_source.source_policy(source, source_context=extension)
            text=vma_modify_source.restore(text, source_context=MODIFY_ID)
        if extension in (copy_extension.ID, MODIFY_ID, MERGE_ID) and name == 'mm/vma.c':
            text=copy_extension.restore(text)
        restored[name]=restore(name,text)
        hashes[name]=hashlib.sha256(restored[name].encode()).hexdigest()
    return restored, dict(extension=extension,raw_sha256=raw,restored_sha256=hashes)


def require_unchanged(paths, before):
    after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    if before!=after:raise ValueError('Source/artifact inputs changed during verification')
