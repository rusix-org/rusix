// SPDX-License-Identifier: GPL-2.0-only
/* Real private-MM transactions. No guest address is faulted or host probe run. */
#include <kunit/test.h>
#include <linux/anon_inodes.h>
#include <linux/completion.h>
#include <linux/file.h>
#include <linux/fs.h>
#include <linux/kthread.h>
#include <linux/maple_tree.h>
#include <linux/mm.h>
#include <linux/mman.h>
#include <linux/mutex.h>
#include <linux/refcount.h>
#include <linux/rmap.h>
#include <linux/rusix_vma_merge_test.h>
#include <linux/sched/mm.h>
#include <linux/sched/task.h>
#include <linux/slab.h>
#include <linux/spinlock.h>

#include "vma_internal.h"
#include "vma.h"

/* Permanent storage, never an unprotected pointer to a freed fixture. Hooks
 * compare owner/address identities and touch counters only under this lock.
 */
static DEFINE_SPINLOCK(gate_lock);
static DEFINE_MUTEX(worker_lock);
static struct {
	struct task_struct *owner;
	struct mm_struct *mm;
	struct ma_state *mas;
	struct vm_area_struct *dst, *src;
	enum rusix_merge_fault fault;
	struct rusix_merge_observation seen;
} gate;

int rusix_merge_test_arm(struct mm_struct *mm, struct ma_state *mas,
			struct vm_area_struct *dst, struct vm_area_struct *src,
			enum rusix_merge_fault fault)
{
	unsigned long flags;
	int ret = 0;

	mmap_assert_write_locked(mm);
	spin_lock_irqsave(&gate_lock, flags);
	if (gate.owner || current->mm != mm || mas->tree != &mm->mm_mt ||
	    mas->alloc || mas->sheaf) {
		ret = -EINVAL;
	} else {
		memset(&gate, 0, sizeof(gate));
		gate.owner = current;
		gate.mm = mm;
		gate.mas = mas;
		gate.dst = dst;
		gate.src = src;
		gate.fault = fault;
	}
	spin_unlock_irqrestore(&gate_lock, flags);
	return ret;
}

int rusix_merge_test_disarm(struct rusix_merge_observation *out)
{
	unsigned long flags;
	int ret = 0;

	spin_lock_irqsave(&gate_lock, flags);
	if (gate.owner != current) {
		ret = -EINVAL;
	} else {
		*out = gate.seen;
		memset(&gate, 0, sizeof(gate));
	}
	spin_unlock_irqrestore(&gate_lock, flags);
	return ret;
}

static bool clone_match(struct vm_area_struct *dst, struct vm_area_struct *src)
{
	return gate.owner == current && gate.mm == current->mm &&
		gate.dst == dst && gate.src == src;
}

void rusix_merge_test_clone_begin(struct vm_area_struct *dst, struct vm_area_struct *src)
{
	unsigned long flags;

	spin_lock_irqsave(&gate_lock, flags);
	if (clone_match(dst, src) && ++gate.seen.clone_begin != 1)
		gate.seen.malformed = true;
	spin_unlock_irqrestore(&gate_lock, flags);
}

bool rusix_merge_test_clone_fail(struct vm_area_struct *dst, struct vm_area_struct *src,
				gfp_t gfp)
{
	unsigned long flags;
	bool fail = false;

	spin_lock_irqsave(&gate_lock, flags);
	if (clone_match(dst, src)) {
		if (gate.seen.clone_begin != 1 || gate.seen.clone_end)
			gate.seen.malformed = true;
		if (gfp == GFP_NOWAIT) {
			if (++gate.seen.clone_nowait != 1 || gate.seen.clone_retry)
				gate.seen.malformed = true;
		} else if (gfp == GFP_KERNEL) {
			if (++gate.seen.clone_retry != 1 || gate.seen.clone_nowait != 1)
				gate.seen.malformed = true;
		} else {
			gate.seen.malformed = true;
		}
		fail = gate.fault == RUSIX_FAULT_CLONE && !gate.seen.malformed;
	}
	spin_unlock_irqrestore(&gate_lock, flags);
	return fail;
}

