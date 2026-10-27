/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Canonical descriptor operations from mm/vma.c and mm/internal.h.
 * Included only by vma.c. No descriptor-wide Rust references are formed.
 */
#ifndef RUSIX_REMOVE_VMA_IMPL_H
#define RUSIX_REMOVE_VMA_IMPL_H
void rusix_remove_might_sleep(void);
const struct vm_operations_struct *rusix_remove_ops(struct vm_area_struct *vma);
typedef void (*rusix_vma_close_fn)(struct vm_area_struct *vma);
rusix_vma_close_fn rusix_remove_close(const struct vm_operations_struct *ops);
void rusix_remove_dummy(struct vm_area_struct *vma);
struct file *rusix_remove_file(struct vm_area_struct *vma);
void rusix_remove_fput(struct file *file);
void rusix_remove_policy(struct vm_area_struct *vma);

void rusix_remove_might_sleep(void)
{
	might_sleep();
}

const struct vm_operations_struct *rusix_remove_ops(struct vm_area_struct *vma)
{
	return vma->vm_ops;
}

rusix_vma_close_fn rusix_remove_close(const struct vm_operations_struct *ops)
{
	return ops->close;
}

void rusix_remove_dummy(struct vm_area_struct *vma)
{
	vma->vm_ops = &vma_dummy_vm_ops;
}

struct file *rusix_remove_file(struct vm_area_struct *vma)
{
	return vma->vm_file;
}

void rusix_remove_fput(struct file *file)
{
	fput(file);
}

void rusix_remove_policy(struct vm_area_struct *vma)
{
	mpol_put(vma_policy(vma));
}
#endif /* RUSIX_REMOVE_VMA_IMPL_H */
