// SPDX-License-Identifier: GPL-2.0
// Rust translation of nine Linux 6.18.58 swait.c queue-policy entry points.

//! Queue enrollment, removal and wake policy over the temporary C list layout.
//!
//! Queue initialization, raw locks, marked list mutation and scheduler task wakeup
//! still execute C. This builtin implementation replaces the nine matching C
//! bodies together; C consumer macros retain their existing wait-loop policy.

use core::ptr::{addr_of, addr_of_mut};
use kernel::{
    bindings,
    ffi::{c_int, c_long, c_uint, c_ulong, c_void},
    types::{NotThreadSafe, Opaque},
};
use pin_init::stack_pin_init;

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
/// is either still on this queue (or its detached wake batch) or self-linked
/// after wakeup (including the
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

/// Private synchronous ownership of a raw queue lock and incoming IRQ state.
struct SavedIrqs {
    lock: *mut bindings::raw_spinlock_t,
    flags: c_ulong,
    _task: NotThreadSafe,
}

impl SavedIrqs {
    /// # Safety
    /// The lock is initialized, pinned and alive through drop, and is not already
    /// owned by this task. No other path may release this acquisition. The guard
    /// stays in the calling task and is neither forgotten nor retained across sleep.
    unsafe fn acquire(lock: *mut bindings::raw_spinlock_t) -> Self {
        // SAFETY: The caller supplies the initialized live nonrecursive lock.
        let flags = unsafe { bindings::raw_spin_lock_irqsave(lock) };
        Self {
            lock,
            flags,
            _task: NotThreadSafe,
        }
    }
}

impl Drop for SavedIrqs {
    fn drop(&mut self) {
        // SAFETY: Construction acquired this exact lock, which remains live and
        // held. No other path releases it; flags belong to this task's acquisition.
        unsafe { bindings::raw_spin_unlock_irqrestore(self.lock, self.flags) };
    }
}

/// Generic broadcast intentionally enables IRQs between nonfinal wakeups.
struct EnabledIrqs {
    lock: *mut bindings::raw_spinlock_t,
    _task: NotThreadSafe,
}

impl EnabledIrqs {
    /// # Safety
    /// The initialized pinned lock stays alive through final drop and every
    /// unlocked interval. Caller enters with IRQs enabled and does not own the
    /// lock. No lock-dependent reference may survive a release/reacquire cycle.
    unsafe fn acquire(lock: *mut bindings::raw_spinlock_t) -> Self {
        // SAFETY: Caller supplies a live initialized nonrecursively held lock.
        unsafe { bindings::raw_spin_lock_irq(lock) };
        Self {
            lock,
            _task: NotThreadSafe,
        }
    }

    /// # Safety
    /// Queue and detached batch storage stay alive while unlocked. No borrowed
    /// node or protected reference crosses this call. No other path unlocks this
    /// guard; the current task will resume and reacquire its original queue lock.
    unsafe fn release_and_reacquire(&mut self) {
        // SAFETY: The guard owns this live lock. IRQ enabling is intentional,
        // matching C swake_up_all, rather than restoring a saved disabled state.
        unsafe { bindings::raw_spin_unlock_irq(self.lock) };
        // SAFETY: The same initialized lock survives the unlocked interval. No
        // fallible Rust operation occurs before reacquiring the guard's lock.
        unsafe { bindings::raw_spin_lock_irq(self.lock) };
    }
}

impl Drop for EnabledIrqs {
    fn drop(&mut self) {
        // SAFETY: Acquisition and each cycle leave this live lock held. Its
        // final release intentionally enables IRQs, matching the original API.
        unsafe { bindings::raw_spin_unlock_irq(self.lock) };
    }
}

/// Wakes at most the first queued task, preserving incoming IRQ state.
///
/// # Safety
/// Queue storage is initialized, pinned and alive through final unlock. Caller
/// does not hold its raw lock. Enrolled waiters obey swake_up_locked's lifetime
/// contract; the caller may enter with IRQs enabled or disabled.
// SAFETY: Conditional C selection retains the original pointer/void ABI/export.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn swake_up_one(queue: *mut bindings::swait_queue_head) {
    // SAFETY: Caller retains initialized pinned queue storage; no reference forms.
    let lock = unsafe { addr_of_mut!((*queue).lock) };
    // SAFETY: The queue lock is live and this task does not own it.
    let _restore = unsafe { SavedIrqs::acquire(lock) };
    // SAFETY: Queue lock is now held with IRQs disabled. Caller supplies waiter
    // lifetimes; zero is the original swake_up_one scheduler flag.
    unsafe { swake_up_locked(queue, 0) };
}

