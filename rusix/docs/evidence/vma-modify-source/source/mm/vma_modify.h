/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Private pointer/scalar ABI. Canonical VMA/iterator/merge/preparation storage
 *remains at its native final address; Rust owns the selected policy.
 */
#ifndef RUSIX_VMA_MODIFY_H
#define RUSIX_VMA_MODIFY_H
typedef int (*rusix_may_split_fn)(struct vm_area_struct *, unsigned long);
void rusix_init_multi_vma_prep(void *prep, struct vm_area_struct *vma, void *merge);
void rusix_init_vma_prep(void *prep, struct vm_area_struct *vma);
void rusix_vma_prepare(void *prep);
void rusix_vma_complete(void *prep, void *iter, struct mm_struct *mm);
int rusix_split_vma_inner(void *iter, struct vm_area_struct *vma, unsigned long addr,
		int new_below, void *prep);
struct vm_area_struct *rusix_vma_modify_flags(void *merge, vm_flags_t *flags);
struct vm_area_struct *rusix_vma_modify_name(void *merge, struct anon_vma_name *name);
struct vm_area_struct *rusix_vma_modify_policy(void *merge, struct mempolicy *policy);
struct vm_area_struct *rusix_vma_modify_flags_uffd(void *merge, vm_flags_t flags,
		const void *context, bool give_up_on_oom);
struct vm_area_struct *rusix_prep_vma(void *opaque);
void rusix_prep_set_vma(void *opaque, struct vm_area_struct *value);
struct vm_area_struct *rusix_prep_adj_next(void *opaque);
void rusix_prep_set_adj_next(void *opaque, struct vm_area_struct *value);
struct file *rusix_prep_file(void *opaque);
void rusix_prep_set_file(void *opaque, struct file *value);
struct address_space *rusix_prep_mapping(void *opaque);
void rusix_prep_set_mapping(void *opaque, struct address_space *value);
struct anon_vma *rusix_prep_anon_vma(void *opaque);
void rusix_prep_set_anon_vma(void *opaque, struct anon_vma *value);
struct vm_area_struct *rusix_prep_insert(void *opaque);
void rusix_prep_set_insert(void *opaque, struct vm_area_struct *value);
struct vm_area_struct *rusix_prep_remove(void *opaque);
void rusix_prep_set_remove(void *opaque, struct vm_area_struct *value);
struct vm_area_struct *rusix_prep_remove2(void *opaque);
void rusix_prep_set_remove2(void *opaque, struct vm_area_struct *value);
bool rusix_prep_skip_vma_uprobe(void *opaque);
void rusix_prep_set_skip_vma_uprobe(void *opaque, bool value);
void rusix_prep_zero(void *opaque);
struct vm_area_struct *rusix_modify_middle(void *opaque);
struct vm_area_struct *rusix_modify_next(void *opaque);
bool rusix_modify_remove_middle(void *opaque);
bool rusix_modify_remove_next(void *opaque);
bool rusix_modify_adjust_middle_start(void *opaque);
bool rusix_modify_adjust_next_start(void *opaque);
bool rusix_modify_skip_vma_uprobe(void *opaque);
bool rusix_modify_give_up_on_oom(void *opaque);
unsigned long rusix_modify_start(void *opaque);
unsigned long rusix_modify_end(void *opaque);
void *rusix_modify_vmi(void *opaque);
void rusix_modify_set_vm_flags(void *opaque, vm_flags_t value);
void rusix_modify_set_anon_name(void *opaque, struct anon_vma_name *value);
void rusix_modify_set_policy(void *opaque, struct mempolicy *value);
void rusix_modify_set_give_up_on_oom(void *opaque, bool value);
void rusix_modify_set_uffd(void *opaque, const void *context);
bool rusix_modify_nomem(void *opaque);
bool rusix_modify_merged(void *opaque);
struct vm_area_struct *rusix_modify_merge(void *opaque);
struct vm_area_struct *rusix_modify_error(int error);
bool rusix_modify_is_error(struct vm_area_struct *vma);
struct mm_struct *rusix_modify_mm(struct vm_area_struct *vma);
vm_flags_t rusix_modify_flags(struct vm_area_struct *vma);
void rusix_modify_set_start(struct vm_area_struct *vma, unsigned long value);
void rusix_modify_set_end(struct vm_area_struct *vma, unsigned long value);
void rusix_modify_set_pgoff(struct vm_area_struct *vma, pgoff_t value);
int rusix_modify_max_map_count(void);
rusix_may_split_fn rusix_modify_may_split(const struct vm_operations_struct *ops);
int rusix_modify_split(void *iter, struct vm_area_struct *vma, unsigned long addr, int new_below);
void rusix_modify_iter_free(void *iter);
void rusix_modify_iter_next(void *iter);
void rusix_modify_prev(void *iter);
void rusix_modify_adjust_huge(struct vm_area_struct *vma, unsigned long start, unsigned long end);
bool rusix_modify_is_hugetlb(struct vm_area_struct *vma);
void rusix_modify_hugetlb_split(struct vm_area_struct *vma, unsigned long addr);
void rusix_modify_uprobe_unmap(struct vm_area_struct *vma, unsigned long start, unsigned long end);
void rusix_modify_uprobe_map(struct vm_area_struct *vma);
void rusix_modify_anon_lock(struct anon_vma *anon);
void rusix_modify_anon_unlock(struct anon_vma *anon);
void rusix_modify_anon_pre(struct vm_area_struct *vma);
void rusix_modify_anon_post(struct vm_area_struct *vma);
void rusix_modify_interval_remove(struct vm_area_struct *vma, struct address_space *mapping);
void rusix_modify_unmap_writable(struct address_space *mapping);
void rusix_modify_store_new(void *iter, struct vm_area_struct *vma);
void rusix_modify_detach(struct vm_area_struct *vma);
void rusix_modify_anon_merge(struct vm_area_struct *vma, struct vm_area_struct *remove);
void rusix_modify_warn_start(bool condition);
void rusix_modify_warn_end(bool condition);
void rusix_modify_warn_anon(bool condition);
void rusix_modify_warn_oom(bool condition);
void rusix_modify_warn_removed_end(bool condition);
#endif
