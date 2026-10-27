/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Native storage access and single subsystem operations only. */
const vm_flags_t rusix_merge_sticky = VM_STICKY;
const vm_flags_t rusix_merge_special = VM_SPECIAL;
const vm_flags_t rusix_merge_ignore = VM_IGNORE_MERGE;
const int rusix_merge_nomerge = VMA_MERGE_NOMERGE;
const int rusix_merge_success = VMA_MERGE_SUCCESS;
const int rusix_merge_nomem = VMA_MERGE_ERROR_NOMEM;
struct mm_struct *rusix_merge_mm(void *g)
{
	return ((struct vma_merge_struct *)g)->mm;
}

struct vm_area_struct *rusix_merge_prev(void *g)
{
	return ((struct vma_merge_struct *)g)->prev;
}

void rusix_merge_set_middle(void *g, struct vm_area_struct *value)
{
	((struct vma_merge_struct *)g)->middle = value;
}

void rusix_merge_set_next(void *g, struct vm_area_struct *value)
{
	((struct vma_merge_struct *)g)->next = value;
}

struct vm_area_struct *rusix_merge_target(void *g)
{
	return ((struct vma_merge_struct *)g)->target;
}

void rusix_merge_set_target(void *g, struct vm_area_struct *value)
{
	((struct vma_merge_struct *)g)->target = value;
}

struct vm_area_struct *rusix_merge_copied_from(void *g)
{
	return ((struct vma_merge_struct *)g)->copied_from;
}

void rusix_merge_set_copied_from(void *g, struct vm_area_struct *value)
{
	((struct vma_merge_struct *)g)->copied_from = value;
}

void rusix_merge_set_start(void *g, unsigned long value)
{
	((struct vma_merge_struct *)g)->start = value;
}

void rusix_merge_set_end(void *g, unsigned long value)
{
	((struct vma_merge_struct *)g)->end = value;
}

pgoff_t rusix_merge_pgoff(void *g)
{
	return ((struct vma_merge_struct *)g)->pgoff;
}

void rusix_merge_set_pgoff(void *g, pgoff_t value)
{
	((struct vma_merge_struct *)g)->pgoff = value;
}

vm_flags_t rusix_merge_vm_flags(void *g)
{
	return ((struct vma_merge_struct *)g)->vm_flags;
}

struct anon_vma *rusix_merge_anon_vma(void *g)
{
	return ((struct vma_merge_struct *)g)->anon_vma;
}

struct file *rusix_merge_file(void *g)
{
	return ((struct vma_merge_struct *)g)->file;
}

bool rusix_merge_just_expand(void *g)
{
	return ((struct vma_merge_struct *)g)->just_expand;
}

void rusix_merge_set_adjust_middle_start(void *g, bool value)
{
	((struct vma_merge_struct *)g)->__adjust_middle_start = value;
}

void rusix_merge_set_adjust_next_start(void *g, bool value)
{
	((struct vma_merge_struct *)g)->__adjust_next_start = value;
}

void rusix_merge_set_remove_middle(void *g, bool value)
{
	((struct vma_merge_struct *)g)->__remove_middle = value;
}

void rusix_merge_set_remove_next(void *g, bool value)
{
	((struct vma_merge_struct *)g)->__remove_next = value;
}

void rusix_merge_set_state(void *g, int state)
{
	((struct vma_merge_struct *)g)->state = state;
}

bool rusix_merge_singular(struct vm_area_struct *v)
{
	return list_is_singular(&v->anon_vma_chain);
}

bool rusix_merge_policy_equal(void *g, struct vm_area_struct *v)
{
	return mpol_equal(((struct vma_merge_struct *)g)->policy, vma_policy(v));
}

bool rusix_merge_uffd_equal(void *g, struct vm_area_struct *v)
{
	return is_mergeable_vm_userfaultfd_ctx(v, ((struct vma_merge_struct *)g)->uffd_ctx);
}

bool rusix_merge_name_equal(void *g, struct vm_area_struct *v)
{
	return anon_vma_name_eq(anon_vma_name(v), ((struct vma_merge_struct *)g)->anon_name);
}

void rusix_merge_set_anon(struct vm_area_struct *v, struct anon_vma *anon)
{
	v->anon_vma = anon;
}

void rusix_merge_assert_mm(struct mm_struct *mm)
{
	mmap_assert_write_locked(mm);
}

void rusix_merge_assert_vma(struct vm_area_struct *v)
{
	vma_assert_write_locked(v);
}

void rusix_merge_warn(bool condition)
{
	VM_WARN_ON(condition);
}

void rusix_merge_warn_range(bool condition)
{
	WARN_ON(condition);
}

void rusix_merge_warn_vmg(bool condition, void *g)
{
	VM_WARN_ON_VMG(condition, (struct vma_merge_struct *)g);
}

unsigned long rusix_merge_iter_addr(void *i)
{
	return vma_iter_addr((struct vma_iterator *)i);
}

struct vm_area_struct *rusix_merge_iter_next_range(void *i)
{
	return vma_iter_next_range((struct vma_iterator *)i);
}

void rusix_merge_iter_prev_range(void *i)
{
	vma_iter_prev_range((struct vma_iterator *)i);
}

void rusix_merge_iter_set(void *i, unsigned long start)
{
	vma_iter_set((struct vma_iterator *)i, start);
}

void rusix_merge_iter_load(void *i)
{
	vma_iter_load((struct vma_iterator *)i);
}

void rusix_merge_iter_store(void *i, struct vm_area_struct *v)
{
	vma_iter_store_overwrite((struct vma_iterator *)i, v);
}

void rusix_merge_iter_clear(void *i)
{
	vma_iter_clear((struct vma_iterator *)i);
}

struct vm_area_struct *rusix_merge_iter_next_rewind(void *i)
{
	return vma_iter_next_rewind((struct vma_iterator *)i, NULL);
}

void rusix_merge_adjust_huge(struct vm_area_struct *v, unsigned long start, unsigned long end, struct vm_area_struct *adjust)
{
	vma_adjust_trans_huge(v, start, end, adjust);
}

void rusix_merge_flags_set(struct vm_area_struct *v, vm_flags_t flags)
{
	vm_flags_set(v, flags);
}

void rusix_merge_khugepaged(struct vm_area_struct *v, vm_flags_t flags)
{
	khugepaged_enter_vma(v, flags);
}
