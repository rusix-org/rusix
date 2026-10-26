/* SPDX-License-Identifier: GPL-2.0-only */
/* Canonical primitives from kernel/fork.c, Copyright (C) 1991, 1992 Linus Torvalds.
 * Included only by fork.c after its private mm initializer declarations.
 * Partial copied fields are NOT owned merely because their bytes were copied.
 */
#ifndef RUSIX_MM_CONSTRUCTION_IMPL_H
#define RUSIX_MM_CONSTRUCTION_IMPL_H

/* Private built-in ABI; no new module exports. */
struct mm_struct *rusix_mm_slab_alloc(void);
struct task_struct *rusix_mm_current_task(void);
struct user_namespace *rusix_mm_current_user_ns(void);
struct mm_struct *rusix_mm_current_mm(void);
void rusix_mm_owner_init(struct mm_struct *mm, struct task_struct *p);
unsigned long rusix_mm_flags_read(struct mm_struct *mm);
unsigned long rusix_mm_def_read(struct mm_struct *mm);
unsigned long rusix_mm_dump_filter(void);
void rusix_mm_flags_write(struct mm_struct *mm, unsigned long value);
void rusix_mm_def_write(struct mm_struct *mm, unsigned long value);
int rusix_mm_futex_init(struct mm_struct *mm);
int rusix_mm_pgd_alloc(struct mm_struct *mm);
int rusix_mm_id_alloc(struct mm_struct *mm);
int rusix_mm_context_init(struct task_struct *p, struct mm_struct *mm);
int rusix_mm_cid_alloc(struct mm_struct *mm, struct task_struct *p);
int rusix_mm_rss_init(struct mm_struct *mm);
void rusix_mm_user_ns_get(struct mm_struct *mm, struct user_namespace *user_ns);
void rusix_mm_tree_init(struct mm_struct *mm);
void rusix_mm_refs_init(struct mm_struct *mm);
void rusix_mm_write_seq_init(struct mm_struct *mm);
void rusix_mm_mmap_lock_init(struct mm_struct *mm);
void rusix_mm_mmlist_init(struct mm_struct *mm);
void rusix_mm_pgtables_init(struct mm_struct *mm);
void rusix_mm_counts_init(struct mm_struct *mm);
void rusix_mm_rss_clear(struct mm_struct *mm);
void rusix_mm_page_table_lock_init(struct mm_struct *mm);
void rusix_mm_arg_lock_init(struct mm_struct *mm);
void rusix_mm_cpumask_init(struct mm_struct *mm);
void rusix_mm_aio_init(struct mm_struct *mm);
void rusix_mm_pasid_init(struct mm_struct *mm);
void rusix_mm_exe_clear(struct mm_struct *mm);
void rusix_mm_notifiers_init(struct mm_struct *mm);
void rusix_mm_tlb_pending_init(struct mm_struct *mm);
void rusix_mm_huge_pmd_clear(struct mm_struct *mm);
void rusix_mm_uprobes_init(struct mm_struct *mm);
void rusix_mm_hugetlb_init(struct mm_struct *mm);
void rusix_mm_flags_clear(struct mm_struct *mm);
void rusix_mm_lru_init(struct mm_struct *mm);
void rusix_mm_cid_destroy(struct mm_struct *mm);
void rusix_mm_context_destroy(struct mm_struct *mm);
void rusix_mm_id_free(struct mm_struct *mm);
void rusix_mm_pgd_free(struct mm_struct *mm);
void rusix_mm_futex_free(struct mm_struct *mm);
void rusix_mm_slab_free(struct mm_struct *mm);
void rusix_mm_zero_fresh(struct mm_struct *mm);

const unsigned long rusix_mm_mdwe_no_inherit = 1UL << MMF_HAS_MDWE_NO_INHERIT;
const unsigned long rusix_mm_mdwe_clear = (1UL << MMF_HAS_MDWE) |
					(1UL << MMF_HAS_MDWE_NO_INHERIT);
const unsigned long rusix_mm_legacy_mask = MMF_INIT_LEGACY_MASK;
const unsigned long rusix_mm_def_mask = VM_INIT_DEF_MASK;

