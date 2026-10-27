/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Native operations for mm/vma.c copy/link policy. Included in vma.c after
 * the private merge engine; no iterator or VMA layout is reproduced in Rust.
 */
#ifndef RUSIX_COPY_VMA_IMPL_H
#define RUSIX_COPY_VMA_IMPL_H
struct rusix_copy_vma_context {
	struct vma_iterator *vmi;
	struct vma_merge_struct *vmg;
	struct vm_area_struct *source;
	struct mm_struct *mm;
	unsigned long source_start;
};
typedef void (*rusix_vma_open_fn)(struct vm_area_struct *vma);
extern int rusix_vma_link(struct mm_struct *mm, struct vm_area_struct *vma,
			 void *iter);
extern struct vm_area_struct *rusix_copy_vma(void *ctx,
	struct vm_area_struct **vmap, unsigned long addr, unsigned long len,
	pgoff_t pgoff, bool *need_rmap_locks, bool keep_source);
extern const unsigned int rusix_copy_page_shift;
extern const int rusix_copy_enomem;
const unsigned int rusix_copy_page_shift = PAGE_SHIFT;
const int rusix_copy_enomem = -ENOMEM;
struct vm_area_struct *rusix_copy_source(void *opaque);
struct mm_struct *rusix_copy_mm(void *opaque);
unsigned long rusix_copy_source_start(void *opaque);
unsigned long rusix_copy_start(struct vm_area_struct *vma);
unsigned long rusix_copy_end(struct vm_area_struct *vma);
pgoff_t rusix_copy_pgoff(struct vm_area_struct *vma);
bool rusix_copy_anonymous(struct vm_area_struct *vma);
struct anon_vma *rusix_copy_anon(struct vm_area_struct *vma);
void rusix_copy_skip_uprobe(void *opaque);
struct vm_area_struct *rusix_copy_find_prev(void *opaque, unsigned long addr);
void rusix_copy_set_pgoff(void *opaque, pgoff_t pgoff);
struct vm_area_struct *rusix_copy_next_rewind(void *opaque);
void rusix_copy_set_next(void *opaque, struct vm_area_struct *vma);
void rusix_copy_set_prev(void *opaque, struct vm_area_struct *vma);
struct vm_area_struct *rusix_copy_prev(void *opaque);
struct vm_area_struct *rusix_copy_next(void *opaque);
struct vm_area_struct *rusix_copy_merge(void *opaque);
void rusix_copy_merge_bug(bool faulted, struct vm_area_struct *vma);
void rusix_copy_set_range(struct vm_area_struct *vma, unsigned long start, unsigned long end, pgoff_t pgoff);
int rusix_copy_dup_policy(struct vm_area_struct *old, struct vm_area_struct *new);
int rusix_copy_clone_anon(struct vm_area_struct *new, struct vm_area_struct *old);
void rusix_copy_get_file(struct file *file);
rusix_vma_open_fn rusix_copy_open(const struct vm_operations_struct *ops);
void rusix_copy_fixup_huge(struct vm_area_struct *vma);
void rusix_copy_unlink_anon(struct vm_area_struct *vma);
void rusix_link_config(void *iter, unsigned long start, unsigned long end);
int rusix_link_prealloc(void *iter, struct vm_area_struct *vma);
void rusix_link_start_write(struct vm_area_struct *vma);
void rusix_link_store(void *iter, struct vm_area_struct *vma);
int rusix_link_count(struct mm_struct *mm);
void rusix_link_set_count(struct mm_struct *mm, int count);
void rusix_link_validate(struct mm_struct *mm);
struct address_space *rusix_link_mapping(struct file *file);
void rusix_link_mapping_lock(struct address_space *mapping);
void rusix_link_mapping_unlock(struct address_space *mapping);
bool rusix_link_shared_maywrite(struct vm_area_struct *vma);
void rusix_link_allow_writable(struct address_space *mapping);
void rusix_link_dcache_lock(struct address_space *mapping);
void rusix_link_dcache_unlock(struct address_space *mapping);
void rusix_link_interval_insert(struct vm_area_struct *vma, struct address_space *mapping);

struct vm_area_struct *rusix_copy_source(void *opaque)
{
	return ((struct rusix_copy_vma_context *)opaque)->source;
}

struct mm_struct *rusix_copy_mm(void *opaque)
{
	return ((struct rusix_copy_vma_context *)opaque)->mm;
}

unsigned long rusix_copy_source_start(void *opaque)
{
	return ((struct rusix_copy_vma_context *)opaque)->source_start;
}

unsigned long rusix_copy_start(struct vm_area_struct *vma)
{
	return vma->vm_start;
}

unsigned long rusix_copy_end(struct vm_area_struct *vma)
{
	return vma->vm_end;
}

pgoff_t rusix_copy_pgoff(struct vm_area_struct *vma)
{
	return vma->vm_pgoff;
}

