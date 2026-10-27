/* SPDX-License-Identifier: GPL-2.0-only */
/* Canonical primitives from kernel/fork.c, Copyright (C) 1991, 1992 Linus Torvalds.
 * Included only by fork.c after dup_mmap and the MM construction/release adapters.
 * Shared foreign accesses remain C; transaction branches and rollback stay Rust.
 */
#ifndef RUSIX_MM_COPY_IMPL_H
#define RUSIX_MM_COPY_IMPL_H

extern const u64 rusix_mm_copy_clone_vm;
void rusix_mm_copy_descriptor(struct mm_struct *mm, struct mm_struct *oldmm);
struct user_namespace *rusix_mm_copy_user_ns(struct mm_struct *mm);
void rusix_mm_copy_uprobe_start(void);
void rusix_mm_copy_uprobe_end(void);
int rusix_mm_copy_mappings(struct mm_struct *mm, struct mm_struct *oldmm);
void rusix_mm_copy_hiwater(struct mm_struct *mm);
bool rusix_mm_copy_binfmt_get(struct mm_struct *mm);
void rusix_mm_copy_binfmt_clear(struct mm_struct *mm);
void rusix_mm_copy_task_counters(struct task_struct *tsk);
void rusix_mm_copy_task_mm(struct task_struct *tsk, struct mm_struct *mm);
void rusix_mm_copy_users_get(struct mm_struct *mm);
void rusix_mm_copy_cid_fork(struct task_struct *tsk);

const u64 rusix_mm_copy_clone_vm = CLONE_VM;
void rusix_mm_copy_descriptor(struct mm_struct *mm, struct mm_struct *oldmm)
{
	memcpy(mm, oldmm, sizeof(*mm));
}
struct user_namespace *rusix_mm_copy_user_ns(struct mm_struct *mm)
{
	return mm->user_ns;
}
void rusix_mm_copy_uprobe_start(void) { uprobe_start_dup_mmap(); }
void rusix_mm_copy_uprobe_end(void) { uprobe_end_dup_mmap(); }
int rusix_mm_copy_mappings(struct mm_struct *mm, struct mm_struct *oldmm)
{
	return dup_mmap(mm, oldmm);
}
void rusix_mm_copy_hiwater(struct mm_struct *mm)
{
	mm->hiwater_rss = get_mm_rss(mm);
	mm->hiwater_vm = mm->total_vm;
}
bool rusix_mm_copy_binfmt_get(struct mm_struct *mm)
{
	return try_module_get(mm->binfmt->module);
}
void rusix_mm_copy_binfmt_clear(struct mm_struct *mm) { mm->binfmt = NULL; }
void rusix_mm_copy_task_counters(struct task_struct *tsk)
{
	tsk->min_flt = tsk->maj_flt = 0;
	tsk->nvcsw = tsk->nivcsw = 0;
#ifdef CONFIG_DETECT_HUNG_TASK
	tsk->last_switch_count = tsk->nvcsw + tsk->nivcsw;
	tsk->last_switch_time = 0;
#endif
}
void rusix_mm_copy_task_mm(struct task_struct *tsk, struct mm_struct *mm)
{
	tsk->mm = mm;
	tsk->active_mm = mm;
}
void rusix_mm_copy_users_get(struct mm_struct *mm) { mmget(mm); }
void rusix_mm_copy_cid_fork(struct task_struct *tsk) { sched_mm_cid_fork(tsk); }
#endif
