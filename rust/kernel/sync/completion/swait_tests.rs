// SPDX-License-Identifier: GPL-2.0
//! Generic swait consumers and queue structure, tested on dedicated kthreads.
//! Acknowledgment is not a join; callback-owned Arcs protect delayed execution.

use super::Completion;
use crate::{
    bindings,
    ffi::{c_int, c_long, c_ulong, c_void},
    prelude::*,
    sync::{
        atomic::{Atomic, Relaxed},
        Arc,
    },
    time::{Delta, Instant, Monotonic},
    types::{NotThreadSafe, Opaque},
};
use core::ptr::{addr_of_mut, null_mut};

// Private pinned scheduler ABI. Only pointers cross this boundary; the waiter
// allocation remains bindings::swait_queue. Opaque argument avoids recursively
// treating configuration-empty task_struct members as by-value FFI types.
unsafe extern "C" {
    fn __prepare_to_swait(queue: *mut bindings::swait_queue_head, waiter: *mut c_void);
}

#[pin_data]
struct Queue {
    #[pin]
    inner: Opaque<bindings::swait_queue_head>,
}

// SAFETY: Pinned storage never moves. All mutable links are protected by the
// queue's raw lock and shared observations follow the original swait protocol.
unsafe impl Send for Queue {}
// SAFETY: The same raw-lock protocol serializes access from all fixture users.
unsafe impl Sync for Queue {}

impl Queue {
    fn new() -> impl PinInit<Self> {
        pin_init!(Self {
            inner <- Opaque::ffi_init(|p| {
                // SAFETY: Exclusive uninitialized final pinned storage.
                unsafe { bindings::swait_test_init(p) };
            }),
        })
    }

    fn raw(&self) -> *mut bindings::swait_queue_head {
        self.inner.get()
    }

    // Private call sites never recursively lock this queue or sleep while held.
    fn lock(&self) -> QueueGuard<'_> {
        // SAFETY: self pins initialized storage; the private callers exclude
        // recursive acquisition. The borrowed guard cannot outlive the queue.
        let flags = unsafe { bindings::swait_test_lock(self.raw()) };
        QueueGuard {
            queue: self,
            flags,
            _task: NotThreadSafe,
        }
    }

    fn count(&self) -> u32 {
        let _guard = self.lock();
        // SAFETY: Initialized queue is locked; null nodes request count only.
        (unsafe { bindings::swait_test_snapshot_locked(self.raw(), null_mut(), null_mut()) }) & 3
    }

    fn wake_one(&self) {
        // SAFETY: Initialized queue lives throughout this ordinary locking
        // wrapper. Any linked worker independently retains its own fixture Arc.
        unsafe { bindings::swake_up_one(self.raw()) };
    }
}

struct QueueGuard<'a> {
    queue: &'a Queue,
    flags: c_ulong,
    _task: NotThreadSafe,
}
impl Drop for QueueGuard<'_> {
    fn drop(&mut self) {
        // SAFETY: This same-task guard owns the exact initialized lock; no path
        // releases it separately. Queue storage remains borrowed through unlock.
        unsafe { bindings::swait_test_unlock(self.queue.raw(), self.flags) };
    }
}

#[derive(Clone, Copy)]
enum Mode {
    Repeat,
    Explicit,
    Generic,
}

#[pin_data]
struct Worker {
    queue: Arc<Queue>,
    #[pin]
    waiter: Opaque<bindings::swait_queue>,
    #[pin]
    finished: Completion,
    condition: Atomic<u32>,
    result: Atomic<i64>,
    elapsed: Atomic<u64>,
    mode: Mode,
    timeout_ms: u32,
}

// SAFETY: Queue and completion fields use their original synchronization; node
// mutation belongs to one dedicated callback under queue.lock. Controller node
// observations also hold that lock and retain the Arc. Other state is immutable
// or LKMM atomic. Pinning keeps all C-visible links/locks at stable addresses.
unsafe impl Send for Worker {}
// SAFETY: The same synchronization and single callback ownership apply across
// shared controller/callback references; no Rust mutable reference covers links.
unsafe impl Sync for Worker {}

impl Worker {
    fn new(queue: Arc<Queue>, mode: Mode, timeout_ms: u32) -> impl PinInit<Self> {
        pin_init!(Self {
            queue,
            waiter <- Opaque::ffi_init(|p: *mut bindings::swait_queue| {
                // SAFETY: Exclusive final pinned storage; initialize every
                // field and form self-links only after the final address exists.
                unsafe {
                    addr_of_mut!((*p).task).write(null_mut());
                    let node = addr_of_mut!((*p).task_list);
                    addr_of_mut!((*node).next).write(node);
                    addr_of_mut!((*node).prev).write(node);
                }
            }),
            finished <- Completion::new(),
            condition: Atomic::new(0),
            result: Atomic::new(i64::MIN),
            elapsed: Atomic::new(0),
            mode,
            timeout_ms,
        })
    }

