// SPDX-License-Identifier: GPL-2.0

#include <linux/sched/signal.h>

int rust_helper_signal_pending(struct task_struct *t)
{
	return signal_pending(t);
}

int rust_helper_signal_pending_state(unsigned int state, struct task_struct *task)
{
	return signal_pending_state(state, task);
}
