// SPDX-License-Identifier: GPL-2.0
/* KUnit-only bridge, included from helpers.c under CONFIG_KUNIT. */
#include <linux/err.h>
#include <linux/jiffies.h>
#include <linux/kthread.h>
#include <linux/sched/signal.h>
#include <linux/sched/task.h>
#include <linux/signal.h>

/* The caller receives an independent task reference and must start the thread.
 * The callback is standalone: no kthread_stop(), no borrowed callback data.
 */
struct task_struct *rust_helper_completion_test_kthread_create(
	int (*threadfn)(void *), void *data)
{
	struct task_struct *task;

	task = kthread_create(threadfn, data, "rusix-cwait");
	if (!IS_ERR(task))
		get_task_struct(task);
	return task;
}

/* Only a dedicated test kthread may call this, for SIGUSR1 or SIGKILL. */
void rust_helper_completion_test_allow_signal(int sig)
{
	allow_signal(sig);
}

int rust_helper_completion_test_send_signal(struct task_struct *task, int sig)
{
	return send_sig(sig, task, 1);
}

unsigned long rust_helper_completion_test_jiffies(void)
{
	return READ_ONCE(jiffies);
}