    fn finish_observed(&self) -> bool {
        // SAFETY: Controller is sleepable with IRQs enabled; its Arc retains
        // initialized pinned acknowledgment storage during the finite wait.
        unsafe {
            bindings::wait_for_completion_timeout(
                self.finished.as_raw(),
                crate::time::msecs_to_jiffies(1000),
            ) != 0
        }
    }

    fn release(&self) {
        self.condition.store(1, Relaxed);
        self.queue.wake_one();
    }
}

struct TaskRef(*mut bindings::task_struct);
impl Drop for TaskRef {
    fn drop(&mut self) {
        // SAFETY: Successful creation supplied one independent task reference;
        // callbacks retain their own lifetime and storage separately.
        unsafe { bindings::put_task_struct(self.0) };
    }
}

fn spawn(worker: &Arc<Worker>) -> Result<TaskRef> {
    let data = Arc::into_raw(worker.clone()).cast_mut().cast();
    // SAFETY: One Arc reference transfers to the sole standalone callback on
    // success. On failure the stopped-thread creator never invokes that callback.
    let task = unsafe { bindings::completion_test_kthread_create(Some(run_worker), data) };
    let task = match crate::error::from_err_ptr(task) {
        Ok(task) => TaskRef(task),
        Err(error) => {
            // SAFETY: Creation failed, so reclaim the unconsumed raw reference.
            unsafe { drop(Arc::<Worker>::from_raw(data.cast())) };
            return Err(error);
        }
    };
    // SAFETY: Extra task reference protects the stopped task. There is no
    // fallible/early-return operation between successful creation and this wake.
    unsafe { bindings::wake_up_process(task.0) };
    Ok(task)
}

fn repeat_in_worker(worker: &Worker) -> c_long {
    let queue = worker.queue.raw();
    let waiter = worker.waiter.get();
    let _guard = worker.queue.lock();
    // SAFETY: This dedicated task owns its pinned waiter; queue.lock is held.
    // Repeated prepare must leave one node, with current recorded as its task.
    unsafe { __prepare_to_swait(queue, waiter.cast()) };
    // SAFETY: Same pinned waiter and held queue lock; duplicate prepare is legal.
    unsafe { __prepare_to_swait(queue, waiter.cast()) };
    // SAFETY: Held queue lock and live separately owned node permit observation.
    let enrolled = unsafe { bindings::swait_test_snapshot_locked(queue, waiter, null_mut()) };
    // SAFETY: This is the dedicated callback's state, not the KUnit controller;
    // no scheduling/fallible operation occurs before finish restores RUNNING.
    unsafe { bindings::__set_current_state(bindings::TASK_UNINTERRUPTIBLE) };
    // SAFETY: Current owns this initialized waiter and queue.lock; finish unlinks.
    unsafe { bindings::__finish_swait(queue, waiter) };
    // SAFETY: Current-only marked read after finish, under the same lock.
    let running = unsafe { bindings::swait_test_current_state() } == bindings::TASK_RUNNING;
    // SAFETY: Node remains initialized/self-linked; repeated finish is legal.
    unsafe { bindings::__finish_swait(queue, waiter) };
    // SAFETY: Queue lock still held, node retained; snapshot does not mutate it.
    let empty = unsafe { bindings::swait_test_snapshot_locked(queue, waiter, null_mut()) };
    // SAFETY: This only observes the calling dedicated task's state.
    let still_running = unsafe { bindings::swait_test_current_state() } == bindings::TASK_RUNNING;
    c_long::from(
        enrolled == (1 | (1 << 4) | (1 << 10))
            && empty == ((1 << 8) | (1 << 10) | (1 << 11))
            && running
            && still_running,
    )
}

fn explicit_wait(worker: &Worker, mut timeout: c_long) -> c_long {
    loop {
        // SAFETY: This dedicated task alone enrolls its own pinned node. Queue
        // is initialized/retained; the C wrapper takes its lock and sets state.
        unsafe {
            bindings::prepare_to_swait_exclusive(
                worker.queue.raw(),
                worker.waiter.get(),
                bindings::TASK_UNINTERRUPTIBLE as c_int,
            )
        };
        if worker.condition.load(Relaxed) != 0 || timeout == 0 {
            break;
        }
        // SAFETY: Current state/enrollment were set above. No lock is held;
        // timeout is finite and the scheduler returns in this same task.
        timeout = unsafe { bindings::schedule_timeout(timeout) };
    }
    // SAFETY: Current owns the initialized pinned node and retained queue; this
    // original generic wrapper restores RUNNING and removes any remaining link.
    unsafe { bindings::finish_swait(worker.queue.raw(), worker.waiter.get()) };
    if worker.condition.load(Relaxed) != 0 {
        if timeout == 0 {
            1
        } else {
            timeout
        }
    } else {
        0
    }
}

