/* SPDX-License-Identifier: GPL-2.0-only */
/* Canonical primitives from kernel/fork.c, Copyright (C) 1991, 1992 Linus Torvalds.
 * Included only by fork.c after mm_construction_impl.h. No whole-MM references
 * or combined cleanup policy: shared accesses and LKMM operations remain C.
 */
#ifndef RUSIX_MM_RELEASE_IMPL_H
#define RUSIX_MM_RELEASE_IMPL_H

void rusix_mm_release_might_sleep(void);
bool rusix_mm_release_users_dec(struct mm_struct *mm);
void rusix_mm_release_users_check(struct mm_struct *mm);
void rusix_mm_release_uprobes(struct mm_struct *mm);
void rusix_mm_release_aio(struct mm_struct *mm);
void rusix_mm_release_ksm(struct mm_struct *mm);
void rusix_mm_release_khugepaged(struct mm_struct *mm);
void rusix_mm_release_mappings(struct mm_struct *mm);
void rusix_mm_release_huge_zero(struct mm_struct *mm);
void rusix_mm_release_exe(struct mm_struct *mm);
bool rusix_mm_release_list_empty(struct mm_struct *mm);
void rusix_mm_release_list_lock(void);
void rusix_mm_release_list_del(struct mm_struct *mm);
void rusix_mm_release_list_unlock(void);
bool rusix_mm_release_has_binfmt(struct mm_struct *mm);
void rusix_mm_release_binfmt_put(struct mm_struct *mm);
void rusix_mm_release_lru(struct mm_struct *mm);
void rusix_mm_release_count_drop(struct mm_struct *mm);
void rusix_mm_release_work_init(struct mm_struct *mm, work_func_t callback);
void rusix_mm_release_work_queue(struct mm_struct *mm);
struct mm_struct *rusix_mm_release_work_mm(struct work_struct *work);
void rusix_mm_release_init_check(struct mm_struct *mm);
void rusix_mm_release_current_check(struct mm_struct *mm);
void rusix_mm_release_lazy_tlbs(struct mm_struct *mm);
void rusix_mm_release_active_check(struct mm_struct *mm);
void rusix_mm_release_notifiers(struct mm_struct *mm);
void rusix_mm_release_check(struct mm_struct *mm);
void rusix_mm_release_user_ns(struct mm_struct *mm);
void rusix_mm_release_pasid(struct mm_struct *mm);
void rusix_mm_release_rss(struct mm_struct *mm);

void rusix_mm_release_might_sleep(void) { might_sleep(); }
bool rusix_mm_release_users_dec(struct mm_struct *mm)
{
	return atomic_dec_and_test(&mm->mm_users);
}
void rusix_mm_release_users_check(struct mm_struct *mm)
{
	VM_BUG_ON(atomic_read(&mm->mm_users));
}
void rusix_mm_release_uprobes(struct mm_struct *mm) { uprobe_clear_state(mm); }
void rusix_mm_release_aio(struct mm_struct *mm) { exit_aio(mm); }
void rusix_mm_release_ksm(struct mm_struct *mm) { ksm_exit(mm); }
void rusix_mm_release_khugepaged(struct mm_struct *mm) { khugepaged_exit(mm); }
void rusix_mm_release_mappings(struct mm_struct *mm) { exit_mmap(mm); }
void rusix_mm_release_huge_zero(struct mm_struct *mm) { mm_put_huge_zero_folio(mm); }
void rusix_mm_release_exe(struct mm_struct *mm) { set_mm_exe_file(mm, NULL); }
bool rusix_mm_release_list_empty(struct mm_struct *mm)
{
	return list_empty(&mm->mmlist);
}
void rusix_mm_release_list_lock(void) { spin_lock(&mmlist_lock); }
void rusix_mm_release_list_del(struct mm_struct *mm) { list_del(&mm->mmlist); }
void rusix_mm_release_list_unlock(void) { spin_unlock(&mmlist_lock); }
bool rusix_mm_release_has_binfmt(struct mm_struct *mm) { return mm->binfmt; }
void rusix_mm_release_binfmt_put(struct mm_struct *mm)
{
	module_put(mm->binfmt->module);
}
void rusix_mm_release_lru(struct mm_struct *mm) { lru_gen_del_mm(mm); }
void rusix_mm_release_count_drop(struct mm_struct *mm) { mmdrop(mm); }
void rusix_mm_release_work_init(struct mm_struct *mm, work_func_t callback)
{
	INIT_WORK(&mm->async_put_work, callback);
}
void rusix_mm_release_work_queue(struct mm_struct *mm)
{
	schedule_work(&mm->async_put_work);
}
struct mm_struct *rusix_mm_release_work_mm(struct work_struct *work)
{
	return container_of(work, struct mm_struct, async_put_work);
}
void rusix_mm_release_init_check(struct mm_struct *mm) { BUG_ON(mm == &init_mm); }
void rusix_mm_release_current_check(struct mm_struct *mm)
{
	WARN_ON_ONCE(mm == current->mm);
}
void rusix_mm_release_lazy_tlbs(struct mm_struct *mm) { cleanup_lazy_tlbs(mm); }
void rusix_mm_release_active_check(struct mm_struct *mm)
{
	WARN_ON_ONCE(mm == current->active_mm);
}
void rusix_mm_release_notifiers(struct mm_struct *mm)
{
	mmu_notifier_subscriptions_destroy(mm);
}
void rusix_mm_release_check(struct mm_struct *mm) { check_mm(mm); }
void rusix_mm_release_user_ns(struct mm_struct *mm) { put_user_ns(mm->user_ns); }
void rusix_mm_release_pasid(struct mm_struct *mm) { mm_pasid_drop(mm); }
void rusix_mm_release_rss(struct mm_struct *mm)
{
	percpu_counter_destroy_many(mm->rss_stat, NR_MM_COUNTERS);
}
#endif
