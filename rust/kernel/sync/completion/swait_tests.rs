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
    PendingFresh,
    PendingQueued,
    SignalFalse,
    SignalCondition,
    Batch,
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
    detail: Atomic<u32>,
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
            detail: Atomic::new(0),
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

// Signals are confined to this dedicated thread's private handler state.
fn pending_signal() -> bool {
    // SAFETY: This helper is called only by our standalone callback, never a
    // shared worker or KUnit controller; its private handler accepts SIGUSR1.
    unsafe { bindings::completion_test_allow_signal(bindings::SIGUSR1 as c_int) };
    // SAFETY: Current is this live callback task; the signal remains pending
    // for kernel wait predicates and no userspace signal delivery occurs here.
    let sent = unsafe {
        bindings::completion_test_send_signal(bindings::get_current(), bindings::SIGUSR1 as c_int)
    };
    // SAFETY: Marked pending-state observation on the live calling task.
    sent == 0 && unsafe { bindings::signal_pending(bindings::get_current()) } != 0
}

fn pending_prepare(worker: &Worker, queued: bool) -> c_long {
    if queued {
        // SAFETY: Current owns the pinned initialized waiter and retained queue.
        unsafe {
            bindings::prepare_to_swait_exclusive(
                worker.queue.raw(),
                worker.waiter.get(),
                bindings::TASK_UNINTERRUPTIBLE as c_int,
            )
        };
        // SAFETY: Immediately restore this dedicated callback's state before any
        // signal operation; no schedule or fallible step occurred in between.
        unsafe { bindings::__set_current_state(bindings::TASK_RUNNING) };
    }
    let pending = pending_signal();
    // SAFETY: Same-task local IRQ save; no sleep/fallible operations until restore.
    let flags = unsafe { bindings::swait_test_irq_save() };
    // SAFETY: Change only this dedicated callback's state with IRQs disabled.
    // No schedule/fallible operation occurs before restoring RUNNING below.
    unsafe { bindings::__set_current_state(bindings::TASK_UNINTERRUPTIBLE) };
    // SAFETY: Initialized retained queue/node, current task, IRQ-safe API. A
    // pending signal must remove any node without changing the sentinel state.
    let result = unsafe {
        bindings::prepare_to_swait_event(
            worker.queue.raw(),
            worker.waiter.get(),
            bindings::TASK_INTERRUPTIBLE as c_int,
        )
    };
    // SAFETY: Current-context observations while IRQs remain locally disabled.
    let irqs = unsafe { bindings::swait_test_irqs_disabled() } != 0;
    // SAFETY: Marked read of this calling task's state only. Testing a sleeping
    // sentinel distinguishes an incorrect finish_swait call that stores RUNNING.
    let unchanged =
        unsafe { bindings::swait_test_current_state() } == bindings::TASK_UNINTERRUPTIBLE;
    // SAFETY: Restore current before IRQs can be enabled or any sleep occurs.
    unsafe { bindings::__set_current_state(bindings::TASK_RUNNING) };
    // SAFETY: Exact saved flags from this callback, restored before other work.
    unsafe { bindings::swait_test_irq_restore(flags) };
    let snapshot;
    {
        let _guard = worker.queue.lock();
        // SAFETY: Held queue lock, initialized node retained by callback Arc.
        snapshot = unsafe {
            bindings::swait_test_snapshot_locked(
                worker.queue.raw(),
                worker.waiter.get(),
                null_mut(),
            )
        };
    }
    let expected = (1 << 8) | (1 << 11) | if queued { 1 << 10 } else { 0 };
    worker.detail.store(
        u32::from(pending)
            | (u32::from(irqs) << 1)
            | (u32::from(unchanged) << 2)
            | (u32::from(snapshot == expected) << 3),
        Relaxed,
    );
    // SAFETY: Always restore RUNNING/unlink before acknowledgment, even when
    // observed behavior was wrong; retained initialized waiter belongs to current.
    unsafe { bindings::finish_swait(worker.queue.raw(), worker.waiter.get()) };
    result
}

fn pending_macro(worker: &Worker, timeout: c_long, late_condition: bool) -> c_long {
    let pending = pending_signal();
    let mut evaluations = 0u32;
    let result = if late_condition {
        // SAFETY: Dedicated sleepable callback and retained queue. evaluations
        // is exclusively borrowed stack storage for this non-retaining helper.
        unsafe {
            bindings::swait_test_condition_after_prepare(
                worker.queue.raw(),
                &mut evaluations,
                timeout,
            )
        }
    } else {
        // SAFETY: Condition is initialized LKMM atomic storage; C uses READ_ONCE.
        // The original macro manages and unlinks its own stack waiter.
        unsafe {
            bindings::swait_test_interruptible_timeout(
                worker.queue.raw(),
                worker.condition.as_ptr(),
                timeout,
            )
        }
    };
    // SAFETY: Marked read of current callback state; pending-error path must
    // preserve RUNNING, and successful macro finish must restore it.
    let running = unsafe { bindings::swait_test_current_state() } == bindings::TASK_RUNNING;
    worker.detail.store(
        u32::from(pending) | (u32::from(running) << 1) | (evaluations << 2),
        Relaxed,
    );
    result
}

