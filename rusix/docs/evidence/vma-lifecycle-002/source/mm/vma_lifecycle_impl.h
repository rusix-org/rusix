/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Canonical primitives from vma_init.c and its inline dependencies. Included
 * only by vma_init.c, preserving that TU's vma_lock_init static lockdep key.
 * No whole-descriptor lifecycle or permanent cache storage lives here.
 */
#ifndef RUSIX_VMA_LIFECYCLE_IMPL_H
#define RUSIX_VMA_LIFECYCLE_IMPL_H
#ifndef __HAVE_PFNMAP_TRACKING
#error Rust VMA lifecycle requires the reviewed x86 PFN tracking ABI
#endif
extern const unsigned int rusix_vma_refcount_max;
const unsigned int rusix_vma_refcount_max = REFCOUNT_MAX;
struct kmem_cache * __init rusix_vma_cache_create(void);
struct vm_area_struct * rusix_vma_alloc(struct kmem_cache *cache);
void rusix_vma_slab_free(struct kmem_cache *cache, struct vm_area_struct *vma);
void rusix_vma_zero(struct vm_area_struct *vma);
void rusix_vma_set_mm(struct vm_area_struct *vma, struct mm_struct *mm);
void rusix_vma_dummy_ops(struct vm_area_struct *vma);
void rusix_vma_list_init(struct vm_area_struct *vma);
void rusix_vma_lock_init(struct vm_area_struct *vma, bool reset);
void rusix_vma_assert_flags(struct vm_area_struct *vma);
void rusix_vma_assert_file(struct vm_area_struct *vma);
void rusix_vma_copy_vm_mm(const struct vm_area_struct *src, struct vm_area_struct *dest);
void rusix_vma_copy_vm_ops(const struct vm_area_struct *src, struct vm_area_struct *dest);
void rusix_vma_copy_vm_start(const struct vm_area_struct *src, struct vm_area_struct *dest);
void rusix_vma_copy_vm_end(const struct vm_area_struct *src, struct vm_area_struct *dest);
void rusix_vma_copy_anon_vma(const struct vm_area_struct *src, struct vm_area_struct *dest);
void rusix_vma_copy_vm_pgoff(const struct vm_area_struct *src, struct vm_area_struct *dest);
void rusix_vma_copy_vm_file(const struct vm_area_struct *src, struct vm_area_struct *dest);
void rusix_vma_copy_vm_private_data(const struct vm_area_struct *src, struct vm_area_struct *dest);
void rusix_vma_copy_flags(const struct vm_area_struct *src, struct vm_area_struct *dest);
void rusix_vma_copy_prot(const struct vm_area_struct *src, struct vm_area_struct *dest);
void rusix_vma_copy_shared(const struct vm_area_struct *src, struct vm_area_struct *dest);
void rusix_vma_copy_userfault(const struct vm_area_struct *src, struct vm_area_struct *dest);
void rusix_vma_copy_name(const struct vm_area_struct *src, struct vm_area_struct *dest);
void rusix_vma_copy_swap(const struct vm_area_struct *src, struct vm_area_struct *dest);
void rusix_vma_copy_policy(const struct vm_area_struct *src, struct vm_area_struct *dest);
void rusix_vma_pfn_clear(struct vm_area_struct *vma);
struct pfnmap_track_ctx * rusix_vma_pfn_get(struct vm_area_struct *vma);
unsigned int rusix_vma_pfn_count(struct pfnmap_track_ctx *ctx);
void rusix_vma_pfn_acquire(struct pfnmap_track_ctx *ctx);
void rusix_vma_pfn_set(struct vm_area_struct *vma, struct pfnmap_track_ctx *ctx);
void rusix_vma_pfn_put(struct pfnmap_track_ctx *ctx);
void rusix_vma_numa_init(struct vm_area_struct *vma);
void rusix_vma_name_dup(struct vm_area_struct *orig, struct vm_area_struct *new);
void rusix_vma_assert_detached(struct vm_area_struct *vma);
void rusix_vma_numa_free(struct vm_area_struct *vma);
void rusix_vma_name_free(struct vm_area_struct *vma);
struct kmem_cache * __init rusix_vma_cache_create(void)
{
	struct kmem_cache_args args = {
		.use_freeptr_offset = true,
		.freeptr_offset = offsetof(struct vm_area_struct, vm_freeptr),
		.sheaf_capacity = 32,
	};
	return kmem_cache_create("vm_area_struct", sizeof(struct vm_area_struct),
			&args, SLAB_HWCACHE_ALIGN|SLAB_PANIC|SLAB_TYPESAFE_BY_RCU|
			SLAB_ACCOUNT);
}
struct vm_area_struct * rusix_vma_alloc(struct kmem_cache *cache)
{
	return kmem_cache_alloc(cache, GFP_KERNEL);
}
void rusix_vma_slab_free(struct kmem_cache *cache, struct vm_area_struct *vma)
{
	kmem_cache_free(cache, vma);
}
void rusix_vma_zero(struct vm_area_struct *vma)
{
	memset(vma, 0, sizeof(*vma));
}
void rusix_vma_set_mm(struct vm_area_struct *vma, struct mm_struct *mm)
{
	vma->vm_mm = mm;
}
void rusix_vma_dummy_ops(struct vm_area_struct *vma)
{
	vma->vm_ops = &vma_dummy_vm_ops;
}
void rusix_vma_list_init(struct vm_area_struct *vma)
{
	INIT_LIST_HEAD(&vma->anon_vma_chain);
}
void rusix_vma_lock_init(struct vm_area_struct *vma, bool reset)
{
	vma_lock_init(vma, reset);
}
void rusix_vma_assert_flags(struct vm_area_struct *vma)
{
	ASSERT_EXCLUSIVE_WRITER(vma->vm_flags);
}
void rusix_vma_assert_file(struct vm_area_struct *vma)
{
	ASSERT_EXCLUSIVE_WRITER(vma->vm_file);
}
void rusix_vma_copy_vm_mm(const struct vm_area_struct *src, struct vm_area_struct *dest)
{
	dest->vm_mm = src->vm_mm;
}
void rusix_vma_copy_vm_ops(const struct vm_area_struct *src, struct vm_area_struct *dest)
{
	dest->vm_ops = src->vm_ops;
}
void rusix_vma_copy_vm_start(const struct vm_area_struct *src, struct vm_area_struct *dest)
{
	dest->vm_start = src->vm_start;
}
void rusix_vma_copy_vm_end(const struct vm_area_struct *src, struct vm_area_struct *dest)
{
	dest->vm_end = src->vm_end;
}
void rusix_vma_copy_anon_vma(const struct vm_area_struct *src, struct vm_area_struct *dest)
{
	dest->anon_vma = src->anon_vma;
}
void rusix_vma_copy_vm_pgoff(const struct vm_area_struct *src, struct vm_area_struct *dest)
{
	dest->vm_pgoff = src->vm_pgoff;
}
void rusix_vma_copy_vm_file(const struct vm_area_struct *src, struct vm_area_struct *dest)
{
	dest->vm_file = src->vm_file;
}
void rusix_vma_copy_vm_private_data(const struct vm_area_struct *src, struct vm_area_struct *dest)
{
	dest->vm_private_data = src->vm_private_data;
}
void rusix_vma_copy_flags(const struct vm_area_struct *src, struct vm_area_struct *dest)
{
	vm_flags_init(dest, src->vm_flags);
}
void rusix_vma_copy_prot(const struct vm_area_struct *src, struct vm_area_struct *dest)
{
	memcpy(&dest->vm_page_prot, &src->vm_page_prot, sizeof(dest->vm_page_prot));
}
void rusix_vma_copy_shared(const struct vm_area_struct *src, struct vm_area_struct *dest)
{
	/* Original tolerated race: caller reinitializes shared.rb linkage. */
	data_race(memcpy(&dest->shared, &src->shared, sizeof(dest->shared)));
}
void rusix_vma_copy_userfault(const struct vm_area_struct *src, struct vm_area_struct *dest)
{
	memcpy(&dest->vm_userfaultfd_ctx, &src->vm_userfaultfd_ctx,
	       sizeof(dest->vm_userfaultfd_ctx));
}
void rusix_vma_copy_name(const struct vm_area_struct *src, struct vm_area_struct *dest)
{
#ifdef CONFIG_ANON_VMA_NAME
	dest->anon_name = src->anon_name;
#endif
}
void rusix_vma_copy_swap(const struct vm_area_struct *src, struct vm_area_struct *dest)
{
#ifdef CONFIG_SWAP
	memcpy(&dest->swap_readahead_info, &src->swap_readahead_info,
	       sizeof(dest->swap_readahead_info));
#endif
}
void rusix_vma_copy_policy(const struct vm_area_struct *src, struct vm_area_struct *dest)
{
#ifdef CONFIG_NUMA
	dest->vm_policy = src->vm_policy;
#endif
}
void rusix_vma_pfn_clear(struct vm_area_struct *vma)
{
	vma->pfnmap_track_ctx = NULL;
}
struct pfnmap_track_ctx * rusix_vma_pfn_get(struct vm_area_struct *vma)
{
	return vma->pfnmap_track_ctx;
}
unsigned int rusix_vma_pfn_count(struct pfnmap_track_ctx *ctx)
{
	return kref_read(&ctx->kref);
}
void rusix_vma_pfn_acquire(struct pfnmap_track_ctx *ctx)
{
	kref_get(&ctx->kref);
}
void rusix_vma_pfn_set(struct vm_area_struct *vma, struct pfnmap_track_ctx *ctx)
{
	vma->pfnmap_track_ctx = ctx;
}
void rusix_vma_pfn_put(struct pfnmap_track_ctx *ctx)
{
	kref_put(&ctx->kref, pfnmap_track_ctx_release);
}
void rusix_vma_numa_init(struct vm_area_struct *vma)
{
	vma_numab_state_init(vma);
}
void rusix_vma_name_dup(struct vm_area_struct *orig, struct vm_area_struct *new)
{
	dup_anon_vma_name(orig, new);
}
void rusix_vma_assert_detached(struct vm_area_struct *vma)
{
	vma_assert_detached(vma);
}
void rusix_vma_numa_free(struct vm_area_struct *vma)
{
	vma_numab_state_free(vma);
}
void rusix_vma_name_free(struct vm_area_struct *vma)
{
	free_anon_vma_name(vma);
}
#endif
