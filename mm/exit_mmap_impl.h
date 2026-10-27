/* SPDX-License-Identifier: GPL-2.0-only */
/* Canonical primitives from mm/mmap.c, written by obz; address-space
 * accounting attribution <alan@lxorguk.ukuu.org.uk>. Included only by mmap.c.
 * The synchronous entry owns final-address iterator and gather storage.
 * Gather storage is uninitialized until Rust selects the nonempty path.
 */
#ifndef RUSIX_EXIT_MMAP_IMPL_H
#define RUSIX_EXIT_MMAP_IMPL_H
struct rusix_exit_context {
	struct vma_iterator *vmi;
	struct mmu_gather *tlb;
};
extern const unsigned long rusix_exit_account;
void rusix_exit_notifier(struct mm_struct *mm);
void rusix_exit_read_lock(struct mm_struct *mm);
void rusix_exit_arch(struct mm_struct *mm);
struct vm_area_struct * rusix_exit_next(struct rusix_exit_context *ctx);
bool rusix_exit_is_zero(struct vm_area_struct *vma);
void rusix_exit_read_unlock(struct mm_struct *mm);
void rusix_exit_write_lock(struct mm_struct *mm);
void rusix_exit_cache(struct mm_struct *mm);
void rusix_exit_gather(struct rusix_exit_context *ctx, struct mm_struct *mm);
void rusix_exit_unmap(struct rusix_exit_context *ctx, struct vm_area_struct *vma);
void rusix_exit_oom_skip(struct mm_struct *mm);
void rusix_exit_clear_rcu(struct mm_struct *mm);
unsigned long rusix_exit_end(struct vm_area_struct *vma);
void rusix_exit_iter_set(struct rusix_exit_context *ctx, unsigned long end);
void rusix_exit_free_pgtables(struct rusix_exit_context *ctx, struct vm_area_struct *vma);
void rusix_exit_finish(struct rusix_exit_context *ctx);
unsigned long rusix_exit_flags(struct vm_area_struct *vma);
unsigned long rusix_exit_pages(struct vm_area_struct *vma);
void rusix_exit_detach(struct vm_area_struct *vma);
void rusix_exit_resched(void);
int rusix_exit_map_count(struct mm_struct *mm);
void rusix_exit_count_bug(bool mismatch);
void rusix_exit_trace(struct mm_struct *mm);
void rusix_exit_destroy(struct mm_struct *mm);
void rusix_exit_write_unlock(struct mm_struct *mm);
void rusix_exit_unaccount(unsigned long pages);

const unsigned long rusix_exit_account = VM_ACCOUNT;

void rusix_exit_notifier(struct mm_struct *mm)
{
	mmu_notifier_release(mm);
}

void rusix_exit_read_lock(struct mm_struct *mm)
{
	mmap_read_lock(mm);
}

void rusix_exit_arch(struct mm_struct *mm)
{
	arch_exit_mmap(mm);
}

struct vm_area_struct * rusix_exit_next(struct rusix_exit_context *ctx)
{
	return vma_next(ctx->vmi);
}

bool rusix_exit_is_zero(struct vm_area_struct *vma)
{
	return xa_is_zero(vma);
}

void rusix_exit_read_unlock(struct mm_struct *mm)
{
	mmap_read_unlock(mm);
}

void rusix_exit_write_lock(struct mm_struct *mm)
{
	mmap_write_lock(mm);
}

void rusix_exit_cache(struct mm_struct *mm)
{
	flush_cache_mm(mm);
}

void rusix_exit_gather(struct rusix_exit_context *ctx, struct mm_struct *mm)
{
	tlb_gather_mmu_fullmm(ctx->tlb, mm);
}

void rusix_exit_unmap(struct rusix_exit_context *ctx, struct vm_area_struct *vma)
{
	unmap_vmas(ctx->tlb, &ctx->vmi->mas, vma, 0, ULONG_MAX, ULONG_MAX, false);
}

void rusix_exit_oom_skip(struct mm_struct *mm)
{
	mm_flags_set(MMF_OOM_SKIP, mm);
}

void rusix_exit_clear_rcu(struct mm_struct *mm)
{
	mt_clear_in_rcu(&mm->mm_mt);
}

unsigned long rusix_exit_end(struct vm_area_struct *vma)
{
	return vma->vm_end;
}

void rusix_exit_iter_set(struct rusix_exit_context *ctx, unsigned long end)
{
	vma_iter_set(ctx->vmi, end);
}

void rusix_exit_free_pgtables(struct rusix_exit_context *ctx, struct vm_area_struct *vma)
{
	free_pgtables(ctx->tlb, &ctx->vmi->mas, vma, FIRST_USER_ADDRESS,
		      USER_PGTABLES_CEILING, true);
}

void rusix_exit_finish(struct rusix_exit_context *ctx)
{
	tlb_finish_mmu(ctx->tlb);
}

unsigned long rusix_exit_flags(struct vm_area_struct *vma)
{
	return vma->vm_flags;
}

unsigned long rusix_exit_pages(struct vm_area_struct *vma)
{
	return vma_pages(vma);
}

void rusix_exit_detach(struct vm_area_struct *vma)
{
	vma_mark_detached(vma);
}

void rusix_exit_resched(void)
{
	cond_resched();
}

int rusix_exit_map_count(struct mm_struct *mm)
{
	return mm->map_count;
}

void rusix_exit_count_bug(bool mismatch)
{
	BUG_ON(mismatch);
}

void rusix_exit_trace(struct mm_struct *mm)
{
	trace_exit_mmap(mm);
}

void rusix_exit_destroy(struct mm_struct *mm)
{
	__mt_destroy(&mm->mm_mt);
}

void rusix_exit_write_unlock(struct mm_struct *mm)
{
	mmap_write_unlock(mm);
}

void rusix_exit_unaccount(unsigned long pages)
{
	vm_unacct_memory(pages);
}

#endif /* RUSIX_EXIT_MMAP_IMPL_H */