bool rusix_copy_anonymous(struct vm_area_struct *vma)
{
	return vma_is_anonymous(vma);
}

struct anon_vma *rusix_copy_anon(struct vm_area_struct *vma)
{
	return vma->anon_vma;
}

void rusix_copy_skip_uprobe(void *opaque)
{
	((struct rusix_copy_vma_context *)opaque)->vmg->skip_vma_uprobe = true;
}

struct vm_area_struct *rusix_copy_find_prev(void *opaque, unsigned long addr)
{
	struct rusix_copy_vma_context *ctx = opaque;
	return find_vma_prev(ctx->mm, addr, &ctx->vmg->prev);
}

void rusix_copy_set_pgoff(void *opaque, pgoff_t pgoff)
{
	((struct rusix_copy_vma_context *)opaque)->vmg->pgoff = pgoff;
}

struct vm_area_struct *rusix_copy_next_rewind(void *opaque)
{
	return vma_iter_next_rewind(((struct rusix_copy_vma_context *)opaque)->vmi, NULL);
}

void rusix_copy_set_next(void *opaque, struct vm_area_struct *vma)
{
	((struct rusix_copy_vma_context *)opaque)->vmg->next = vma;
}

void rusix_copy_set_prev(void *opaque, struct vm_area_struct *vma)
{
	((struct rusix_copy_vma_context *)opaque)->vmg->prev = vma;
}

struct vm_area_struct *rusix_copy_prev(void *opaque)
{
	return ((struct rusix_copy_vma_context *)opaque)->vmg->prev;
}

struct vm_area_struct *rusix_copy_next(void *opaque)
{
	return ((struct rusix_copy_vma_context *)opaque)->vmg->next;
}

struct vm_area_struct *rusix_copy_merge(void *opaque)
{
	return vma_merge_copied_range(((struct rusix_copy_vma_context *)opaque)->vmg);
}

void rusix_copy_merge_bug(bool faulted, struct vm_area_struct *vma)
{
	VM_BUG_ON_VMA(faulted, vma);
}

void rusix_copy_set_range(struct vm_area_struct *vma, unsigned long start, unsigned long end, pgoff_t pgoff)
{
	vma_set_range(vma, start, end, pgoff);
}

int rusix_copy_dup_policy(struct vm_area_struct *old, struct vm_area_struct *new)
{
	return vma_dup_policy(old, new);
}

int rusix_copy_clone_anon(struct vm_area_struct *new, struct vm_area_struct *old)
{
	return anon_vma_clone(new, old);
}

void rusix_copy_get_file(struct file *file)
{
	get_file(file);
}

rusix_vma_open_fn rusix_copy_open(const struct vm_operations_struct *ops)
{
	return ops->open;
}

void rusix_copy_fixup_huge(struct vm_area_struct *vma)
{
	fixup_hugetlb_reservations(vma);
}

void rusix_copy_unlink_anon(struct vm_area_struct *vma)
{
	unlink_anon_vmas(vma);
}

void rusix_link_config(void *iter, unsigned long start, unsigned long end)
{
	vma_iter_config(iter, start, end);
}

int rusix_link_prealloc(void *iter, struct vm_area_struct *vma)
{
	return vma_iter_prealloc(iter, vma);
}

void rusix_link_start_write(struct vm_area_struct *vma)
{
	vma_start_write(vma);
}

void rusix_link_store(void *iter, struct vm_area_struct *vma)
{
	vma_iter_store_new(iter, vma);
}

int rusix_link_count(struct mm_struct *mm)
{
	return mm->map_count;
}

void rusix_link_set_count(struct mm_struct *mm, int count)
{
	mm->map_count = count;
}

void rusix_link_validate(struct mm_struct *mm)
{
	validate_mm(mm);
}

struct address_space *rusix_link_mapping(struct file *file)
{
	return file->f_mapping;
}

void rusix_link_mapping_lock(struct address_space *mapping)
{
	i_mmap_lock_write(mapping);
}

void rusix_link_mapping_unlock(struct address_space *mapping)
{
	i_mmap_unlock_write(mapping);
}

bool rusix_link_shared_maywrite(struct vm_area_struct *vma)
{
	return vma_is_shared_maywrite(vma);
}

void rusix_link_allow_writable(struct address_space *mapping)
{
	mapping_allow_writable(mapping);
}

void rusix_link_dcache_lock(struct address_space *mapping)
{
	flush_dcache_mmap_lock(mapping);
}

void rusix_link_dcache_unlock(struct address_space *mapping)
{
	flush_dcache_mmap_unlock(mapping);
}

void rusix_link_interval_insert(struct vm_area_struct *vma, struct address_space *mapping)
{
	vma_interval_tree_insert(vma, &mapping->i_mmap);
}

#endif /* RUSIX_COPY_VMA_IMPL_H */