unsafe extern "C" fn run_worker(data: *mut c_void) -> c_int {
    // SAFETY: Creator transfers exactly one raw Arc to this sole callback;
    // no kthread_stop path can bypass callback execution after successful create.
    let worker = unsafe { Arc::<Worker>::from_raw(data.cast()) };
    let timeout = crate::time::msecs_to_jiffies(worker.timeout_ms) as c_long;
    // SAFETY: Marked global read, with no Rust reference to C-mutated jiffies.
    let before = unsafe { bindings::completion_test_jiffies() };
    let result = match worker.mode {
        Mode::Repeat => repeat_in_worker(&worker),
        Mode::Explicit => explicit_wait(&worker, timeout),
        Mode::Generic => {
            // SAFETY: Sleepable standalone task; the queue and marked condition
            // are Arc-owned through return. This is the original C consumer macro,
            // whose local stack waiter is unlinked on all normal return paths.
            unsafe {
                bindings::swait_test_event_timeout(
                    worker.queue.raw(),
                    worker.condition.as_ptr(),
                    timeout,
                )
            }
        }
    };
    // SAFETY: Same marked global read; bounded intervals make wrapping delta valid.
    let elapsed = unsafe { bindings::completion_test_jiffies() }.wrapping_sub(before);
    worker.elapsed.store(elapsed as u64, Relaxed);
    worker.result.store(result as i64, Relaxed);
    // Arc pins acknowledgment storage; no queue/node access follows this
    // notification, and the callback retains its Arc through return.
    worker.finished.complete_all();
    0
}

fn observe_count(queue: &Queue, count: u32) -> bool {
    for _ in 0..100 {
        if queue.count() == count {
            return true;
        }
        crate::time::delay::fsleep(Delta::from_millis(10));
    }
    false
}

#[macros::kunit_tests(rusix_completion_swait)]
mod tests {
    use super::*;

    #[test]
    fn empty_wake_preserves_initialized_queue() -> Result {
        let queue = Arc::pin_init(Queue::new(), GFP_KERNEL)?;
        // SAFETY: Observation of this current context only, without changing it.
        let before = unsafe { bindings::swait_test_irqs_disabled() };
        let initial;
        let empty;
        let during;
        {
            let _guard = queue.lock();
            // SAFETY: Initialized queue is locked; observe both initial self-links.
            initial = unsafe {
                bindings::swait_test_snapshot_locked(queue.raw(), null_mut(), null_mut())
            };
            // SAFETY: Initialized empty queue, raw lock held with IRQs disabled.
            unsafe { bindings::swake_up_locked(queue.raw(), 0) };
            // SAFETY: Current-context observation, while the raw lock is held.
            during = unsafe { bindings::swait_test_irqs_disabled() };
            // SAFETY: Same held lock; null nodes request count/head-link state.
            empty = unsafe {
                bindings::swait_test_snapshot_locked(queue.raw(), null_mut(), null_mut())
            };
        }
        queue.wake_one();
        let after_wrapper;
        {
            let _guard = queue.lock();
            // SAFETY: Queue is locked again; check both self-links after the
            // original C locking wrapper, without changing queue policy.
            after_wrapper = unsafe {
                bindings::swait_test_snapshot_locked(queue.raw(), null_mut(), null_mut())
            };
        }
        // SAFETY: Current-context IRQ observation after guard restored its flags.
        let after = unsafe { bindings::swait_test_irqs_disabled() };
        assert_eq!(initial, 1 << 11);
        assert_eq!(empty, 1 << 11);
        assert_eq!(after_wrapper, 1 << 11);
        assert_ne!(during, 0);
        assert_eq!(queue.count(), 0);
        assert_eq!(before, after);
        Ok(())
    }

    #[test]
    fn repeated_prepare_keeps_single_enrollment_and_finish_restores_state() -> Result {
        let queue = Arc::pin_init(Queue::new(), GFP_KERNEL)?;
        let worker = Arc::pin_init(Worker::new(queue.clone(), Mode::Repeat, 10000), GFP_KERNEL)?;
        let started = Instant::<Monotonic>::now();
        let task = spawn(&worker)?;
        let finished = worker.finish_observed();
        worker.release();
        drop(task);
        assert!(finished);
        assert!(started.elapsed().as_millis() < 5000);
        assert_eq!(worker.result.load(Relaxed), 1);
        assert_eq!(queue.count(), 0);
        Ok(())
    }

