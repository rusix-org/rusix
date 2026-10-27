/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Included after the private native definitions in vma.c. Each accessor operates
 *on canonical C storage. Transactions and cleanup decisions live in Rust.
 */
struct vm_area_struct *rusix_prep_vma(void *opaque)
{
	return ((struct vma_prepare *)opaque)->vma;
}

void rusix_prep_set_vma(void *opaque, struct vm_area_struct *value)
{
	((struct vma_prepare *)opaque)->vma = value;
}

struct vm_area_struct *rusix_prep_adj_next(void *opaque)
{
	return ((struct vma_prepare *)opaque)->adj_next;
}

void rusix_prep_set_adj_next(void *opaque, struct vm_area_struct *value)
{
	((struct vma_prepare *)opaque)->adj_next = value;
}

struct file *rusix_prep_file(void *opaque)
{
	return ((struct vma_prepare *)opaque)->file;
}

void rusix_prep_set_file(void *opaque, struct file *value)
{
	((struct vma_prepare *)opaque)->file = value;
}

struct address_space *rusix_prep_mapping(void *opaque)
{
	return ((struct vma_prepare *)opaque)->mapping;
}

void rusix_prep_set_mapping(void *opaque, struct address_space *value)
{
	((struct vma_prepare *)opaque)->mapping = value;
}

struct anon_vma *rusix_prep_anon_vma(void *opaque)
{
	return ((struct vma_prepare *)opaque)->anon_vma;
}

void rusix_prep_set_anon_vma(void *opaque, struct anon_vma *value)
{
	((struct vma_prepare *)opaque)->anon_vma = value;
}

struct vm_area_struct *rusix_prep_insert(void *opaque)
{
	return ((struct vma_prepare *)opaque)->insert;
}

void rusix_prep_set_insert(void *opaque, struct vm_area_struct *value)
{
	((struct vma_prepare *)opaque)->insert = value;
}

struct vm_area_struct *rusix_prep_remove(void *opaque)
{
	return ((struct vma_prepare *)opaque)->remove;
}

void rusix_prep_set_remove(void *opaque, struct vm_area_struct *value)
{
	((struct vma_prepare *)opaque)->remove = value;
}

struct vm_area_struct *rusix_prep_remove2(void *opaque)
{
	return ((struct vma_prepare *)opaque)->remove2;
}

void rusix_prep_set_remove2(void *opaque, struct vm_area_struct *value)
{
	((struct vma_prepare *)opaque)->remove2 = value;
}

bool rusix_prep_skip_vma_uprobe(void *opaque)
{
	return ((struct vma_prepare *)opaque)->skip_vma_uprobe;
}

void rusix_prep_set_skip_vma_uprobe(void *opaque, bool value)
{
	((struct vma_prepare *)opaque)->skip_vma_uprobe = value;
}

void rusix_prep_zero(void *opaque)
{
	memset(opaque, 0, sizeof(struct vma_prepare));
}

struct vm_area_struct *rusix_modify_middle(void *opaque)
{
	return ((struct vma_merge_struct *)opaque)->middle;
}

struct vm_area_struct *rusix_modify_next(void *opaque)
{
	return ((struct vma_merge_struct *)opaque)->next;
}

bool rusix_modify_remove_middle(void *opaque)
{
	return ((struct vma_merge_struct *)opaque)->__remove_middle;
}

bool rusix_modify_remove_next(void *opaque)
{
	return ((struct vma_merge_struct *)opaque)->__remove_next;
}

bool rusix_modify_adjust_middle_start(void *opaque)
{
	return ((struct vma_merge_struct *)opaque)->__adjust_middle_start;
}

bool rusix_modify_adjust_next_start(void *opaque)
{
	return ((struct vma_merge_struct *)opaque)->__adjust_next_start;
}

bool rusix_modify_skip_vma_uprobe(void *opaque)
{
	return ((struct vma_merge_struct *)opaque)->skip_vma_uprobe;
}

bool rusix_modify_give_up_on_oom(void *opaque)
{
	return ((struct vma_merge_struct *)opaque)->give_up_on_oom;
}

unsigned long rusix_modify_start(void *opaque)
{
	return ((struct vma_merge_struct *)opaque)->start;
}

unsigned long rusix_modify_end(void *opaque)
{
	return ((struct vma_merge_struct *)opaque)->end;
}

void *rusix_modify_vmi(void *opaque)
{
	return ((struct vma_merge_struct *)opaque)->vmi;
}

void rusix_modify_set_vm_flags(void *opaque, vm_flags_t value)
{
	((struct vma_merge_struct *)opaque)->vm_flags = value;
}

void rusix_modify_set_anon_name(void *opaque, struct anon_vma_name *value)
{
	((struct vma_merge_struct *)opaque)->anon_name = value;
}