// Keep initialized nodes enrolled until the controller's release, independently
// of spurious task wakeups. This tests broadcast list traversal, not wake latency.
fn batch_wait(worker: &Worker, timeout: c_long) -> c_long {
    {
        let _guard = worker.queue.lock();
        // SAFETY: Current owns this pinned node and holds queue.lock. It remains
        // alive until finish below; a running task is a valid queued wake target.
        unsafe { __prepare_to_swait(worker.queue.raw(), worker.waiter.get().cast()) };
    }
    // SAFETY: Marked global read; interval is finite and below half-counter range.
    let start = unsafe { bindings::completion_test_jiffies() };
    while worker.condition.load(Relaxed) == 0 {
        // SAFETY: Same marked read used for bounded callback lifetime.
        if unsafe { bindings::completion_test_jiffies() }.wrapping_sub(start) >= timeout as c_ulong
        {
            break;
        }
        // SAFETY: Sleepable dedicated task with no held locks. The retained
        // queue/node can be woken by broadcast; no reenrollment occurs here.
        unsafe { bindings::schedule_timeout_uninterruptible(1) };
    }
    // SAFETY: Current-owned pinned node, retained queue, original finish API.
    unsafe { bindings::finish_swait(worker.queue.raw(), worker.waiter.get()) };
    c_long::from(worker.condition.load(Relaxed) != 0)
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
        Mode::PendingFresh => pending_prepare(&worker, false),
        Mode::PendingQueued => pending_prepare(&worker, true),
        Mode::SignalFalse => pending_macro(&worker, timeout, false),
        Mode::SignalCondition => pending_macro(&worker, timeout, true),
        Mode::Batch => batch_wait(&worker, timeout),
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

    #[test]
    fn pending_prepare_event_unlinks_without_changing_state_or_irqs() -> Result {
        for mode in [Mode::PendingFresh, Mode::PendingQueued] {
            let queue = Arc::pin_init(Queue::new(), GFP_KERNEL)?;
            let worker = Arc::pin_init(Worker::new(queue.clone(), mode, 10000), GFP_KERNEL)?;
            let started = Instant::<Monotonic>::now();
            let task = spawn(&worker)?;
            let finished = worker.finish_observed();
            worker.release();
            drop(task);
            assert!(finished);
            assert!(started.elapsed().as_millis() < 5000);
            assert_eq!(worker.result.load(Relaxed), -(bindings::ERESTARTSYS as i64));
            assert_eq!(worker.detail.load(Relaxed), 15);
            assert_eq!(queue.count(), 0);
        }
        Ok(())
    }

    #[test]
    fn generic_signal_error_and_post_prepare_condition_precedence() -> Result {
        for late_condition in [false, true] {
            let queue = Arc::pin_init(Queue::new(), GFP_KERNEL)?;
            let mode = if late_condition {
                Mode::SignalCondition
            } else {
                Mode::SignalFalse
            };
            let worker = Arc::pin_init(Worker::new(queue.clone(), mode, 10000), GFP_KERNEL)?;
            let started = Instant::<Monotonic>::now();
            let task = spawn(&worker)?;
            let finished = worker.finish_observed();
            let count = queue.count();
            worker.release();
            drop(task);
            assert!(finished);
            assert!(started.elapsed().as_millis() < 5000);
            assert_eq!(count, 0);
            assert_eq!(
                worker.detail.load(Relaxed),
                if late_condition { 3 | (2 << 2) } else { 3 }
            );
            assert_eq!(
                worker.result.load(Relaxed),
                if late_condition {
                    crate::time::msecs_to_jiffies(10000) as i64
                } else {
                    -(bindings::ERESTARTSYS as i64)
                }
            );
        }
        Ok(())
    }

    #[test]
    fn generic_broadcast_removes_initial_batch_and_leaves_late_waiter() -> Result {
        let queue = Arc::pin_init(Queue::new(), GFP_KERNEL)?;
        let first = Arc::pin_init(Worker::new(queue.clone(), Mode::Batch, 10000), GFP_KERNEL)?;
        let second = Arc::pin_init(Worker::new(queue.clone(), Mode::Batch, 10000), GFP_KERNEL)?;
        let late = Arc::pin_init(Worker::new(queue.clone(), Mode::Generic, 10000), GFP_KERNEL)?;
        let started = Instant::<Monotonic>::now();
        let first_task = spawn(&first)?;
        let second_task = match spawn(&second) {
            Ok(task) => task,
            Err(error) => {
                first.release();
                return Err(error);
            }
        };
        let enrolled = observe_count(&queue, 2);
        // SAFETY: Current-context observation. KUnit controller enters the
        // generic broadcast with IRQs enabled and holds no queue lock.
        let before_irq = unsafe { bindings::swait_test_irqs_disabled() };
        // SAFETY: Retained initialized queue; callbacks own nodes and do not
        // finish or reenroll until released below (except bounded failure).
        unsafe { bindings::swake_up_all(queue.raw()) };
        // SAFETY: Observe the same context after broadcast returns.
        let after_irq = unsafe { bindings::swait_test_irqs_disabled() };
        let removed = queue.count();
        first.release();
        second.release();
        let first_finished = first.finish_observed();
        let second_finished = second.finish_observed();
        drop(first_task);
        drop(second_task);
        // All previous callbacks are now released; a late waiter requires its
        // own condition publication/wake rather than any broadcast credit.
        let late_task = spawn(&late)?;
        let late_enrolled = observe_count(&queue, 1);
        let late_count = queue.count();
        late.release();
        let late_finished = late.finish_observed();
        late.release();
        drop(late_task);
        assert!(enrolled && first_finished && second_finished);
        assert!(started.elapsed().as_millis() < 5000);
        assert_eq!(before_irq, 0);
        assert_eq!(after_irq, 0);
        assert_eq!(removed, 0);
        assert_eq!(first.result.load(Relaxed), 1);
        assert_eq!(second.result.load(Relaxed), 1);
        assert!(late_enrolled && late_finished);
        assert_eq!(late_count, 1);
        assert!(late.result.load(Relaxed) > 0);
        assert_eq!(queue.count(), 0);
        Ok(())
    }
}