/// Wakes the initial batch of waiters, enabling IRQs between nonfinal wakeups.
///
/// New enrollments on the original queue are not part of this detached batch.
///
/// # Safety
/// Caller enters with IRQs enabled, does not hold the queue lock, and retains
/// initialized pinned queue storage through return, including unlocked intervals.
/// Waiters and their tasks follow the generic swait lifetime protocol. The
/// original queue lock protects both its list and this temporary detached batch.
// SAFETY: Same C pointer/void ABI; original export retained and C body excluded.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn swake_up_all(queue: *mut bindings::swait_queue_head) {
    // Initialize the self-linked head at its final pinned stack address. C can
    // mutate it while IRQs are enabled, so all links remain behind Opaque.
    stack_pin_init!(let batch = Opaque::ffi_init(|head: *mut bindings::list_head| {
        // SAFETY: Exclusive uninitialized final pinned storage; every field is
        // initialized before publishing this head to any linked waiter.
        unsafe {
            addr_of_mut!((*head).next).write(head);
            addr_of_mut!((*head).prev).write(head);
        }
    }));
    let head = batch.get();
    // SAFETY: Queue storage is initialized, pinned and retained through return.
    let lock = unsafe { addr_of_mut!((*queue).lock) };
    // SAFETY: Caller enters with enabled IRQs and excludes recursive locking.
    let mut guard = unsafe { EnabledIrqs::acquire(lock) };
    // SAFETY: Raw projection only; this initialized source list is locked.
    let original = unsafe { addr_of_mut!((*queue).task_list) };
    // SAFETY: Both heads are initialized and live. The batch is empty and
    // self-linked; the original queue lock protects its nodes, including after
    // detachment. The original head is reinitialized, preserving C semantics.
    unsafe { bindings::swait_list_splice_init(original, head) };
    // SAFETY: The same lock protects all mutations of the pinned batch head.
    while unsafe { bindings::swait_list_empty(head) } == 0 {
        // SAFETY: Nonempty locked batch points to a live enrolled waiter's node.
        let first = unsafe { addr_of!((*head).next).read() };
        // SAFETY: Each node is embedded at task_list in a pinned swait_queue.
        let waiter = unsafe { kernel::container_of!(first, bindings::swait_queue, task_list) };
        // SAFETY: Enrollment initialized task; the queue lock excludes task-field
        // mutation and this queued waiter retains its task's lifetime.
        let task = unsafe { addr_of!((*waiter).task).read() };
        // SAFETY: Live task; the existing C scheduler wake primitive preserves
        // baseline state ordering and is callable under this raw lock. It does
        // not retain any waiter/list pointer. Its return is intentionally ignored.
        unsafe { bindings::wake_up_state(task, bindings::TASK_NORMAL) };
        // SAFETY: This still-linked node is protected by the original lock.
        // Marked C deletion preserves debug checks. This is the FINAL waiter
        // access: generic finish_swait may now return and destroy its storage.
        unsafe { bindings::swait_list_del_init(first) };
        // SAFETY: Only the persistent pinned batch head is accessed after removal.
        if unsafe { bindings::swait_list_empty(head) } != 0 {
            break;
        }
        // SAFETY: No node/protected reference survives this cycle. Batch and
        // original queue stay alive. Concurrent finish may remove batch nodes;
        // a re-enrolled removed waiter joins original, not this batch. The loop
        // reloads batch after reacquiring and never follows a saved node pointer.
        unsafe { guard.release_and_reacquire() };
    }
    // Guard drops before pinned batch storage. The batch is empty under lock;
    // no queued waiter retains a link into it when final unlock occurs.
}