void rusix_merge_test_clone_end(struct vm_area_struct *dst, struct vm_area_struct *src, int ret)
{
	unsigned long flags;

	spin_lock_irqsave(&gate_lock, flags);
	if (clone_match(dst, src)) {
		if (++gate.seen.clone_end != 1 || gate.seen.clone_begin != 1)
			gate.seen.malformed = true;
		gate.seen.clone_result = ret;
		gate.seen.clone_cleared = !dst->anon_vma && list_empty(&dst->anon_vma_chain);
	}
	spin_unlock_irqrestore(&gate_lock, flags);
}

static bool maple_match(struct ma_state *mas)
{
	return gate.owner == current && gate.mm == current->mm && gate.mas == mas &&
		mas->tree == &gate.mm->mm_mt;
}

void rusix_merge_test_maple_begin(struct ma_state *mas)
{
	unsigned long flags;

	spin_lock_irqsave(&gate_lock, flags);
	if (maple_match(mas) && ++gate.seen.maple_begin != 1)
		gate.seen.malformed = true;
	spin_unlock_irqrestore(&gate_lock, flags);
}

bool rusix_merge_test_maple_fail(struct ma_state *mas)
{
	unsigned long flags;
	bool fail = false;

	spin_lock_irqsave(&gate_lock, flags);
	if (maple_match(mas)) {
		gate.seen.node_request = mas->node_request;
		gate.seen.store_type = mas->store_type;
		if (gate.seen.maple_begin != 1 || gate.seen.maple_end ||
		    !mas->node_request || mas->alloc || mas->sheaf)
			gate.seen.malformed = true;
		if (gate.fault == RUSIX_FAULT_MAPLE && !gate.seen.malformed) {
			if (++gate.seen.maple_injected != 1)
				gate.seen.malformed = true;
			fail = !gate.seen.malformed;
		}
	}
	spin_unlock_irqrestore(&gate_lock, flags);
	return fail;
}

void rusix_merge_test_maple_end(struct ma_state *mas, int ret)
{
	unsigned long flags;

	spin_lock_irqsave(&gate_lock, flags);
	if (maple_match(mas)) {
		if (++gate.seen.maple_end != 1 || gate.seen.maple_begin != 1)
			gate.seen.malformed = true;
		gate.seen.maple_result = ret;
		gate.seen.maple_reset = !mas->alloc && !mas->sheaf && !mas->node_request &&
			!(mas->mas_flags & MA_STATE_PREALLOC) && mas->status == ma_start;
	}
	spin_unlock_irqrestore(&gate_lock, flags);
}

#define FILLERS 64
#define SNAP_LIMIT (FILLERS + 3)
#define TARGET 0x10000000UL
#define FORBIDDEN (VM_ACCOUNT | VM_LOCKED | VM_LOCKONFAULT | VM_HUGETLB | VM_PFNMAP | VM_MIXEDMAP)

struct vma_record {
	unsigned long pointer, start, end, pgoff, flags, file, ops;
};
struct vm_counts {
	unsigned long total, exec, stack, data, locked;
};
struct merge_fixture {
	refcount_t refs;
	struct task_struct *task;
	struct completion done;
	enum rusix_merge_case mode;
	struct mm_struct *mm;
	struct file *file;
	struct anon_vma *anon;
	struct vma_record before[SNAP_LIMIT], expected[SNAP_LIMIT], after[SNAP_LIMIT];
	struct vm_counts counts, counts_after;
	struct rusix_merge_outcome outcome;
	unsigned int before_count, expected_count;
	int after_count;
	unsigned int closes, releases, expected_closes;
	unsigned int before_active, before_children;
	unsigned long before_file_count;
	int status, phase;
	bool callback_bad, cleanup;
};

static bool is_file_case(enum rusix_merge_case mode)
{
	return mode >= RUSIX_MIDDLE_CLOSE && mode <= RUSIX_NEW_NEXT_CLOSE;
}

