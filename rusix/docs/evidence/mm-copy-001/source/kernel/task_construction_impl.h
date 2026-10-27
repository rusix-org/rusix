/* SPDX-License-Identifier: GPL-2.0-only */
/* Canonical primitives extracted from Linux kernel/fork.c.
 * Copyright (C) 1991, 1992 Linus Torvalds
 * Included only inside fork.c: private allocator access remains here.
 * No adapter publishes the child or accepts a generally live task for mutation.
 */
#ifndef RUSIX_TASK_CONSTRUCTION_IMPL_H
#define RUSIX_TASK_CONSTRUCTION_IMPL_H

/* Private built-in ABI; declarations also keep -Wmissing-prototypes strict. */
int rusix_task_fork_node(struct task_struct *orig);
struct task_struct *rusix_task_alloc(int node);
int rusix_task_arch_dup(struct task_struct *tsk, struct task_struct *orig);
int rusix_task_alloc_stack(struct task_struct *tsk, int node);
int rusix_task_scs(struct task_struct *tsk, int node);
void rusix_task_setup_stack(struct task_struct *tsk, struct task_struct *orig);
bool rusix_task_cpus_are_owned(struct task_struct *orig);
int rusix_task_dup_user_cpus(struct task_struct *tsk, struct task_struct *orig, int node);
void rusix_task_stack_refcount(struct task_struct *tsk);
void rusix_task_account_stack(struct task_struct *tsk);
void rusix_task_clear_seccomp(struct task_struct *tsk);
void rusix_task_clear_notifier(struct task_struct *tsk);
void rusix_task_clear_resched(struct task_struct *tsk);
void rusix_task_stack_magic(struct task_struct *tsk);
void rusix_task_clear_dispatch(struct task_struct *tsk);
void rusix_task_canary(struct task_struct *tsk);
void rusix_task_own_cpus(struct task_struct *tsk);
void rusix_task_refs(struct task_struct *tsk);
void rusix_task_btrace(struct task_struct *tsk);
void rusix_task_clear_transients(struct task_struct *tsk);
void rusix_task_kcov(struct task_struct *tsk);
void rusix_task_kmsan(struct task_struct *tsk);
void rusix_task_kmap(struct task_struct *tsk);
void rusix_task_fault(struct task_struct *tsk);
void rusix_task_blkcg(struct task_struct *tsk);
void rusix_task_pasid(struct task_struct *tsk);
void rusix_task_memcg(struct task_struct *tsk);
void rusix_task_split_lock(struct task_struct *tsk);
void rusix_task_mm_cid(struct task_struct *tsk);
void rusix_task_bpf(struct task_struct *tsk);
void rusix_task_unaccount_stack(struct task_struct *tsk);
void rusix_task_free_stack(struct task_struct *tsk);
void rusix_task_free_slab(struct task_struct *tsk);

const int rusix_task_numa_no_node = NUMA_NO_NODE;
int rusix_task_fork_node(struct task_struct *orig) { return tsk_fork_get_node(orig); }
struct task_struct *rusix_task_alloc(int node) { return alloc_task_struct_node(node); }
int rusix_task_arch_dup(struct task_struct *tsk, struct task_struct *orig)
{
	return arch_dup_task_struct(tsk, orig);
}
int rusix_task_alloc_stack(struct task_struct *tsk, int node)
{
	return alloc_thread_stack_node(tsk, node);
}
int rusix_task_scs(struct task_struct *tsk, int node) { return scs_prepare(tsk, node); }
void rusix_task_setup_stack(struct task_struct *tsk, struct task_struct *orig)
{
	setup_thread_stack(tsk, orig);
}
bool rusix_task_cpus_are_owned(struct task_struct *orig)
{
	return orig->cpus_ptr == &orig->cpus_mask;
}
int rusix_task_dup_user_cpus(struct task_struct *tsk, struct task_struct *orig, int node)
{
	return dup_user_cpus_ptr(tsk, orig, node);
}