/// Enrolls current and publishes the caller's state with the full sleep barrier.
///
/// # Safety
/// Queue and waiter obey __prepare_to_swait's initialized/pinned lifetime rules;
/// waiter belongs to current. Caller does not hold queue.lock. Incoming IRQ state
/// may be enabled or disabled. Caller follows the normal condition/schedule loop.
// SAFETY: C uses a swait_queue* second argument; opaque object pointer preserves
// the selected x86_64 pointer ABI, while actual storage remains the generated type.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn prepare_to_swait_exclusive(
    queue: *mut bindings::swait_queue_head,
    waiter: *mut c_void,
    state: c_int,
) {
    // SAFETY: Initialized pinned queue storage remains alive through unlock.
    let lock = unsafe { addr_of_mut!((*queue).lock) };
    // SAFETY: Caller excludes recursive locking and retains live storage.
    let _restore = unsafe { SavedIrqs::acquire(lock) };
    // SAFETY: The lock is held with IRQs disabled; caller supplies a pinned
    // initialized node belonging to current, including detached-batch membership.
    unsafe { __prepare_to_swait(queue, waiter) };
    // SAFETY: Current owns this wait. The macro adapter preserves smp_store_mb,
    // debug and trace hooks; __set_current_state would omit the required barrier.
    unsafe { bindings::swait_set_current_state(state as c_uint) };
}

/// Prepares current to wait, or removes its node and returns -ERESTARTSYS.
///
/// # Safety
/// The storage/context requirements of prepare_to_swait_exclusive apply. The
/// node's links are initialized even when task has not yet been initialized.
// SAFETY: C pointer/pointer/int -> long ABI and export are preserved.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn prepare_to_swait_event(
    queue: *mut bindings::swait_queue_head,
    waiter: *mut c_void,
    state: c_int,
) -> c_long {
    // SAFETY: Caller retains initialized pinned queue storage through unlock.
    let lock = unsafe { addr_of_mut!((*queue).lock) };
    // SAFETY: Live lock, not already held by this task.
    let _restore = unsafe { SavedIrqs::acquire(lock) };
    // SAFETY: Current remains live through its own wait; state's bit pattern is
    // unchanged by the same signed-to-unsigned conversion as the C predicate.
    if unsafe { bindings::signal_pending_state(state as c_uint, bindings::get_current()) } != 0 {
        let waiter = waiter.cast::<bindings::swait_queue>();
        // SAFETY: The initialized node is self-linked or enrolled in the logical
        // queue/batch protected by the held lock. task need not be initialized.
        let node = unsafe { addr_of_mut!((*waiter).task_list) };
        // SAFETY: Unconditional deletion/self-initialization matches C even for
        // a never-enrolled node. No later node access or task-state store occurs.
        unsafe { bindings::swait_list_del_init(node) };
        return -(bindings::ERESTARTSYS as c_long);
    }
    // SAFETY: Caller supplies the pinned waiter; the lock serializes enrollment.
    unsafe { __prepare_to_swait(queue, waiter) };
    // SAFETY: Publish current state with the baseline full barrier and hooks.
    unsafe { bindings::swait_set_current_state(state as c_uint) };
    0
}

/// Restores running state and removes a waiter, using the careful lockless fast path.
///
/// # Safety
/// This is the current task's initialized pinned waiter. Its only concurrent link
/// mutation can be removal by the logical queue's waker; no other context can
/// re-enroll or reinitialize it. Queue storage stays live if locking is needed,
/// and caller does not already hold its lock. Incoming IRQ state is preserved.
// SAFETY: C pointer/pointer -> void ABI and original export are retained.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn finish_swait(queue: *mut bindings::swait_queue_head, waiter: *mut c_void) {
    // SAFETY: Caller is current finishing its own wait; retains debug/trace hooks.
    unsafe { bindings::__set_current_state(bindings::TASK_RUNNING) };
    let waiter = waiter.cast::<bindings::swait_queue>();
    // SAFETY: The current task retains its initialized pinned node throughout.
    let node = unsafe { addr_of_mut!((*waiter).task_list) };
    // SAFETY: Only concurrent removal/self-linking is allowed. The C adapter
    // preserves acquire on next plus READ_ONCE on prev; ordinary list_empty or
    // a plain Rust load would not satisfy this lockless observation protocol.
    if unsafe { bindings::swait_list_empty_careful(node) } == 0 {
        // SAFETY: Caller retains initialized queue storage when removal needs
        // locking. Projection is delayed until after the lockless fast path.
        let lock = unsafe { addr_of_mut!((*queue).lock) };
        // SAFETY: Live initialized lock not held by this task; preserve IRQ flags.
        let _restore = unsafe { SavedIrqs::acquire(lock) };
        // SAFETY: The node is live and now serialized with deletion, including
        // a concurrent removal that completed before lock acquisition. Do not
        // recheck: list_del_init on self-links is valid and is exactly C's path.
        unsafe { bindings::swait_list_del_init(node) };
    }
}
