/* SPDX-License-Identifier: GPL-2.0-only */
/* Canonical operations from mm/mmap.c: written by obz; address-space
 * accounting attribution <alan@lxorguk.ukuu.org.uk>.
 * Included solely by mmap.c. The synchronous C entry owns this stack context;
 * Rust never reads its layout or lets its pointers escape the call.
 */
#ifndef RUSIX_DUP_MMAP_IMPL_H
#define RUSIX_DUP_MMAP_IMPL_H
struct rusix_dup_mmap_context {
	struct vma_iterator *vmi;
	struct list_head *uf;
};
extern const unsigned long rusix_dup_dontcopy;
extern const unsigned long rusix_dup_account;
extern const unsigned long rusix_dup_wipeonfork;
int rusix_dup_lock_parent(struct mm_struct *mm);
void rusix_dup_cache_parent(struct mm_struct *mm);
void rusix_dup_uprobes(struct mm_struct *oldmm, struct mm_struct *mm);
void rusix_dup_lock_child(struct mm_struct *mm);
void rusix_dup_exe(struct mm_struct *mm, struct mm_struct *oldmm);
void rusix_dup_vm_counters(struct mm_struct *mm, struct mm_struct *oldmm);
int rusix_dup_tree(struct mm_struct *mm, struct mm_struct *oldmm);
void rusix_dup_rcu_clear(struct rusix_dup_mmap_context *ctx);
void rusix_dup_rcu_set(struct rusix_dup_mmap_context *ctx);
struct vm_area_struct * rusix_dup_next(struct rusix_dup_mmap_context *ctx);
void rusix_dup_vma_write(struct vm_area_struct *vma);
unsigned long rusix_dup_flags(struct vm_area_struct *vma);
int rusix_dup_clear_range(struct rusix_dup_mmap_context *ctx, struct vm_area_struct *vma);
void rusix_dup_subtract_stats(struct mm_struct *mm, struct vm_area_struct *vma);
bool rusix_dup_fatal(void);
unsigned long rusix_dup_pages(struct vm_area_struct *vma);
int rusix_dup_charge(struct mm_struct *oldmm, unsigned long len);
struct vm_area_struct * rusix_dup_vma(struct vm_area_struct *vma);
int rusix_dup_policy(struct vm_area_struct *old, struct vm_area_struct *new);
void rusix_dup_vma_mm(struct vm_area_struct *vma, struct mm_struct *mm);
int rusix_dup_userfault(struct rusix_dup_mmap_context *ctx, struct vm_area_struct *vma);
void rusix_dup_anon_clear(struct vm_area_struct *vma);
int rusix_dup_anon(struct vm_area_struct *new, struct vm_area_struct *old);
void rusix_dup_locked_clear(struct vm_area_struct *vma);
bool rusix_dup_is_hugetlb(struct vm_area_struct *vma);
void rusix_dup_hugetlb(struct vm_area_struct *vma);
void rusix_dup_store(struct rusix_dup_mmap_context *ctx, struct vm_area_struct *vma);
void rusix_dup_map_count(struct mm_struct *mm);
bool rusix_dup_has_open(struct vm_area_struct *vma);
void rusix_dup_open(struct vm_area_struct *vma);
struct file * rusix_dup_file(struct vm_area_struct *vma);
struct address_space * rusix_dup_mapping(struct file *file);
void rusix_dup_file_get(struct file *file);
void rusix_dup_mapping_lock(struct address_space *mapping);
bool rusix_dup_shared_write(struct vm_area_struct *vma);
void rusix_dup_mapping_writable(struct address_space *mapping);
void rusix_dup_dcache_lock(struct address_space *mapping);
void rusix_dup_interval_insert(struct vm_area_struct *new, struct vm_area_struct *old, struct address_space *mapping);
void rusix_dup_dcache_unlock(struct address_space *mapping);
void rusix_dup_mapping_unlock(struct address_space *mapping);
int rusix_dup_page_range(struct vm_area_struct *new, struct vm_area_struct *old);
int rusix_dup_arch(struct mm_struct *oldmm, struct mm_struct *mm);
void rusix_dup_iter_free(struct rusix_dup_mmap_context *ctx);
void rusix_dup_ksm(struct mm_struct *mm, struct mm_struct *oldmm);
void rusix_dup_khugepaged(struct mm_struct *mm, struct mm_struct *oldmm);
void rusix_dup_sentinel(struct rusix_dup_mmap_context *ctx, struct vm_area_struct *vma);
void rusix_dup_oom_skip(struct mm_struct *mm);
void rusix_dup_unstable(struct mm_struct *mm);
void rusix_dup_unlock(struct mm_struct *mm);
void rusix_dup_tlb_parent(struct mm_struct *mm);
void rusix_dup_userfault_complete(struct rusix_dup_mmap_context *ctx);
void rusix_dup_userfault_fail(struct rusix_dup_mmap_context *ctx);
void rusix_dup_policy_put(struct vm_area_struct *vma);
void rusix_dup_vma_free(struct vm_area_struct *vma);
void rusix_dup_uncharge(unsigned long charge);
const unsigned long rusix_dup_dontcopy = VM_DONTCOPY;
const unsigned long rusix_dup_account = VM_ACCOUNT;
const unsigned long rusix_dup_wipeonfork = VM_WIPEONFORK;
int rusix_dup_lock_parent(struct mm_struct *mm)
{
	return mmap_write_lock_killable(mm);
}
void rusix_dup_cache_parent(struct mm_struct *mm)
{
	flush_cache_dup_mm(mm);
}
void rusix_dup_uprobes(struct mm_struct *oldmm, struct mm_struct *mm)
{
	uprobe_dup_mmap(oldmm, mm);
}
void rusix_dup_lock_child(struct mm_struct *mm)
{
	mmap_write_lock_nested(mm, SINGLE_DEPTH_NESTING);
}
void rusix_dup_exe(struct mm_struct *mm, struct mm_struct *oldmm)
{
	dup_mm_exe_file(mm, oldmm);
}
void rusix_dup_vm_counters(struct mm_struct *mm, struct mm_struct *oldmm)
{
	mm->total_vm = oldmm->total_vm;
	mm->data_vm = oldmm->data_vm;
	mm->exec_vm = oldmm->exec_vm;
	mm->stack_vm = oldmm->stack_vm;
}
int rusix_dup_tree(struct mm_struct *mm, struct mm_struct *oldmm)
{
	return __mt_dup(&oldmm->mm_mt, &mm->mm_mt, GFP_KERNEL);
}
void rusix_dup_rcu_clear(struct rusix_dup_mmap_context *ctx)
{
	mt_clear_in_rcu(ctx->vmi->mas.tree);
}
void rusix_dup_rcu_set(struct rusix_dup_mmap_context *ctx)
{
	mt_set_in_rcu(ctx->vmi->mas.tree);
}
struct vm_area_struct * rusix_dup_next(struct rusix_dup_mmap_context *ctx)
{
	return vma_next(ctx->vmi);
}
void rusix_dup_vma_write(struct vm_area_struct *vma)
{
	vma_start_write(vma);
}
unsigned long rusix_dup_flags(struct vm_area_struct *vma)
{
	return vma->vm_flags;
}
int rusix_dup_clear_range(struct rusix_dup_mmap_context *ctx, struct vm_area_struct *vma)
{
	return vma_iter_clear_gfp(ctx->vmi, vma->vm_start, vma->vm_end, GFP_KERNEL);
}
void rusix_dup_subtract_stats(struct mm_struct *mm, struct vm_area_struct *vma)
{
	vm_stat_account(mm, vma->vm_flags, -vma_pages(vma));
}
bool rusix_dup_fatal(void)
{
	return fatal_signal_pending(current);
}
unsigned long rusix_dup_pages(struct vm_area_struct *vma)
{
	return vma_pages(vma);
}
int rusix_dup_charge(struct mm_struct *oldmm, unsigned long len)
{
	return security_vm_enough_memory_mm(oldmm, len);
}
struct vm_area_struct * rusix_dup_vma(struct vm_area_struct *vma)
{
	return vm_area_dup(vma);
}
int rusix_dup_policy(struct vm_area_struct *old, struct vm_area_struct *new)
{
	return vma_dup_policy(old, new);
}
void rusix_dup_vma_mm(struct vm_area_struct *vma, struct mm_struct *mm)
{
	vma->vm_mm = mm;
}
int rusix_dup_userfault(struct rusix_dup_mmap_context *ctx, struct vm_area_struct *vma)
{
	return dup_userfaultfd(vma, ctx->uf);
}
void rusix_dup_anon_clear(struct vm_area_struct *vma)
{
	vma->anon_vma = NULL;
}
int rusix_dup_anon(struct vm_area_struct *new, struct vm_area_struct *old)
{
	return anon_vma_fork(new, old);
}
void rusix_dup_locked_clear(struct vm_area_struct *vma)
{
	vm_flags_clear(vma, VM_LOCKED_MASK);
}
bool rusix_dup_is_hugetlb(struct vm_area_struct *vma)
{
	return is_vm_hugetlb_page(vma);
}
void rusix_dup_hugetlb(struct vm_area_struct *vma)
{
	hugetlb_dup_vma_private(vma);
}
void rusix_dup_store(struct rusix_dup_mmap_context *ctx, struct vm_area_struct *vma)
{
	/* __mt_dup preallocated this insertion; pinned policy ignores return. */
	vma_iter_bulk_store(ctx->vmi, vma);
}
void rusix_dup_map_count(struct mm_struct *mm)
{
	mm->map_count++;
}
bool rusix_dup_has_open(struct vm_area_struct *vma)
{
	return vma->vm_ops && vma->vm_ops->open;
}
void rusix_dup_open(struct vm_area_struct *vma)
{
	vma->vm_ops->open(vma);
}
struct file * rusix_dup_file(struct vm_area_struct *vma)
{
	return vma->vm_file;
}
struct address_space * rusix_dup_mapping(struct file *file)
{
	return file->f_mapping;
}
void rusix_dup_file_get(struct file *file)
{
	get_file(file);
}
void rusix_dup_mapping_lock(struct address_space *mapping)
{
	i_mmap_lock_write(mapping);
}
bool rusix_dup_shared_write(struct vm_area_struct *vma)
{
	return vma_is_shared_maywrite(vma);
}
void rusix_dup_mapping_writable(struct address_space *mapping)
{
	mapping_allow_writable(mapping);
}
void rusix_dup_dcache_lock(struct address_space *mapping)
{
	flush_dcache_mmap_lock(mapping);
}
void rusix_dup_interval_insert(struct vm_area_struct *new, struct vm_area_struct *old, struct address_space *mapping)
{
	vma_interval_tree_insert_after(new, old, &mapping->i_mmap);
}
void rusix_dup_dcache_unlock(struct address_space *mapping)
{
	flush_dcache_mmap_unlock(mapping);
}
void rusix_dup_mapping_unlock(struct address_space *mapping)
{
	i_mmap_unlock_write(mapping);
}
int rusix_dup_page_range(struct vm_area_struct *new, struct vm_area_struct *old)
{
	return copy_page_range(new, old);
}
int rusix_dup_arch(struct mm_struct *oldmm, struct mm_struct *mm)
{
	return arch_dup_mmap(oldmm, mm);
}
void rusix_dup_iter_free(struct rusix_dup_mmap_context *ctx)
{
	vma_iter_free(ctx->vmi);
}
void rusix_dup_ksm(struct mm_struct *mm, struct mm_struct *oldmm)
{
	ksm_fork(mm, oldmm);
}
void rusix_dup_khugepaged(struct mm_struct *mm, struct mm_struct *oldmm)
{
	khugepaged_fork(mm, oldmm);
}
void rusix_dup_sentinel(struct rusix_dup_mmap_context *ctx, struct vm_area_struct *vma)
{
	mas_set_range(&ctx->vmi->mas, vma->vm_start, vma->vm_end - 1);
	mas_store(&ctx->vmi->mas, XA_ZERO_ENTRY);
}
void rusix_dup_oom_skip(struct mm_struct *mm)
{
	mm_flags_set(MMF_OOM_SKIP, mm);
}
void rusix_dup_unstable(struct mm_struct *mm)
{
	mm_flags_set(MMF_UNSTABLE, mm);
}
void rusix_dup_unlock(struct mm_struct *mm)
{
	mmap_write_unlock(mm);
}
void rusix_dup_tlb_parent(struct mm_struct *mm)
{
	flush_tlb_mm(mm);
}
void rusix_dup_userfault_complete(struct rusix_dup_mmap_context *ctx)
{
	dup_userfaultfd_complete(ctx->uf);
}
void rusix_dup_userfault_fail(struct rusix_dup_mmap_context *ctx)
{
	dup_userfaultfd_fail(ctx->uf);
}
void rusix_dup_policy_put(struct vm_area_struct *vma)
{
	mpol_put(vma_policy(vma));
}
void rusix_dup_vma_free(struct vm_area_struct *vma)
{
	vm_area_free(vma);
}
void rusix_dup_uncharge(unsigned long charge)
{
	vm_unacct_memory(charge);
}
#endif
