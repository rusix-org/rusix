/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _LINUX_RUSIX_VMA_MERGE_TEST_H
#define _LINUX_RUSIX_VMA_MERGE_TEST_H
/* Test-only native operation observations. No production ABI or layout contract. */
#include <linux/types.h>
struct vm_area_struct;
struct mm_struct;
struct ma_state;

enum rusix_merge_case {
	RUSIX_EXISTING_CLONE_REPORT,
	RUSIX_EXISTING_CLONE_SILENT,
	RUSIX_EXISTING_PREALLOC_REPORT,
	RUSIX_EXISTING_PREALLOC_SILENT,
	RUSIX_NEW_PREALLOC_REPORT,
	RUSIX_NEW_PREALLOC_SILENT,
	RUSIX_EXPAND_CLONE,
	RUSIX_EXPAND_PREALLOC_REPORT,
	RUSIX_EXPAND_PREALLOC_SILENT,
	RUSIX_SHRINK_PREALLOC,
	RUSIX_MIDDLE_CLOSE,
	RUSIX_NEXT_CLOSE,
	RUSIX_BOTH_SUCCESS,
	RUSIX_NEW_NEXT_CLOSE,
	RUSIX_EXISTING_SUCCESS,
	RUSIX_NEW_SUCCESS,
	RUSIX_EXPAND_SUCCESS,
	RUSIX_SHRINK_SUCCESS,
	RUSIX_MERGE_CASES,
};
enum rusix_merge_fault { RUSIX_FAULT_NONE, RUSIX_FAULT_CLONE, RUSIX_FAULT_MAPLE };
struct rusix_merge_observation {
	unsigned int clone_begin, clone_end, clone_nowait, clone_retry;
	unsigned int maple_begin, maple_end, maple_injected;
	unsigned int node_request, store_type;
	int clone_result, maple_result;
	bool clone_cleared, maple_reset, malformed;
};
struct rusix_merge_outcome {
	unsigned long returned;
	unsigned long cursor;
	int error, state;
	struct rusix_merge_observation observed;
};
void rusix_merge_test_clone_begin(struct vm_area_struct *dst, struct vm_area_struct *src);
bool rusix_merge_test_clone_fail(struct vm_area_struct *dst, struct vm_area_struct *src,
				gfp_t flags);
void rusix_merge_test_clone_end(struct vm_area_struct *dst, struct vm_area_struct *src, int ret);
void rusix_merge_test_maple_begin(struct ma_state *mas);
bool rusix_merge_test_maple_fail(struct ma_state *mas);
void rusix_merge_test_maple_end(struct ma_state *mas, int ret);
int rusix_merge_test_arm(struct mm_struct *mm, struct ma_state *mas,
			struct vm_area_struct *dst, struct vm_area_struct *src,
			enum rusix_merge_fault fault);
int rusix_merge_test_disarm(struct rusix_merge_observation *out);
int rusix_merge_test_dispatch(struct mm_struct *mm, enum rusix_merge_case mode,
			     struct vm_area_struct *prev, struct vm_area_struct *middle,
			     struct vm_area_struct *next, struct rusix_merge_outcome *out);
#endif