static bool is_existing(enum rusix_merge_case mode)
{
	return mode <= RUSIX_EXISTING_PREALLOC_SILENT || mode == RUSIX_MIDDLE_CLOSE ||
		mode == RUSIX_NEXT_CLOSE || mode == RUSIX_BOTH_SUCCESS ||
		mode == RUSIX_EXISTING_SUCCESS;
}

static bool is_shrink(enum rusix_merge_case mode)
{
	return mode == RUSIX_SHRINK_PREALLOC || mode == RUSIX_SHRINK_SUCCESS;
}

static bool is_failure(enum rusix_merge_case mode)
{
	return mode <= RUSIX_SHRINK_PREALLOC;
}

static bool is_clone_failure(enum rusix_merge_case mode)
{
	return mode == RUSIX_EXISTING_CLONE_REPORT || mode == RUSIX_EXISTING_CLONE_SILENT ||
		mode == RUSIX_EXPAND_CLONE;
}

static void fixture_put(struct merge_fixture *f)
{
	if (refcount_dec_and_test(&f->refs)) {
		put_task_struct(f->task);
		kfree(f);
	}
}

static void test_close(struct vm_area_struct *vma)
{
	struct merge_fixture *f = vma->vm_private_data;

	f->closes++;
	if (vma->vm_file != f->file || f->phase != 5 || f->releases)
		f->callback_bad = true;
}

static const struct vm_operations_struct close_ops = { .close = test_close };
static const struct vm_operations_struct plain_ops;

static int test_mmap(struct file *file, struct vm_area_struct *vma)
{
	struct merge_fixture *f = file->private_data;
	bool close = f->mode == RUSIX_MIDDLE_CLOSE ? vma->vm_pgoff == 1 :
		(f->mode == RUSIX_NEXT_CLOSE || f->mode == RUSIX_NEW_NEXT_CLOSE) &&
		vma->vm_pgoff == 2;

	vma->vm_private_data = f;
	vma->vm_ops = close ? &close_ops : &plain_ops;
	return 0;
}

static int test_release(struct inode *inode, struct file *file)
{
	struct merge_fixture *f = file->private_data;

	f->releases++;
	if (f->phase != 6 || f->closes != f->expected_closes || f->releases != 1)
		f->callback_bad = true;
	return 0;
}

static const struct file_operations test_fops = { .mmap = test_mmap, .release = test_release };

static struct vm_counts read_counts(struct mm_struct *mm)
{
	return (struct vm_counts) {
		.total = mm->total_vm, .exec = mm->exec_vm, .stack = mm->stack_vm,
		.data = mm->data_vm, .locked = mm->locked_vm,
	};
}

static bool same_counts(struct vm_counts a, struct vm_counts b)
{
	return a.total == b.total && a.exec == b.exec && a.stack == b.stack &&
		a.data == b.data && a.locked == b.locked;
}

static bool same_record(const struct vma_record *a, const struct vma_record *b)
{
	return a->pointer == b->pointer && a->start == b->start && a->end == b->end &&
		a->pgoff == b->pgoff && a->flags == b->flags && a->file == b->file &&
		a->ops == b->ops;
}

/* A complete private-tree walk: unsupported actual flags on ANY mapping fail,
 * even if MAP_NORESERVE was requested and ignored by overcommit policy.
 */
static int snapshot(struct mm_struct *mm, struct vma_record *records)
{
	VMA_ITERATOR(vmi, mm, 0);
	struct vm_area_struct *vma;
	unsigned int count = 0;

	mmap_assert_write_locked(mm);
	for_each_vma(vmi, vma) {
		if (count == SNAP_LIMIT || vma->vm_flags & FORBIDDEN ||
		    vma->vm_flags & VM_WRITE || vma->vm_start >= vma->vm_end)
			return -EINVAL;
		records[count++] = (struct vma_record) {
			.pointer = (unsigned long)vma, .start = vma->vm_start, .end = vma->vm_end,
			.pgoff = vma->vm_pgoff, .flags = vma->vm_flags,
			.file = (unsigned long)vma->vm_file, .ops = (unsigned long)vma->vm_ops,
		};
	}
	return count;
}

