// SPDX-License-Identifier: GPL-2.0-only
/* Native MM/file construction. Only private workers perform teardown; timeout
 * or uncertain ownership retains every reference needed by possible callbacks.
 */
#include <linux/anon_inodes.h>
#include <linux/completion.h>
#include <linux/file.h>
#include <linux/fs.h>
#include <linux/kthread.h>
#include <linux/mm.h>
#include <linux/mman.h>
#include <linux/refcount.h>
#include <linux/sched/mm.h>
#include <linux/sched/task.h>
#include <linux/slab.h>

struct exit_fixture {
	refcount_t refs;
	struct task_struct *task;
	struct completion done;
	struct mm_struct *mm;
	struct file *file;
	u32 mode;
	s64 result[16];
};
void *rusix_exit_test_start(u32 mode);
bool rusix_exit_test_wait(void *ptr, u32 ms);
void rusix_exit_test_result(void *ptr, s64 *out);
void rusix_exit_test_put(void *ptr);

void rusix_exit_test_put(void *ptr)
{
	struct exit_fixture *f = ptr;

	if (!refcount_dec_and_test(&f->refs))
		return;
	put_task_struct(f->task);
	kfree(f);
}

static void poison_close(struct vm_area_struct *vma)
{
	struct exit_fixture *f = vma->vm_private_data;

	f->result[4]++;
}

static const struct vm_operations_struct poison_ops = { .close = poison_close };

static void fixture_close(struct vm_area_struct *vma)
{
	struct exit_fixture *f = vma->vm_private_data;

	f->result[3]++;
	f->result[5] = vma->vm_file == f->file;
	f->result[6] = file_count(f->file);
	f->result[7] = f->result[8] == 0;
	/* Native vma_close must replace this with dummy hooks after return.
	 * MAP_FIXED cleanup will later invoke remove_vma on this same descriptor. */
	vma->vm_ops = &poison_ops;
}

static const struct vm_operations_struct fixture_ops = { .close = fixture_close };

static int fixture_mmap(struct file *file, struct vm_area_struct *vma)
{
	vma->vm_ops = &fixture_ops;
	vma->vm_private_data = file->private_data;
	return 0;
}

static int fixture_release(struct inode *inode, struct file *file)
{
	struct exit_fixture *f = file->private_data;

	f->result[8]++;
	f->result[9] = f->result[3] == 1 && f->result[4] == 0;
	return 0;
}

static const struct file_operations fixture_fops = {
	.mmap = fixture_mmap,
	.release = fixture_release,
};