struct mm_struct *rusix_mm_slab_alloc(void) { return allocate_mm(); }
struct task_struct *rusix_mm_current_task(void) { return current; }
struct user_namespace *rusix_mm_current_user_ns(void) { return current_user_ns(); }
struct mm_struct *rusix_mm_current_mm(void) { return current->mm; }
void rusix_mm_owner_init(struct mm_struct *mm, struct task_struct *p) { mm_init_owner(mm, p); }
unsigned long rusix_mm_flags_read(struct mm_struct *mm) { return __mm_flags_get_word(mm); }
unsigned long rusix_mm_def_read(struct mm_struct *mm) { return mm->def_flags; }
unsigned long rusix_mm_dump_filter(void) { return default_dump_filter; }
void rusix_mm_flags_write(struct mm_struct *mm, unsigned long value) { __mm_flags_set_word(mm, value); }
void rusix_mm_def_write(struct mm_struct *mm, unsigned long value) { mm->def_flags = value; }
int rusix_mm_futex_init(struct mm_struct *mm) { return futex_mm_init(mm); }
int rusix_mm_pgd_alloc(struct mm_struct *mm) { return mm_alloc_pgd(mm); }
int rusix_mm_id_alloc(struct mm_struct *mm) { return mm_alloc_id(mm); }
int rusix_mm_context_init(struct task_struct *p, struct mm_struct *mm) { return init_new_context(p, mm); }
int rusix_mm_cid_alloc(struct mm_struct *mm, struct task_struct *p) { return mm_alloc_cid(mm, p); }
int rusix_mm_rss_init(struct mm_struct *mm)
{
	return percpu_counter_init_many(mm->rss_stat, 0, GFP_KERNEL_ACCOUNT,
				       NR_MM_COUNTERS);
}
void rusix_mm_user_ns_get(struct mm_struct *mm, struct user_namespace *user_ns)
{
	mm->user_ns = get_user_ns(user_ns);
}

void rusix_mm_tree_init(struct mm_struct *mm)
{
	mt_init_flags(&mm->mm_mt, MM_MT_FLAGS);
	mt_set_external_lock(&mm->mm_mt, &mm->mmap_lock);
}

void rusix_mm_refs_init(struct mm_struct *mm)
{
	atomic_set(&mm->mm_users, 1);
	atomic_set(&mm->mm_count, 1);
}

void rusix_mm_write_seq_init(struct mm_struct *mm)
{
	seqcount_init(&mm->write_protect_seq);
}

void rusix_mm_mmap_lock_init(struct mm_struct *mm)
{
	mmap_init_lock(mm);
}

void rusix_mm_mmlist_init(struct mm_struct *mm)
{
	INIT_LIST_HEAD(&mm->mmlist);
}

void rusix_mm_pgtables_init(struct mm_struct *mm)
{
	mm_pgtables_bytes_init(mm);
}

void rusix_mm_counts_init(struct mm_struct *mm)
{
	mm->map_count = 0;
	mm->locked_vm = 0;
	atomic64_set(&mm->pinned_vm, 0);
}

void rusix_mm_rss_clear(struct mm_struct *mm)
{
	memset(&mm->rss_stat, 0, sizeof(mm->rss_stat));
}

void rusix_mm_page_table_lock_init(struct mm_struct *mm)
{
	spin_lock_init(&mm->page_table_lock);
}

void rusix_mm_arg_lock_init(struct mm_struct *mm)
{
	spin_lock_init(&mm->arg_lock);
}

void rusix_mm_cpumask_init(struct mm_struct *mm)
{
	mm_init_cpumask(mm);
}

void rusix_mm_aio_init(struct mm_struct *mm)
{
	mm_init_aio(mm);
}

void rusix_mm_pasid_init(struct mm_struct *mm)
{
	mm_pasid_init(mm);
}

void rusix_mm_exe_clear(struct mm_struct *mm)
{
	RCU_INIT_POINTER(mm->exe_file, NULL);
}

void rusix_mm_notifiers_init(struct mm_struct *mm)
{
	mmu_notifier_subscriptions_init(mm);
}

void rusix_mm_tlb_pending_init(struct mm_struct *mm)
{
	init_tlb_flush_pending(mm);
}

void rusix_mm_huge_pmd_clear(struct mm_struct *mm)
{
#if defined(CONFIG_TRANSPARENT_HUGEPAGE) && !defined(CONFIG_SPLIT_PMD_PTLOCKS)
	mm->pmd_huge_pte = NULL;
#endif
}

void rusix_mm_uprobes_init(struct mm_struct *mm)
{
	mm_init_uprobes_state(mm);
}

void rusix_mm_hugetlb_init(struct mm_struct *mm)
{
	hugetlb_count_init(mm);
}

void rusix_mm_flags_clear(struct mm_struct *mm)
{
	mm_flags_clear_all(mm);
}

void rusix_mm_lru_init(struct mm_struct *mm)
{
	lru_gen_init_mm(mm);
}

void rusix_mm_cid_destroy(struct mm_struct *mm)
{
	mm_destroy_cid(mm);
}

void rusix_mm_context_destroy(struct mm_struct *mm)
{
	destroy_context(mm);
}

void rusix_mm_id_free(struct mm_struct *mm)
{
	mm_free_id(mm);
}

void rusix_mm_pgd_free(struct mm_struct *mm)
{
	mm_free_pgd(mm);
}

void rusix_mm_futex_free(struct mm_struct *mm)
{
	futex_hash_free(mm);
}

void rusix_mm_slab_free(struct mm_struct *mm)
{
	free_mm(mm);
}

void rusix_mm_zero_fresh(struct mm_struct *mm)
{
	memset(mm, 0, sizeof(*mm));
}

#endif