static bool counts_match_tree(struct mm_struct *mm, struct vma_record *records, unsigned int count)
{
	struct vm_counts expected = {};
	unsigned int i;

	for (i = 0; i < count; i++) {
		unsigned long pages = (records[i].end - records[i].start) >> PAGE_SHIFT;
		vm_flags_t flags = records[i].flags;

		expected.total += pages;
		if (is_exec_mapping(flags))
			expected.exec += pages;
		else if (is_stack_mapping(flags))
			expected.stack += pages;
		else if (is_data_mapping(flags))
			expected.data += pages;
	}
	return same_counts(read_counts(mm), expected);
}

static int map_one(struct merge_fixture *f, unsigned long start, unsigned long pages,
		   unsigned long prot, bool file, unsigned long offset)
{
	unsigned long result = vm_mmap(file ? f->file : NULL, start, pages << PAGE_SHIFT,
		prot, MAP_PRIVATE | MAP_FIXED | MAP_NORESERVE | (file ? 0 : MAP_ANONYMOUS),
		offset << PAGE_SHIFT);

	return result == start ? 0 : -EINVAL;
}

static int setup_maps(struct merge_fixture *f)
{
	unsigned int i;
	bool file = is_file_case(f->mode);

	/* R/RX/R avoids writable anonymous charges even when MAP_NORESERVE is
	 * ignored; actual flags are still checked over the complete tree.
	 */
	for (i = 0; i < FILLERS; i++)
		if (map_one(f, TARGET + (16 + i * 2) * PAGE_SIZE, 1, PROT_READ, false, 0))
			return -EINVAL;
	if (is_shrink(f->mode))
		return map_one(f, TARGET, 3, PROT_READ, false, 0);
	if (map_one(f, TARGET, 1, PROT_READ, file, 0))
		return -EINVAL;
	if (is_existing(f->mode) && map_one(f, TARGET + PAGE_SIZE, 1,
					   PROT_READ | PROT_EXEC, file, 1))
		return -EINVAL;
	return map_one(f, TARGET + 2 * PAGE_SIZE, 1, PROT_READ, file, 2);
}

static void remove_expected(struct merge_fixture *f, unsigned int index)
{
	memmove(&f->expected[index], &f->expected[index + 1],
		(f->expected_count - index - 1) * sizeof(f->expected[0]));
	f->expected_count--;
}

/* This oracle is fixed BEFORE production invocation; never normalize observed
 * buggy topology or counters into a passing result.
 */
static int plan_expected(struct merge_fixture *f)
{
	unsigned int region = is_shrink(f->mode) ? 1 : is_existing(f->mode) ? 3 : 2;

	if (f->before_count != FILLERS + region || f->before[0].start != TARGET)
		return -EINVAL;
	if (is_shrink(f->mode)) {
		if (f->before[0].end != TARGET + 3 * PAGE_SIZE)
			return -EINVAL;
	} else if (f->before[0].end != TARGET + PAGE_SIZE ||
		   f->before[region - 1].start != TARGET + 2 * PAGE_SIZE ||
		   f->before[region - 1].end != TARGET + 3 * PAGE_SIZE) {
		return -EINVAL;
	}
	if (region == 3 && (f->before[1].start != TARGET + PAGE_SIZE ||
			   f->before[1].end != TARGET + 2 * PAGE_SIZE))
		return -EINVAL;
	if (!is_shrink(f->mode) && (f->before[region - 1].pgoff != f->before[0].pgoff + 2 ||
				   f->before[region - 1].flags != f->before[0].flags))
		return -EINVAL;
	if (region == 3 && ((f->before[1].flags ^ f->before[0].flags) != VM_EXEC ||
			   f->before[1].pgoff != f->before[0].pgoff + 1))
		return -EINVAL;
	memcpy(f->expected, f->before, f->before_count * sizeof(f->before[0]));
	f->expected_count = f->before_count;
	if (is_failure(f->mode) || f->mode == RUSIX_MIDDLE_CLOSE)
		return 0;
	if (is_shrink(f->mode)) {
		f->expected[0].start += PAGE_SIZE;
		f->expected[0].pgoff++;
	} else if (is_existing(f->mode)) {
		if (f->mode == RUSIX_NEXT_CLOSE) {
			f->expected[0].end = TARGET + 2 * PAGE_SIZE;
			remove_expected(f, 1);
		} else {
			f->expected[0].end = TARGET + 3 * PAGE_SIZE;
			remove_expected(f, 2);
			remove_expected(f, 1);
		}
	} else {
		f->expected[0].end = TARGET + (f->mode == RUSIX_NEW_NEXT_CLOSE ? 2 : 3) * PAGE_SIZE;
		if (f->mode != RUSIX_NEW_NEXT_CLOSE)
			remove_expected(f, 1);
	}
	return 0;
}

