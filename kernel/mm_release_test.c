// SPDX-License-Identifier: GPL-2.0-only
/* Real MM references and VMA teardown in retained private workers. Blocking
 * cleanup never runs on the KUnit controller. Uncertain teardown retains storage.
 */
#include <linux/completion.h>
#include <linux/kthread.h>
#include <linux/mm.h>
#include <linux/refcount.h>
#include <linux/sched/mm.h>
#include <linux/sched/task.h>
#include <linux/slab.h>
#include <linux/workqueue.h>
#include "../mm/internal.h"

struct release_fixture {
	refcount_t refs;
	struct task_struct *task;
	struct completion done;
	struct mm_struct *mm;
	u32 mode;
	s64 result[18];
};
void *rusix_mm_test_start(u32 mode);
bool rusix_mm_test_wait(void *p, u32 ms);
void rusix_mm_test_result(void *p, s64 *out);
void rusix_mm_test_put(void *p);

void rusix_mm_test_put(void *p)
{
	struct release_fixture *f = p;

	if (!refcount_dec_and_test(&f->refs))
		return;
	put_task_struct(f->task);
	kfree(f);
}

/* Called only while owning a users reference: the VMA remains live. */
static bool same_vma(struct mm_struct *mm, struct vm_area_struct *expected,
		     unsigned long address)
{
	bool same;

	mmap_read_lock(mm);
	same = find_vma(mm, address) == expected && mm->map_count == 1 &&
		expected->vm_start == address &&
		expected->vm_end - address == PAGE_SIZE;
	mmap_read_unlock(mm);
	return same;
}

static int release_worker(void *p)
{
	struct release_fixture *f = p;
	struct mm_struct *mm;
	struct vm_area_struct *vma = NULL;
	unsigned long address, top, flags;
	bool retained = false;
	int error;

	mm = mm_alloc();
	if (!mm) {
		f->result[0] = -ENOMEM;
		goto done;
	}
	f->mm = mm;
	f->result[1] = atomic_read(&mm->mm_users);
	f->result[2] = atomic_read(&mm->mm_count);
	if (f->result[1] != 1 || f->result[2] != 1)
		goto uncertain;
	if (f->mode == 3) {
		/* Exactly the fresh exec failure storage path, with no inserted VMA.
		 * No assertion or read of mm follows this final storage release. */
		mmdrop(mm);
		f->mm = NULL;
		f->result[16] = 1;
		goto done;
	}

	error = create_init_stack_vma(mm, &vma, &top);
	if (error) {
		f->result[0] = error;
		/* The canonical failed stack constructor has unwound its VMA. */
		mmdrop(mm);
		f->mm = NULL;
		goto done;
	}
	address = vma->vm_start;
	f->result[3] = same_vma(mm, vma, address);
	mmgrab(mm);
	if (!f->result[3] || atomic_read(&mm->mm_count) != 2)
		goto uncertain;

	if (f->mode == 0) {
		mmget(mm);
		mmput(mm);
		f->result[4] = atomic_read(&mm->mm_users);
		f->result[5] = atomic_read(&mm->mm_count);
		if (f->result[4] != 1 || f->result[5] != 2)
			goto uncertain;
		f->result[6] = same_vma(mm, vma, address);
		if (!f->result[6])
			goto uncertain;
		mmget(mm);
		mmput_async(mm);
		f->result[7] = atomic_read(&mm->mm_users);
		f->result[8] = atomic_read(&mm->mm_count);
		if (f->result[7] != 1 || f->result[8] != 2)
			goto uncertain;
		f->result[9] = same_vma(mm, vma, address);
		if (!f->result[9])
			goto uncertain;
	}

	if (f->mode == 2) {
		local_irq_save(flags);
		mmput_async(mm);
		f->result[15] = irqs_disabled();
		local_irq_restore(flags);
		f->result[17] = !in_atomic() && !irqs_disabled();
		/* Only the final transition initializes this work. The explicit
		 * mmgrab keeps its embedding allocation live even if work ran. */
		if (atomic_read(&mm->mm_users) != 0 ||
		    !READ_ONCE(mm->async_put_work.func))
			goto uncertain;
		flush_work(&mm->async_put_work);
	} else {
		mmput(mm);
	}
	/* No VMA pointer is used after final users. exit_mmap intentionally
	 * leaves map_count/total_vm stale: inspect the destroyed tree instead. */
	f->result[10] = atomic_read(&mm->mm_users);
	f->result[11] = atomic_read(&mm->mm_count);
	f->result[12] = mt_empty(&mm->mm_mt);
	f->result[13] = mm->pgd != NULL;
	f->result[14] = mm->rss_stat[0].counters != NULL;
	if (f->result[10] || f->result[11] != 1 || !f->result[12] ||
	    !f->result[13] || !f->result[14])
		goto uncertain;
	mmdrop(mm);
	f->mm = NULL;
	f->result[16] = 1;
	goto done;

uncertain:
	/* No speculative second release if the candidate violates its contract.
	 * Retain MM, taskref and worker fixture ref. The test still fails. */
	f->result[0] = -EIO;
	retained = true;
done:
	complete_all(&f->done);
	if (!retained)
		rusix_mm_test_put(f);
	return 0;
}

void *rusix_mm_test_start(u32 mode)
{
	struct release_fixture *f;
	struct task_struct *task;

	if (mode > 3)
		return ERR_PTR(-EINVAL);
	f = kzalloc(sizeof(*f), GFP_KERNEL);
	if (!f)
		return ERR_PTR(-ENOMEM);
	refcount_set(&f->refs, 2);
	init_completion(&f->done);
	f->mode = mode;
	task = kthread_create(release_worker, f, "rusix_mm_release");
	if (IS_ERR(task)) {
		kfree(f);
		return ERR_CAST(task);
	}
	f->task = task;
	get_task_struct(task);
	wake_up_process(task);
	return f;
}

bool rusix_mm_test_wait(void *p, u32 ms)
{
	struct release_fixture *f = p;

	return wait_for_completion_timeout(&f->done, msecs_to_jiffies(ms)) != 0;
}

void rusix_mm_test_result(void *p, s64 *out)
{
	struct release_fixture *f = p;

	memcpy(out, f->result, sizeof(f->result));
}