    #[test]
    fn queued_wake_removes_fifo_head_before_second_waiter() -> Result {
        let queue = Arc::pin_init(Queue::new(), GFP_KERNEL)?;
        let first = Arc::pin_init(
            Worker::new(queue.clone(), Mode::Explicit, 10000),
            GFP_KERNEL,
        )?;
        let second = Arc::pin_init(
            Worker::new(queue.clone(), Mode::Explicit, 10000),
            GFP_KERNEL,
        )?;
        let started = Instant::<Monotonic>::now();
        let task_first = spawn(&first)?;
        let first_enrolled = observe_count(&queue, 1);
        let task_second = match spawn(&second) {
            Ok(task) => task,
            Err(error) => {
                first.release();
                return Err(error);
            }
        };
        let both_enrolled = observe_count(&queue, 2);
        let before;
        let after;
        {
            let _guard = queue.lock();
            // SAFETY: Queue locked; both initialized pinned nodes retained by
            // controller Arcs even if a callback has already finished.
            before = unsafe {
                bindings::swait_test_snapshot_locked(
                    queue.raw(),
                    first.waiter.get(),
                    second.waiter.get(),
                )
            };
            // Conditions and wake/snapshot share the lock. Neither worker can
            // remove an enrolled node through finish_swait before this snapshot.
            first.condition.store(1, Relaxed);
            second.condition.store(1, Relaxed);
            // SAFETY: Queue lock held; every linked node belongs to a live worker.
            unsafe { bindings::swake_up_locked(queue.raw(), 0) };
            // SAFETY: Same held lock and retained nodes; observe removal order,
            // not task execution order. No saved task pointer is dereferenced.
            after = unsafe {
                bindings::swait_test_snapshot_locked(
                    queue.raw(),
                    first.waiter.get(),
                    second.waiter.get(),
                )
            };
        }
        // Unconditional cleanup before assertions; late callbacks own their Arcs.
        first.release();
        second.release();
        let finished_first = first.finish_observed();
        let finished_second = second.finish_observed();
        drop(task_first);
        drop(task_second);
        assert!(first_enrolled && both_enrolled);
        assert!(finished_first && finished_second);
        assert!(started.elapsed().as_millis() < 5000);
        assert_eq!(before, 2 | (1 << 4) | (1 << 6) | (1 << 7));
        assert_eq!(after, 1 | (1 << 5) | (1 << 7) | (1 << 8));
        assert!(first.result.load(Relaxed) > 0);
        assert!(second.result.load(Relaxed) > 0);
        assert_eq!(queue.count(), 0);
        Ok(())
    }

    #[test]
    fn generic_swait_event_observes_condition_and_unlinks() -> Result {
        let queue = Arc::pin_init(Queue::new(), GFP_KERNEL)?;
        let worker = Arc::pin_init(Worker::new(queue.clone(), Mode::Generic, 10000), GFP_KERNEL)?;
        let started = Instant::<Monotonic>::now();
        let task = spawn(&worker)?;
        let enrolled = observe_count(&queue, 1);
        worker.release();
        let finished = worker.finish_observed();
        worker.release();
        drop(task);
        assert!(enrolled && finished);
        assert!(started.elapsed().as_millis() < 5000);
        assert!(worker.result.load(Relaxed) > 0);
        assert_eq!(queue.count(), 0);
        Ok(())
    }

    #[test]
    fn generic_swait_timeout_unlinks_before_late_wake() -> Result {
        let queue = Arc::pin_init(Queue::new(), GFP_KERNEL)?;
        let worker = Arc::pin_init(Worker::new(queue.clone(), Mode::Generic, 20), GFP_KERNEL)?;
        let started = Instant::<Monotonic>::now();
        let task = spawn(&worker)?;
        let finished = worker.finish_observed();
        let count_before_cleanup = queue.count();
        queue.wake_one();
        let count_after_late_wake = queue.count();
        worker.release();
        drop(task);
        assert!(finished);
        assert!(started.elapsed().as_millis() < 5000);
        assert_eq!(worker.result.load(Relaxed), 0);
        assert!(worker.elapsed.load(Relaxed) >= crate::time::msecs_to_jiffies(20) as u64);
        assert_eq!(count_before_cleanup, 0);
        assert_eq!(count_after_late_wake, 0);
        Ok(())
    }
}