static int exit_worker(void *ptr)
{
	struct exit_fixture *f = ptr;
	struct mm_struct *mm;
	unsigned long address;
	const unsigned long target = 0x10000000;
	bool adopted = false, retained = false;

	mm = mm_alloc();
	if (!mm) {
		f->result[0] = -ENOMEM;
		goto done;
	}
	f->mm = mm;
	if (atomic_read(&mm->mm_users) != 1 || atomic_read(&mm->mm_count) != 1 ||
	    !mtree_empty(&mm->mm_mt))
		goto uncertain;
	mmgrab(mm);
	f->result[1] = atomic_read(&mm->mm_count);
	if (f->result[1] != 2)
		goto uncertain;

	if (f->mode) {
		f->file = anon_inode_create_getfile("rusix_exit", &fixture_fops, f,
						 O_RDWR, NULL);
		if (IS_ERR(f->file)) {
			f->result[0] = PTR_ERR(f->file);
			f->file = NULL;
			goto uncertain;
		}
		/* Final-address native MM, no shared process/descriptor state. Fixed
		 * placement in its verified empty tree needs no mmap-base setup. */
		kthread_use_mm(mm);
		adopted = true;
		address = vm_mmap(f->file, target, PAGE_SIZE, PROT_READ | PROT_WRITE,
				  MAP_PRIVATE | MAP_FIXED, 0);
		if (IS_ERR_VALUE(address) || address != target)
			goto uncertain;
		f->result[2] = file_count(f->file);
		if (f->result[2] != 2 || mm->map_count != 1)
			goto uncertain;
		if (f->mode == 2) {
			/* Unlike ordinary vm_munmap, MAP_FIXED first closes detached
			 * old VMAs in vms_clean_up_area, then remove_vma sees dummy
			 * hooks in vms_complete_munmap_vmas. Never fault either map. */
			address = vm_mmap(NULL, target, PAGE_SIZE, PROT_READ | PROT_WRITE,
					  MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, 0);
			if (IS_ERR_VALUE(address) || address != target ||
			    f->result[3] != 1 || f->result[4] ||
			    file_count(f->file) != 1)
				goto uncertain;
		}
		kthread_unuse_mm(mm);
		adopted = false;
	}
	mmput(mm);
	/* The explicit mmgrab protects storage, not any removed VMA. Native
	 * exit_mmap leaves map_count stale; only the destroyed tree is tested. */
	f->result[10] = atomic_read(&mm->mm_users);
	f->result[11] = atomic_read(&mm->mm_count);
	f->result[12] = mtree_empty(&mm->mm_mt);
	f->result[13] = mm->pgd != NULL && mm->rss_stat[0].counters != NULL;
	/* Adopted MMs may retain native lazy-TLB references after unuse_mm,
	 * including references lent to other scheduled kernel threads. Only
	 * the never-adopted empty mode has an exact remaining-count oracle.
	 * Mapped modes prove retained storage, not final reference exhaustion. */
	if (f->result[10] || (f->mode ? f->result[11] < 1 : f->result[11] != 1) ||
	    !f->result[12] || !f->result[13])
		goto uncertain;
	if (f->mode && (f->result[3] != 1 || f->result[4] || !f->result[5] ||
			f->result[6] != 2 || !f->result[7] || f->result[8] ||
			file_count(f->file) != 1))
		goto uncertain;
	mmdrop(mm);
	f->mm = NULL;
	if (f->file) {
		/* Private test file has no other users or filesystem teardown work.
		 * Its synchronous release callback retains the worker fixture ref. */
		__fput_sync(f->file);
		f->file = NULL;
		if (f->result[8] != 1 || !f->result[9])
			goto uncertain;
	}
	f->result[14] = 1;
	goto done;
uncertain:
	if (adopted)
		kthread_unuse_mm(mm);
	/* No guessed second mmput or fput after a contract violation. Keep all
	 * still-owned references and the worker fixture ref; report failure. */
	if (!f->result[0])
		f->result[0] = -EIO;
	retained = true;
done:
	complete_all(&f->done);
	if (!retained)
		rusix_exit_test_put(f);
	return 0;
}

void *rusix_exit_test_start(u32 mode)
{
	struct exit_fixture *f;
	struct task_struct *task;

	if (mode > 2)
		return ERR_PTR(-EINVAL);
	f = kzalloc(sizeof(*f), GFP_KERNEL);
	if (!f)
		return ERR_PTR(-ENOMEM);
	refcount_set(&f->refs, 2);
	init_completion(&f->done);
	f->mode = mode;
	task = kthread_create(exit_worker, f, "rusix_exit_mmap");
	if (IS_ERR(task)) {
		kfree(f);
		return ERR_CAST(task);
	}
	f->task = task;
	get_task_struct(task);
	wake_up_process(task);
	return f;
}

bool rusix_exit_test_wait(void *ptr, u32 ms)
{
	struct exit_fixture *f = ptr;

	return wait_for_completion_timeout(&f->done, msecs_to_jiffies(ms)) != 0;
}

void rusix_exit_test_result(void *ptr, s64 *out)
{
	struct exit_fixture *f = ptr;

	/* Caller must have observed done; results are immutable after complete. */
	memcpy(out, f->result, sizeof(f->result));
}