void rusix_modify_set_policy(void *opaque, struct mempolicy *value)
{
	((struct vma_merge_struct *)opaque)->policy = value;
}

void rusix_modify_set_give_up_on_oom(void *opaque, bool value)
{
	((struct vma_merge_struct *)opaque)->give_up_on_oom = value;
}

void rusix_modify_set_uffd(void *opaque, const void *context)
{
	((struct vma_merge_struct *)opaque)->uffd_ctx = *(const struct vm_userfaultfd_ctx *)context;
}

bool rusix_modify_nomem(void *opaque)
{
	return vmg_nomem(opaque);
}

bool rusix_modify_merged(void *opaque)
{
	return ((struct vma_merge_struct *)opaque)->state == VMA_MERGE_SUCCESS;
}

struct vm_area_struct *rusix_modify_merge(void *opaque)
{
	return vma_merge_existing_range(opaque);
}

struct vm_area_struct *rusix_modify_error(int error)
{
	return ERR_PTR(error);
}

bool rusix_modify_is_error(struct vm_area_struct *vma)
{
	return IS_ERR(vma);
}

struct mm_struct *rusix_modify_mm(struct vm_area_struct *vma)
{
	return vma->vm_mm;
}

vm_flags_t rusix_modify_flags(struct vm_area_struct *vma)
{
	return vma->vm_flags;
}

void rusix_modify_set_start(struct vm_area_struct *vma, unsigned long value)
{
	vma->vm_start = value;
}

void rusix_modify_set_end(struct vm_area_struct *vma, unsigned long value)
{
	vma->vm_end = value;
}

void rusix_modify_set_pgoff(struct vm_area_struct *vma, pgoff_t value)
{
	vma->vm_pgoff = value;
}

int rusix_modify_max_map_count(void)
{
	return sysctl_max_map_count;
}

rusix_may_split_fn rusix_modify_may_split(const struct vm_operations_struct *ops)
{
	return ops->may_split;
}

int rusix_modify_split(void *iter, struct vm_area_struct *vma, unsigned long addr, int new_below)
{
	return __split_vma(iter, vma, addr, new_below);
}

void rusix_modify_iter_free(void *iter)
{
	vma_iter_free(iter);
}

void rusix_modify_iter_next(void *iter)
{
	vma_next(iter);
}

void rusix_modify_prev(void *iter)
{
	vma_prev(iter);
}

void rusix_modify_adjust_huge(struct vm_area_struct *vma, unsigned long start, unsigned long end)
{
	vma_adjust_trans_huge(vma, start, end, NULL);
}

bool rusix_modify_is_hugetlb(struct vm_area_struct *vma)
{
	return is_vm_hugetlb_page(vma);
}

void rusix_modify_hugetlb_split(struct vm_area_struct *vma, unsigned long addr)
{
	hugetlb_split(vma, addr);
}

void rusix_modify_uprobe_unmap(struct vm_area_struct *vma, unsigned long start, unsigned long end)
{
	uprobe_munmap(vma, start, end);
}

void rusix_modify_uprobe_map(struct vm_area_struct *vma)
{
	uprobe_mmap(vma);
}

void rusix_modify_anon_lock(struct anon_vma *anon)
{
	anon_vma_lock_write(anon);
}

void rusix_modify_anon_unlock(struct anon_vma *anon)
{
	anon_vma_unlock_write(anon);
}

void rusix_modify_anon_pre(struct vm_area_struct *vma)
{
	anon_vma_interval_tree_pre_update_vma(vma);
}

void rusix_modify_anon_post(struct vm_area_struct *vma)
{
	anon_vma_interval_tree_post_update_vma(vma);
}

void rusix_modify_interval_remove(struct vm_area_struct *vma, struct address_space *mapping)
{
	vma_interval_tree_remove(vma, &mapping->i_mmap);
}

void rusix_modify_unmap_writable(struct address_space *mapping)
{
	mapping_unmap_writable(mapping);
}

void rusix_modify_store_new(void *iter, struct vm_area_struct *vma)
{
	vma_iter_store_new(iter, vma);
}

void rusix_modify_detach(struct vm_area_struct *vma)
{
	vma_mark_detached(vma);
}

void rusix_modify_anon_merge(struct vm_area_struct *vma, struct vm_area_struct *remove)
{
	anon_vma_merge(vma, remove);
}

void rusix_modify_warn_start(bool condition)
{
	WARN_ON(condition);
}

void rusix_modify_warn_end(bool condition)
{
	WARN_ON(condition);
}

void rusix_modify_warn_anon(bool condition)
{
	VM_WARN_ON(condition);
}

void rusix_modify_warn_oom(bool condition)
{
	VM_WARN_ON(condition);
}

void rusix_modify_warn_removed_end(bool condition)
{
	WARN_ON_ONCE(condition);
}
