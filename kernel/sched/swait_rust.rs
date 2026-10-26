// SPDX-License-Identifier: GPL-2.0
// Rust translation of four Linux 6.18.58 swait.c queue-policy entry points.

//! Queue enrollment, removal and wake policy over the temporary C list layout.
//!
//! Queue initialization, raw locks, marked list mutation and scheduler task wakeup
//! still execute C. This builtin implementation replaces the four matching C
//! bodies together; generic swait wrappers also call these entry points.

use core::ptr::{addr_of, addr_of_mut};
use kernel::{
    bindings,
    ffi::{c_int, c_uint, c_void},
};

// Pinned private scheduler ABI from kernel/sched/sched.h:
// int try_to_wake_up(struct task_struct *tsk, unsigned int state, int wake_flags).
// Only the object pointer crosses this boundary, never task_struct by value.
// An opaque pointer avoids recursive FFI diagnostics for configuration-empty
// embedded task members. On the selected x86_64 target the pointer ABI matches;
// the cast preserves the live task pointer's address and provenance.
unsafe extern "C" {
    fn try_to_wake_up(task: *mut c_void, state: c_uint, wake_flags: c_int) -> c_int;
}

/// Enrolls the current task once, preserving FIFO list order.
///
/// # Safety
///
/// The caller must hold `queue.lock` with IRQs disabled. Queue storage is
/// initialized, immovable and live through this call. `waiter` is a pinned
/// `struct swait_queue` whose task_list is initialized and either self-linked
/// or already enrolled for the current task, including a detached wake batch
/// protected by this same queue lock. Its task field
/// may be uninitialized on first enrollment. The task and waiter stay alive
/// until removal; no other context may reuse/reinitialize the waiter meanwhile.
// SAFETY: Conditional C selection excludes the original body. The second C
// parameter is struct swait_queue *; c_void is only an opaque object-pointer ABI
// boundary. Actual storage remains the generated, target-layout waiter type.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn __prepare_to_swait(
    queue: *mut bindings::swait_queue_head,
    waiter: *mut c_void,
) {
    let waiter = waiter.cast::<bindings::swait_queue>();
    // SAFETY: Caller supplies final pinned waiter storage, exclusively protected
    // by queue.lock. Writing initializes/replaces only task, not its list links;
    // current remains alive during its own wait. No Rust reference is created.
    unsafe { addr_of_mut!((*waiter).task).write(bindings::get_current()) };
    // SAFETY: Both projections address initialized list_head fields in live
    // storage. Holding queue.lock excludes all competing link mutations.
    let node = unsafe { addr_of_mut!((*waiter).task_list) };
    // SAFETY: Same initialized/live queue and held-lock requirements apply.
    let head = unsafe { addr_of_mut!((*queue).task_list) };
    // SAFETY: node is initialized and stable under the held queue lock. The C
    // adapter preserves list_empty's marked READ_ONCE and retains no pointer.
    if unsafe { bindings::swait_list_empty(node) } != 0 {
        // SAFETY: The waiter is self-linked, not concurrently owned by another
        // queue. Caller retains pinned storage until removal. The adapter keeps
        // baseline list hardening/debug checks and marked publication stores.
        unsafe { bindings::swait_list_add_tail(node, head) };
    }
}

/// Restores running state and removes the current task's waiter if still queued.
///
/// # Safety
///
/// Caller holds the queue's raw lock with IRQs disabled. Queue and waiter obey
/// __prepare_to_swait's storage/lifetime rules. The waiter belongs to current and
/// is either still on this queue or self-linked after wakeup (including the
/// initialized-but-never-enrolled signal path). No other context reuses it.
// SAFETY: Matching C body is excluded. C ABI uses two object pointers; only the
// second is opaque here to avoid recursively exposing task internals by value.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn __finish_swait(
    _queue: *mut bindings::swait_queue_head,
    waiter: *mut c_void,
) {
    // SAFETY: The caller is the task finishing its own synchronous wait. The
    // existing helper preserves __set_current_state's debug/tracing hooks.
    unsafe { bindings::__set_current_state(bindings::TASK_RUNNING) };
    let waiter = waiter.cast::<bindings::swait_queue>();
    // SAFETY: The pinned initialized waiter is live; queue.lock protects links.
    let node = unsafe { addr_of_mut!((*waiter).task_list) };
    // SAFETY: Initialized node; the held queue lock prevents link mutations.
    if unsafe { bindings::swait_list_empty(node) } == 0 {
        // SAFETY: node is enrolled on the locked queue. The C adapter preserves
        // validation, unlink stores and self-link ordering. No node access follows.
        unsafe { bindings::swait_list_del_init(node) };
    }
}