static int observe_transaction(struct merge_fixture *f)
{
	struct rusix_merge_observation *o = &f->outcome.observed;
	bool clone = !is_file_case(f->mode) && !is_shrink(f->mode);

	if (o->malformed)
		return -EINVAL;
	if (clone) {
		if (o->clone_begin != 1 || o->clone_end != 1 || o->clone_nowait != 1)
			return -EINVAL;
		if (is_clone_failure(f->mode)) {
			if (o->clone_retry != 1 || o->clone_result != -ENOMEM || !o->clone_cleared ||
			    o->maple_begin || o->maple_end || o->maple_injected)
				return -EINVAL;
			return 0;
		}
		if (o->clone_retry || o->clone_result || o->clone_cleared)
			return -EINVAL;
	} else if (o->clone_begin || o->clone_end || o->clone_nowait || o->clone_retry) {
		return -EINVAL;
	}
	if (f->mode == RUSIX_MIDDLE_CLOSE)
		return o->maple_begin || o->maple_end || o->maple_injected ? -EINVAL : 0;
	if (o->maple_begin != 1 || o->maple_end != 1)
		return -EINVAL;
	if (is_failure(f->mode)) {
		if (o->maple_injected != 1 || !o->node_request ||
		    o->maple_result != -ENOMEM || !o->maple_reset)
			return -EINVAL;
	} else if (o->maple_injected || o->maple_result) {
		return -EINVAL;
	}
	return 0;
}

static int check_after(struct merge_fixture *f, struct vm_area_struct *prev)
{
	struct mm_struct *mm = f->mm;
	unsigned int i;
	int count = snapshot(mm, f->after);

	f->after_count = count;

	if (count < 0 || count != f->expected_count || mm->map_count != count ||
	    f->closes || f->releases || f->callback_bad ||
	    !same_counts(read_counts(mm), f->counts))
		return -EINVAL;
	for (i = 0; i < count; i++)
		if (!same_record(&f->after[i], &f->expected[i]))
			return -EINVAL;
	if (f->file && file_count(f->file) != f->before_file_count -
						(f->before_count - f->expected_count))
		return -EINVAL;
	if (f->anon) {
		bool valid;

		anon_vma_lock_read(f->anon);
		valid = f->anon->num_active_vmas == f->before_active &&
			f->anon->num_children == f->before_children;
		anon_vma_unlock_read(f->anon);
		/* prev is always the live target, even if middle/next were retired. */
		if (!valid || (is_failure(f->mode) ?
		    prev->anon_vma || !list_empty(&prev->anon_vma_chain) :
		    prev->anon_vma != f->anon || !list_is_singular(&prev->anon_vma_chain)))
			return -EINVAL;
	}
	if (observe_transaction(f))
		return -EINVAL;
	/* Caller-owned accounting: fixed scalars from the predeclared transaction,
	 * applied ONLY after exact topology and unchanged policy counters passed.
	 */
	if (!is_failure(f->mode) && f->mode != RUSIX_MIDDLE_CLOSE) {
		if (is_shrink(f->mode)) {
			vm_stat_account(mm, f->before[0].flags, -1);
		} else if (is_existing(f->mode)) {
			vm_stat_account(mm, f->before[1].flags, -1);
			vm_stat_account(mm, f->before[0].flags, 1);
		} else {
			vm_stat_account(mm, f->before[0].flags, 1);
		}
	}
	f->counts_after = read_counts(mm);
	return counts_match_tree(mm, f->expected, f->expected_count) ? 0 : -EINVAL;
}

