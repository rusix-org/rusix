# SPDX-License-Identifier: GPL-2.0-only
"""Literal opt-in copy/link source restoration, before teardown restoration."""
import hashlib
ID = 'copy-vma-v1'
START = '#ifdef CONFIG_RUSIX_COPY_VMA_RUST\n'
END = '#endif /* CONFIG_RUSIX_COPY_VMA_RUST */\n'
SHIMS = ('extern void rusix_vma_link_file_locked(struct vm_area_struct *vma,\n\t\t\t\t     struct address_space *mapping);\nstatic void __vma_link_file(struct vm_area_struct *vma,\n\t\t\t    struct address_space *mapping)\n{\n\trusix_vma_link_file_locked(vma, mapping);\n}\n#else\n', '#include "copy_vma_impl.h"\n#else\n', 'int vma_link(struct mm_struct *mm, struct vm_area_struct *vma)\n{\n\tVMA_ITERATOR(vmi, mm, 0);\n\n\treturn rusix_vma_link(mm, vma, &vmi);\n}\n#else\n', 'struct vm_area_struct *copy_vma(struct vm_area_struct **vmap,\n\tunsigned long addr, unsigned long len, pgoff_t pgoff,\n\tbool *need_rmap_locks, bool keep_source)\n{\n\tstruct vm_area_struct *vma = *vmap;\n\tunsigned long vma_start = vma->vm_start;\n\tstruct mm_struct *mm = vma->vm_mm;\n\tVMA_ITERATOR(vmi, mm, addr);\n\tVMG_VMA_STATE(vmg, &vmi, NULL, vma, addr, addr + len);\n\tstruct rusix_copy_vma_context ctx = {\n\t\t.vmi = &vmi, .vmg = &vmg, .source = vma,\n\t\t.mm = mm, .source_start = vma_start,\n\t};\n\n\treturn rusix_copy_vma(&ctx, vmap, addr, len, pgoff,\n\t\t\t      need_rmap_locks, keep_source);\n}\n#else\n')
BASE_SHA256 = '1dd5a0bbb2ae056796b0a12e506159c8af841cf38b0cb77f72a4b7d37c30950d'
EXTRA = ('mm/copy_vma_impl.h','mm/copy_vma_rust.rs',
         'include/linux/rmap.h','include/linux/hugetlb.h','include/linux/pagemap.h',
         'include/linux/dcache.h','include/linux/fs.h','rusix/scripts/verify-copy-vma.py',
         'rusix/scripts/preprocess-copy-vma.py')

def restore(text):
    if text.count(START)!=4 or text.count(END)!=4:
        raise ValueError('Missing/ambiguous copy VMA guards')
    out=''
    for shim in SHIMS:
        before,rest=text.split(START,1)
        if not rest.startswith(shim):raise ValueError('Changed copy VMA shim/order')
        original,text=rest[len(shim):].split(END,1)
        out+=before+original
    out+=text
    if hashlib.sha256(out.encode()).hexdigest()!=BASE_SHA256:
        raise ValueError('Changed copy VMA original source or boundary')
    return out