/// Wakes and removes the first queued waiter, retaining the scheduler wake flags.
///
/// # Safety
///
/// Caller holds the initialized queue's raw lock with IRQs disabled and keeps
/// its storage immovable and alive. Every queued node is a live pinned swait
/// waiter whose task remains alive until removal. Waiter owners must follow the
/// swait protocol; nodes cannot be freed/reused while still linked. `wake_flags`
/// must be accepted by the scheduler's original swake_up_locked API.
// SAFETY: C body is excluded under the same option. The queue-pointer/int ABI
// matches swait.h, and its original EXPORT_SYMBOL record remains in C exactly once.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn swake_up_locked(
    queue: *mut bindings::swait_queue_head,
    wake_flags: c_int,
) {
    // SAFETY: Caller provides initialized live queue storage and owns its lock.
    let head = unsafe { addr_of_mut!((*queue).task_list) };
    // SAFETY: The head is initialized and its mutations are excluded by the lock.
    if unsafe { bindings::swait_list_empty(head) } != 0 {
        return;
    }
    // SAFETY: Queue is nonempty and locked. Its next pointer denotes the first
    // live waiter's embedded node; the head itself cannot be returned here.
    // A plain raw read is protected from every concurrent link writer.
    let first = unsafe { addr_of!((*head).next).read() };
    // SAFETY: swait queue invariants place first at task_list within a live,
    // pinned bindings::swait_queue allocation, not an arbitrary list payload.
    let waiter = unsafe { kernel::container_of!(first, bindings::swait_queue, task_list) };
    // SAFETY: Enrollment initialized task. Queue.lock serializes task/link
    // mutation, and this live queued waiter retains its task's lifetime.
    let task = unsafe { addr_of!((*waiter).task).read() };
    // SAFETY: The task is live while this node remains enrolled. The retained
    // scheduler primitive supplies state ordering/full barriers and returns in
    // the same atomic context without retaining queue/node pointers. The lock
    // remains held. Ignore its return exactly like C: an already-running task
    // will observe its condition. Wake precedes unlink as in the baseline.
    unsafe { try_to_wake_up(task.cast(), bindings::TASK_NORMAL, wake_flags) };
    // SAFETY: first is still linked to the locked queue. The list adapter keeps
    // hardening/debug checks and WRITE_ONCE stores. This is the FINAL access to
    // this waiter: generic finish_swait may observe the self-links locklessly
    // and return, destroying its stack storage even before we release queue.lock.
    unsafe { bindings::swait_list_del_init(first) };
}

/// Wakes every queued waiter without releasing the queue lock.
///
/// This is completion's broadcast primitive, not generic swake_up_all: it does
/// not splice to a temporary list or drop/reacquire the lock between wakeups.
///
/// # Safety
///
/// The queue/node/task/lock requirements of swake_up_locked apply. Caller must
/// keep the queue itself alive for the whole traversal; removed waiters may
/// immediately cease to exist and are never revisited.
// SAFETY: The private C definition is excluded under the same option. The
// queue-pointer/void ABI matches sched.h; no new module export is introduced.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn swake_up_all_locked(queue: *mut bindings::swait_queue_head) {
    // SAFETY: Initialized live queue storage remains pinned and locked throughout.
    let head = unsafe { addr_of_mut!((*queue).task_list) };
    // SAFETY: The same initialized head stays live; the held lock excludes all
    // external mutations. Each iteration reloads the head, never a removed node.
    while unsafe { bindings::swait_list_empty(head) } == 0 {
        // SAFETY: Caller supplies the same locked queue/lifetime contract. The
        // queue is nonempty. Zero is the baseline broadcast scheduler wake flag.
        unsafe { swake_up_locked(queue, 0) };
    }
}