static int merge_worker(void *ptr)
{
	struct merge_fixture *f = ptr;
	struct mm_struct *mm = NULL;
	struct vm_area_struct *prev, *middle, *next, *source;
	bool adopted = false, locked = false, retained = false;
	int count;

	mutex_lock(&worker_lock);
	f->status = -EIO;
	f->phase = 1;
	mm = mm_alloc();
	if (!mm) {
		f->status = -ENOMEM;
		goto done;
	}
	f->mm = mm;
	if (atomic_read(&mm->mm_users) != 1 || atomic_read(&mm->mm_count) != 1 ||
	    !mtree_empty(&mm->mm_mt))
		goto uncertain;
	mmgrab(mm);
	if (is_file_case(f->mode)) {
		f->file = anon_inode_create_getfile("rusix_merge", &test_fops, f, O_RDONLY, NULL);
		if (IS_ERR(f->file)) {
			f->file = NULL;
			goto uncertain;
		}
		f->expected_closes = f->mode == RUSIX_BOTH_SUCCESS ? 0 : 1;
	}
	kthread_use_mm(mm);
	adopted = true;
	if (setup_maps(f))
		goto uncertain;
	mmap_write_lock(mm);
	locked = true;
	f->phase = 2;
	count = snapshot(mm, f->before);
	if (count < 0 || mm->map_count != count)
		goto uncertain;
	f->before_count = count;
	f->counts = read_counts(mm);
	if (!counts_match_tree(mm, f->before, count) || plan_expected(f))
		goto uncertain;
	prev = find_vma(mm, TARGET);
	middle = is_existing(f->mode) ? find_vma(mm, TARGET + PAGE_SIZE) : NULL;
	next = is_shrink(f->mode) ? NULL : find_vma(mm, TARGET + 2 * PAGE_SIZE);
	if (!prev || (is_existing(f->mode) && !middle) || (!is_shrink(f->mode) && !next))
		goto uncertain;
	if (f->file) {
		f->before_file_count = file_count(f->file);
		if (f->before_file_count != (is_existing(f->mode) ? 4 : 3))
			goto uncertain;
	} else if (!is_shrink(f->mode)) {
		source = is_existing(f->mode) ? middle : next;
		if (prev->anon_vma || !list_empty(&prev->anon_vma_chain) ||
		    source->anon_vma || !list_empty(&source->anon_vma_chain))
			goto uncertain;
		vma_start_write(source);
		if (anon_vma_prepare(source) || !source->anon_vma ||
		    !list_is_singular(&source->anon_vma_chain))
			goto uncertain;
		f->anon = source->anon_vma;
		get_anon_vma(f->anon);
		anon_vma_lock_read(f->anon);
		f->before_active = f->anon->num_active_vmas;
		f->before_children = f->anon->num_children;
		anon_vma_unlock_read(f->anon);
		if (f->before_active != 1 || f->before_children != 1)
			goto uncertain;
	}
	f->phase = 3;
	if (rusix_merge_test_dispatch(mm, f->mode, prev, middle, next, &f->outcome))
		goto uncertain;
	f->phase = 4;
	if (check_after(f, prev))
		goto uncertain;
	mmap_write_unlock(mm);
	locked = false;
	kthread_unuse_mm(mm);
	adopted = false;
	f->phase = 5;
	mmput(mm);
	/* mmgrab holds storage only, not retired VMAs. Native teardown may leave
	 * map_count stale, and lazy-TLB references need not have exhausted yet.
	 */
	if (atomic_read(&mm->mm_users) || atomic_read(&mm->mm_count) < 1 ||
	    !mtree_empty(&mm->mm_mt) || f->callback_bad ||
	    f->closes != f->expected_closes || f->releases)
		goto uncertain;
	if (f->anon) {
		bool valid;

		anon_vma_lock_read(f->anon);
		valid = f->anon->num_active_vmas == 0;
		anon_vma_unlock_read(f->anon);
		if (!valid)
			goto uncertain;
		put_anon_vma(f->anon);
		f->anon = NULL;
	}
	mmdrop(mm);
	f->mm = NULL;
	if (f->file) {
		if (file_count(f->file) != 1)
			goto uncertain;
		f->phase = 6;
		__fput_sync(f->file);
		f->file = NULL;
		if (f->releases != 1 || f->callback_bad)
			goto uncertain;
	}
	f->cleanup = true;
	f->status = 0;
	goto done;
uncertain:
	/* No reconstructed accounting, guessed second put, global flush or forced
	 * teardown after a failed invariant. Keep callback and native ownership.
	 */
	if (locked)
		mmap_write_unlock(mm);
	if (adopted)
		kthread_unuse_mm(mm);
	retained = true;
done:
	mutex_unlock(&worker_lock);
	complete_all(&f->done);
	if (!retained)
		fixture_put(f);
	return 0;
}

