/* SPDX-License-Identifier: GPL-2.0-only */
/* Included in vma.c solely to call the genuine private selected entrypoints. */
#include <linux/rusix_vma_merge_test.h>

int rusix_merge_test_dispatch(struct mm_struct *mm, enum rusix_merge_case mode,
			     struct vm_area_struct *prev, struct vm_area_struct *middle,
			     struct vm_area_struct *next, struct rusix_merge_outcome *out)
{
	bool existing = mode <= RUSIX_EXISTING_PREALLOC_SILENT ||
		mode == RUSIX_MIDDLE_CLOSE || mode == RUSIX_NEXT_CLOSE ||
		mode == RUSIX_BOTH_SUCCESS || mode == RUSIX_EXISTING_SUCCESS;
	bool shrink = mode == RUSIX_SHRINK_PREALLOC || mode == RUSIX_SHRINK_SUCCESS;
	bool expand = mode == RUSIX_EXPAND_CLONE ||
		mode == RUSIX_EXPAND_PREALLOC_REPORT ||
		mode == RUSIX_EXPAND_PREALLOC_SILENT || mode == RUSIX_EXPAND_SUCCESS;
	bool silent = mode == RUSIX_EXISTING_CLONE_SILENT ||
		mode == RUSIX_EXISTING_PREALLOC_SILENT || mode == RUSIX_NEW_PREALLOC_SILENT ||
		mode == RUSIX_EXPAND_PREALLOC_SILENT;
	enum rusix_merge_fault fault = mode == RUSIX_EXISTING_CLONE_REPORT ||
		mode == RUSIX_EXISTING_CLONE_SILENT || mode == RUSIX_EXPAND_CLONE ?
		RUSIX_FAULT_CLONE : mode <= RUSIX_SHRINK_PREALLOC ?
		RUSIX_FAULT_MAPLE : RUSIX_FAULT_NONE;
	unsigned long start = existing ? middle->vm_start : prev->vm_end;
	unsigned long end = existing ? middle->vm_end : next ? next->vm_start : prev->vm_end;
	struct vm_area_struct *context_vma = existing ? middle : prev;

	VMA_ITERATOR(vmi, mm, existing ? middle->vm_start : prev->vm_start);
	VMG_VMA_STATE(vmg, &vmi, prev, context_vma, start, end);
	struct vm_area_struct *result = NULL;
	struct vm_area_struct *source = existing ? middle : next;
	int ret, expected_state;

	mmap_assert_write_locked(mm);
	/* The fixture validates ranges/flags before reaching this dispatcher. */
	vmg.give_up_on_oom = silent;
	vmg.vm_flags = prev->vm_flags;
	if (existing) {
		if (vma_iter_load(&vmi) != middle)
			return -EINVAL;
	} else if (shrink) {
		if (vma_iter_load(&vmi) != prev)
			return -EINVAL;
	} else {
		vmg.middle = NULL;
		vmg.next = next;
		vmg.anon_vma = NULL;
		vmg.pgoff = prev->vm_pgoff + vma_pages(prev);
		if (expand) {
			vmg.target = prev;
			vmg.start = prev->vm_start;
			vmg.end = next->vm_end;
			vmg.pgoff = prev->vm_pgoff;
		} else {
			/* New-range cursor must be at the gap, not at prev. */
			vma_iter_set(&vmi, start);
			vma_iter_load(&vmi);
		}
	}
	ret = rusix_merge_test_arm(mm, &vmi.mas, prev, source, fault);
	if (ret)
		return ret;
	if (existing)
		result = vma_merge_existing_range(&vmg);
	else if (shrink)
		ret = vma_shrink(&vmi, prev, prev->vm_start + PAGE_SIZE,
				 prev->vm_end, prev->vm_pgoff + 1);
	else if (expand)
		ret = vma_expand(&vmg);
	else
		result = vma_merge_new_range(&vmg);
	out->returned = (unsigned long)result;
	out->error = ret;
	out->state = vmg.state;
	out->cursor = vma_iter_addr(&vmi);
	/* Disarm before the stack cursor or descriptors can lose ownership. */
	if (rusix_merge_test_disarm(&out->observed))
		ret = -EIO;
	vma_iter_free(&vmi);
	if (ret == -EIO)
		return ret;
	if (fault != RUSIX_FAULT_NONE) {
		if ((expand || shrink) ? out->error != -ENOMEM : result != NULL)
			return -EINVAL;
		/* Direct expansion's clone failure returns without setting state. */
		expected_state = shrink || mode == RUSIX_EXPAND_CLONE ? VMA_MERGE_START :
			silent ? (expand ? VMA_MERGE_START : VMA_MERGE_NOMERGE) :
			VMA_MERGE_ERROR_NOMEM;
		if (out->state != expected_state)
			return -EINVAL;
		if (existing && out->cursor != start)
			return -EINVAL;
	} else if (mode == RUSIX_MIDDLE_CLOSE) {
		if (result || out->state != VMA_MERGE_NOMERGE)
			return -EINVAL;
	} else if (expand || shrink) {
		if (out->error)
			return -EINVAL;
	} else if (result != prev || out->state != VMA_MERGE_SUCCESS) {
		return -EINVAL;
	}
	return 0;
}
