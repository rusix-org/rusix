/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef RUSIX_VMA_MERGE_H
#define RUSIX_VMA_MERGE_H
/* Pointer/scalar ABI only; no copied native context layout. */
struct vm_area_struct *rusix_merge_existing(void *g, void *prep);
struct vm_area_struct *rusix_merge_new(void *g, void *prep);
struct vm_area_struct *rusix_merge_copied(void *g, void *prep);
int rusix_merge_expand(void *g, void *prep);
struct vm_area_struct *rusix_merge_extend(void *g, void *prep);
int rusix_merge_shrink(void *i, struct vm_area_struct *v, unsigned long start, unsigned long end, pgoff_t pgoff, void *prep);
struct mm_struct *rusix_merge_mm(void *g);
struct vm_area_struct *rusix_merge_prev(void *g);
void rusix_merge_set_middle(void *g, struct vm_area_struct *value);
void rusix_merge_set_next(void *g, struct vm_area_struct *value);
struct vm_area_struct *rusix_merge_target(void *g);
void rusix_merge_set_target(void *g, struct vm_area_struct *value);
struct vm_area_struct *rusix_merge_copied_from(void *g);
void rusix_merge_set_copied_from(void *g, struct vm_area_struct *value);
void rusix_merge_set_start(void *g, unsigned long value);
void rusix_merge_set_end(void *g, unsigned long value);
pgoff_t rusix_merge_pgoff(void *g);
void rusix_merge_set_pgoff(void *g, pgoff_t value);
vm_flags_t rusix_merge_vm_flags(void *g);
struct anon_vma *rusix_merge_anon_vma(void *g);
struct file *rusix_merge_file(void *g);
bool rusix_merge_just_expand(void *g);
void rusix_merge_set_adjust_middle_start(void *g, bool value);
void rusix_merge_set_adjust_next_start(void *g, bool value);
void rusix_merge_set_remove_middle(void *g, bool value);
void rusix_merge_set_remove_next(void *g, bool value);
void rusix_merge_set_state(void *g, int state);
bool rusix_merge_singular(struct vm_area_struct *v);
bool rusix_merge_policy_equal(void *g, struct vm_area_struct *v);
bool rusix_merge_uffd_equal(void *g, struct vm_area_struct *v);
bool rusix_merge_name_equal(void *g, struct vm_area_struct *v);
void rusix_merge_set_anon(struct vm_area_struct *v, struct anon_vma *anon);
void rusix_merge_assert_mm(struct mm_struct *mm);
void rusix_merge_assert_vma(struct vm_area_struct *v);
void rusix_merge_warn(bool condition);
void rusix_merge_warn_range(bool condition);
void rusix_merge_warn_vmg(bool condition, void *g);
unsigned long rusix_merge_iter_addr(void *i);
struct vm_area_struct *rusix_merge_iter_next_range(void *i);
void rusix_merge_iter_prev_range(void *i);
void rusix_merge_iter_set(void *i, unsigned long start);
void rusix_merge_iter_load(void *i);
void rusix_merge_iter_store(void *i, struct vm_area_struct *v);
void rusix_merge_iter_clear(void *i);
struct vm_area_struct *rusix_merge_iter_next_rewind(void *i);
void rusix_merge_adjust_huge(struct vm_area_struct *v, unsigned long start, unsigned long end, struct vm_area_struct *adjust);
void rusix_merge_flags_set(struct vm_area_struct *v, vm_flags_t flags);
void rusix_merge_khugepaged(struct vm_area_struct *v, vm_flags_t flags);
extern const vm_flags_t rusix_merge_sticky;
extern const vm_flags_t rusix_merge_special;
extern const vm_flags_t rusix_merge_ignore;
extern const int rusix_merge_nomerge;
extern const int rusix_merge_success;
extern const int rusix_merge_nomem;
#endif