static void run_case(struct kunit *test, enum rusix_merge_case mode)
{
	struct merge_fixture *f;
	struct task_struct *task;
	struct rusix_merge_observation *o;
	unsigned int i;

	f = kzalloc(sizeof(*f), GFP_KERNEL);
	KUNIT_ASSERT_NOT_NULL(test, f);
	refcount_set(&f->refs, 2);
	init_completion(&f->done);
	f->mode = mode;
	task = kthread_create(merge_worker, f, "rusix_vma_merge");
	if (IS_ERR(task)) {
		kfree(f);
		KUNIT_FAIL(test, "private worker creation failed");
		return;
	}
	f->task = task;
	get_task_struct(task);
	wake_up_process(task);
	if (!wait_for_completion_timeout(&f->done, msecs_to_jiffies(10000))) {
		KUNIT_FAIL(test, "private worker timeout; worker references retained");
		fixture_put(f);
		return;
	}
	/* Completion publishes results. Never inspect mutable worker fields on a
	 * timeout. Print native observations on failures as well as successes.
	 */
	o = &f->outcome.observed;
	kunit_info(test, "mode=%u phase=%d status=%d cleanup=%d ret=%lx err=%d state=%d cursor=%lx\n",
		   mode, f->phase, f->status, f->cleanup, f->outcome.returned,
		   f->outcome.error, f->outcome.state, f->outcome.cursor);
	kunit_info(test, "clone=%u/%u allocations=%u/%u ret=%d cleared=%d maple=%u/%u injected=%u nodes=%u store=%u ret=%d reset=%d malformed=%d close=%u release=%u\n",
		   o->clone_begin, o->clone_end, o->clone_nowait, o->clone_retry,
		   o->clone_result, o->clone_cleared, o->maple_begin, o->maple_end,
		   o->maple_injected, o->node_request, o->store_type, o->maple_result,
		   o->maple_reset, o->malformed, f->closes, f->releases);
	kunit_info(test, "before=%u expected=%u after=%d total=%lu/%lu exec=%lu/%lu stack=%lu/%lu data=%lu/%lu locked=%lu/%lu\n",
		   f->before_count, f->expected_count, f->after_count,
		   f->counts.total, f->counts_after.total, f->counts.exec, f->counts_after.exec,
		   f->counts.stack, f->counts_after.stack, f->counts.data, f->counts_after.data,
		   f->counts.locked, f->counts_after.locked);
	for (i = 0; i < f->before_count; i++) {
		struct vma_record *r = &f->before[i];

		kunit_info(test, "before[%u]=%lx:%lx-%lx off=%lx flags=%lx file=%lx ops=%lx\n",
			   i, r->pointer, r->start, r->end, r->pgoff, r->flags, r->file, r->ops);
	}
	for (i = 0; f->after_count > 0 && i < f->after_count; i++) {
		struct vma_record *r = &f->after[i];

		kunit_info(test, "after[%u]=%lx:%lx-%lx off=%lx flags=%lx file=%lx ops=%lx\n",
			   i, r->pointer, r->start, r->end, r->pgoff, r->flags, r->file, r->ops);
	}
	KUNIT_EXPECT_EQ(test, f->status, 0);
	KUNIT_EXPECT_TRUE(test, f->cleanup);
	fixture_put(f);
}