void rusix_task_stack_refcount(struct task_struct *tsk)
{
	refcount_set(&tsk->stack_refcount, 1);
}

void rusix_task_account_stack(struct task_struct *tsk)
{
	account_kernel_stack(tsk, 1);
}

void rusix_task_clear_seccomp(struct task_struct *tsk)
{
#ifdef CONFIG_SECCOMP
	tsk->seccomp.filter = NULL;
#endif
}

void rusix_task_clear_notifier(struct task_struct *tsk)
{
	clear_user_return_notifier(tsk);
}

void rusix_task_clear_resched(struct task_struct *tsk)
{
	clear_tsk_need_resched(tsk);
}

void rusix_task_stack_magic(struct task_struct *tsk)
{
	set_task_stack_end_magic(tsk);
}

void rusix_task_clear_dispatch(struct task_struct *tsk)
{
	clear_syscall_work_syscall_user_dispatch(tsk);
}

void rusix_task_canary(struct task_struct *tsk)
{
#ifdef CONFIG_STACKPROTECTOR
	tsk->stack_canary = get_random_canary();
#endif
}

void rusix_task_own_cpus(struct task_struct *tsk)
{
	tsk->cpus_ptr = &tsk->cpus_mask;
}

void rusix_task_refs(struct task_struct *tsk)
{
	refcount_set(&tsk->rcu_users, 2);
	refcount_set(&tsk->usage, 1);
}

void rusix_task_btrace(struct task_struct *tsk)
{
#ifdef CONFIG_BLK_DEV_IO_TRACE
	tsk->btrace_seq = 0;
#endif
}

void rusix_task_clear_transients(struct task_struct *tsk)
{
	tsk->splice_pipe = NULL;
	tsk->task_frag.page = NULL;
	tsk->wake_q.next = NULL;
	tsk->worker_private = NULL;
}

void rusix_task_kcov(struct task_struct *tsk)
{
	kcov_task_init(tsk);
}

void rusix_task_kmsan(struct task_struct *tsk)
{
	kmsan_task_create(tsk);
}

void rusix_task_kmap(struct task_struct *tsk)
{
	kmap_local_fork(tsk);
}

void rusix_task_fault(struct task_struct *tsk)
{
#ifdef CONFIG_FAULT_INJECTION
	tsk->fail_nth = 0;
#endif
}

void rusix_task_blkcg(struct task_struct *tsk)
{
#ifdef CONFIG_BLK_CGROUP
	tsk->throttle_disk = NULL;
	tsk->use_memdelay = 0;
#endif
}

void rusix_task_pasid(struct task_struct *tsk)
{
#ifdef CONFIG_ARCH_HAS_CPU_PASID
	tsk->pasid_activated = 0;
#endif
}

void rusix_task_memcg(struct task_struct *tsk)
{
#ifdef CONFIG_MEMCG
	tsk->active_memcg = NULL;
#endif
}

void rusix_task_split_lock(struct task_struct *tsk)
{
#ifdef CONFIG_X86_BUS_LOCK_DETECT
	tsk->reported_split_lock = 0;
#endif
}

void rusix_task_mm_cid(struct task_struct *tsk)
{
#ifdef CONFIG_SCHED_MM_CID
	tsk->mm_cid = -1;
	tsk->last_mm_cid = -1;
	tsk->mm_cid_active = 0;
	tsk->migrate_from_cpu = -1;
#endif
}

void rusix_task_bpf(struct task_struct *tsk)
{
#ifdef CONFIG_BPF_SYSCALL
	RCU_INIT_POINTER(tsk->bpf_storage, NULL);
	tsk->bpf_ctx = NULL;
#endif
}

void rusix_task_unaccount_stack(struct task_struct *tsk)
{
	exit_task_stack_account(tsk);
}

void rusix_task_free_stack(struct task_struct *tsk)
{
	free_thread_stack(tsk);
}

void rusix_task_free_slab(struct task_struct *tsk)
{
	free_task_struct(tsk);
}

#endif