static void existing_clone_fail_report(struct kunit *test)
{
	run_case(test, RUSIX_EXISTING_CLONE_REPORT);
}

static void existing_clone_fail_silent(struct kunit *test)
{
	run_case(test, RUSIX_EXISTING_CLONE_SILENT);
}

static void existing_prealloc_fail_report(struct kunit *test)
{
	run_case(test, RUSIX_EXISTING_PREALLOC_REPORT);
}

static void existing_prealloc_fail_silent(struct kunit *test)
{
	run_case(test, RUSIX_EXISTING_PREALLOC_SILENT);
}

static void new_prealloc_fail_report(struct kunit *test)
{
	run_case(test, RUSIX_NEW_PREALLOC_REPORT);
}

static void new_prealloc_fail_silent(struct kunit *test)
{
	run_case(test, RUSIX_NEW_PREALLOC_SILENT);
}

static void expand_clone_fail(struct kunit *test)
{
	run_case(test, RUSIX_EXPAND_CLONE);
}

static void expand_prealloc_fail_report(struct kunit *test)
{
	run_case(test, RUSIX_EXPAND_PREALLOC_REPORT);
}

static void expand_prealloc_fail_silent(struct kunit *test)
{
	run_case(test, RUSIX_EXPAND_PREALLOC_SILENT);
}

static void shrink_prealloc_fail(struct kunit *test)
{
	run_case(test, RUSIX_SHRINK_PREALLOC);
}

static void existing_middle_close_refusal(struct kunit *test)
{
	run_case(test, RUSIX_MIDDLE_CLOSE);
}

static void existing_next_close_reduction(struct kunit *test)
{
	run_case(test, RUSIX_NEXT_CLOSE);
}

static void existing_both_success(struct kunit *test)
{
	run_case(test, RUSIX_BOTH_SUCCESS);
}

static void new_next_close_reduction(struct kunit *test)
{
	run_case(test, RUSIX_NEW_NEXT_CLOSE);
}

static void existing_success_control(struct kunit *test)
{
	run_case(test, RUSIX_EXISTING_SUCCESS);
}

static void new_success_control(struct kunit *test)
{
	run_case(test, RUSIX_NEW_SUCCESS);
}

static void expand_success_control(struct kunit *test)
{
	run_case(test, RUSIX_EXPAND_SUCCESS);
}

static void shrink_success_control(struct kunit *test)
{
	run_case(test, RUSIX_SHRINK_SUCCESS);
}

static struct kunit_case merge_cases[] = {
	KUNIT_CASE(existing_clone_fail_report),
	KUNIT_CASE(existing_clone_fail_silent),
	KUNIT_CASE(existing_prealloc_fail_report),
	KUNIT_CASE(existing_prealloc_fail_silent),
	KUNIT_CASE(new_prealloc_fail_report),
	KUNIT_CASE(new_prealloc_fail_silent),
	KUNIT_CASE(expand_clone_fail),
	KUNIT_CASE(expand_prealloc_fail_report),
	KUNIT_CASE(expand_prealloc_fail_silent),
	KUNIT_CASE(shrink_prealloc_fail),
	KUNIT_CASE(existing_middle_close_refusal),
	KUNIT_CASE(existing_next_close_reduction),
	KUNIT_CASE(existing_both_success),
	KUNIT_CASE(new_next_close_reduction),
	KUNIT_CASE(existing_success_control),
	KUNIT_CASE(new_success_control),
	KUNIT_CASE(expand_success_control),
	KUNIT_CASE(shrink_success_control),
	{}
};

static struct kunit_suite merge_suite = {
	.name = "rusix_vma_merge",
	.test_cases = merge_cases,
};

kunit_test_suite(merge_suite);
