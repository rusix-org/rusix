// SPDX-License-Identifier: GPL-2.0
// Rust translation of Linux 6.18.58 completion.c's blocking wait operations.

//! Private completion wait engine, retaining the baseline C storage and scheduler.
//!
//! This module must only be linked when the matching nine C bodies are excluded.
//! Their C EXPORT_SYMBOL records remain. Queue/scheduler primitives and macro
//! adapters still execute C; this is not independent Rust queue ownership.

use core::ptr::addr_of_mut;
use kernel::{
    bindings,
    ffi::{c_int, c_long, c_uint, c_ulong, c_void},
    sync::atomic::{Atomic, Relaxed},
    types::{NotThreadSafe, Opaque},
};
use pin_init::stack_pin_init;

// Private scheduler declaration at kernel/sched/sched.h in the pinned baseline.
// The implementation is a linked builtin; no public header or symbol export is
// needed by this builtin Rust implementation. The C waiter parameter is
// struct swait_queue *. Use an opaque pointer only at this private ABI boundary:
// x86_64 object-pointer representations match and the cast preserves provenance.
// The actual pinned allocation remains bindings::swait_queue. No struct crosses
// by value; this avoids recursively treating task_struct's configuration-empty
// sched_statistics member as a by-value FFI type.
unsafe extern "C" {
    fn __prepare_to_swait(queue: *mut bindings::swait_queue_head, waiter: *mut c_void);
}

type ScheduleAction = unsafe extern "C" fn(c_long) -> c_long;
const RESTART_SYS: c_long = -(bindings::ERESTARTSYS as c_long);

/// Owns a raw lock acquired with IRQ disabling, releasing it with IRQ enabling.
///
/// Unlike signaling's irqsave guard, this models the blocking C API's IRQ
/// transitions. Storage stays live throughout waits, including unlocked sleep.
/// The private scheduler method returns with the lock held again. The guard
/// cannot cross execution contexts or escape the enclosing synchronous wait.
struct IrqEnabledOnDrop {
    lock: *mut bindings::raw_spinlock_t,
    _task: NotThreadSafe,
}

impl IrqEnabledOnDrop {
    /// # Safety
    ///
    /// Caller must be in sleepable task context with IRQs enabled and must not
    /// hold this lock. Its initialized, immovable storage must stay alive through
    /// final unlock, including all scheduler calls. No other path may release
    /// this acquisition. The guard must remain in this task and be dropped here.
    unsafe fn acquire(lock: *mut bindings::raw_spinlock_t) -> Self {
        // SAFETY: Caller supplies initialized live storage and excludes recursive
        // locking. This macro adapter disables IRQs and takes this exact lock.
        unsafe { bindings::raw_spin_lock_irq(lock) };
        Self {
            lock,
            _task: NotThreadSafe,
        }
    }

    /// Temporarily releases the lock and enables IRQs to run the C scheduler.
    ///
    /// # Safety
    ///
    /// This task must already have prepared its waiter and set its task state
    /// under the lock. `action` must be schedule_timeout or io_schedule_timeout.
    /// No lock-dependent reference may survive this call. Storage must remain
    /// alive while unlocked. The action cannot unwind and must return in this
    /// same task. Its signed timeout is forwarded unchanged.
    #[unsafe(link_section = ".sched.text")]
    unsafe fn schedule(&mut self, action: ScheduleAction, timeout: c_long) -> c_long {
        // SAFETY: This guard currently owns the lock. The caller keeps queue and
        // waiter storage alive and has published state before this release.
        unsafe { bindings::raw_spin_unlock_irq(self.lock) };
        // SAFETY: The caller restricts action to the two scheduler entry points,
        // prepared the task state and supplies a timeout accepted by the C API.
        // Both functions return in the calling task and cannot unwind through Rust.
        let remaining = unsafe { action(timeout) };
        // SAFETY: The same initialized lock remains alive across sleep. It is no
        // longer owned by this task. Reacquisition restores the guard invariant
        // before any other Rust operation or reference to protected storage.
        unsafe { bindings::raw_spin_lock_irq(self.lock) };
        remaining
    }
}

impl Drop for IrqEnabledOnDrop {
    fn drop(&mut self) {
        // SAFETY: Construction acquires this lock, and schedule reacquires it
        // before returning. No other path unlocks it. Caller keeps storage alive
        // through this release; the guard makes no later storage access.
        unsafe { bindings::raw_spin_unlock_irq(self.lock) };
    }
}

/// Reads the counter without retaining an atomic reference across unlock.
///
/// # Safety
///
/// `completion` must be live initialized storage whose wait.lock this task holds.
/// All concurrent counter updates hold that lock and selected core accesses
/// are LKMM atomic. External observations must be marked or synchronized;
/// Kconfig excludes known incompatible readers. Init/reset must be quiescent.
unsafe fn locked_done(completion: *mut bindings::completion) -> u32 {
    // SAFETY: The initialized, aligned u32 field is protected from C plain
    // initialization/reset for this reference's entire lifetime. Concurrent marked readers
    // do not race against this LKMM operation. The reference does not escape.
    unsafe { Atomic::<u32>::from_ptr(addr_of_mut!((*completion).done)) }.load(Relaxed)
}

/// Consumes a nonsaturated counter value under the completion lock.
///
/// # Safety
///
/// The requirements of locked_done apply. `count` must be the current nonzero
/// counter value observed under this uninterrupted lock acquisition.
unsafe fn consume_locked(completion: *mut bindings::completion, count: u32) {
    if count != u32::MAX {
        // SAFETY: The caller holds wait.lock, excludes concurrent plain writers
        // and supplies the current positive count. The reference ends here,
        // before any unlock. Quiescent reset cannot overlap the store.
        unsafe { Atomic::<u32>::from_ptr(addr_of_mut!((*completion).done)) }
            .store(count.wrapping_sub(1), Relaxed);
    }
}

/// Shared implementation of the nine C blocking completion entry points.
///
/// # Safety
///
/// The completion must be initialized, immovable and alive through final unlock,
/// including periods when this task is asleep. Initialization/reset must be
/// externally quiescent. Other operations follow the baseline queue-lock and
/// counter rules. Caller must be in sleepable task context with IRQs enabled,
/// without holding this lock or locks needed by a completing task. `action` must
/// be schedule_timeout or io_schedule_timeout. `state` and `timeout` retain the
/// original C API's meaning, including unsigned-to-signed timeout conversion.
#[unsafe(link_section = ".sched.text")]
unsafe fn wait_for_common(
    completion: *mut bindings::completion,
    action: ScheduleAction,
    mut timeout: c_long,
    state: c_uint,
) -> c_long {
    kernel::task::might_sleep();
    // complete_acquire/complete_release are empty inline functions in the pinned
    // include/linux/completion.h. There is no omitted runtime operation.

    // SAFETY: Caller supplies initialized live completion storage; raw field
    // projection creates no reference to concurrently mutable containing data.
    let queue = unsafe { addr_of_mut!((*completion).wait) };
    // SAFETY: The lock is an initialized in-bounds field of this live queue.
    let lock = unsafe { addr_of_mut!((*queue).lock) };
    // SAFETY: The caller's context/lifetime/nonrecursive requirements are those
    // of this guard. It stays local, including across synchronous scheduler calls.
    let mut guard = unsafe { IrqEnabledOnDrop::acquire(lock) };

    // SAFETY: This task holds wait.lock and the caller guarantees reset quiescence.
    if unsafe { locked_done(completion) } == 0 {
        // Initialize directly in final pinned stack storage. Opaque keeps the
        // C-mutated list links behind UnsafeCell, even while the task sleeps.
        stack_pin_init!(let waiter = Opaque::ffi_init(|p: *mut bindings::swait_queue| {
            // SAFETY: p denotes exclusive uninitialized final pinned storage.
            // Raw writes initialize every field without reading it or exposing
            // references. Self-links point within this same pinned allocation;
            // current stays alive throughout its own synchronous wait.
            unsafe {
                addr_of_mut!((*p).task).write(bindings::get_current());
                let list = addr_of_mut!((*p).task_list);
                addr_of_mut!((*list).next).write(list);
                addr_of_mut!((*list).prev).write(list);
            }
        }));

        loop {
            // SAFETY: get_current returns this live calling task. The helper
            // performs the baseline signal-state query without retaining it.
            if unsafe { bindings::signal_pending_state(state, bindings::get_current()) } != 0 {
                timeout = RESTART_SYS;
                break;
            }
            // SAFETY: queue and pinned waiter remain initialized/live. This task
            // owns queue.lock; the waiter is either self-linked or already on
            // this queue. The primitive records current and enrolls only once.
            unsafe { __prepare_to_swait(queue, waiter.get().cast()) };
            // SAFETY: The state is the original C caller's requested wait state;
            // it is published while holding the lock, retaining debug/trace hooks.
            unsafe { bindings::__set_current_state(state) };
            // SAFETY: State and enrollment were established above. Only the two
            // C scheduler actions reach this function; no atomic/reference to
            // lock-protected data survives the release. Caller retains storage.
            timeout = unsafe { guard.schedule(action, timeout) };
            // SAFETY: schedule reacquired wait.lock. The short atomic reference
            // ends before any subsequent iteration releases the lock again.
            if unsafe { locked_done(completion) } != 0 || timeout == 0 {
                break;
            }
        }

        // SAFETY: The pinned waiter is still live and queue.lock is held, even
        // if interruption happened before first enrollment. Its initialized
        // self-links make that case valid. This restores TASK_RUNNING and removes
        // any remaining link before stack storage can be destroyed.
        unsafe { bindings::__finish_swait(queue, waiter.get()) };
        // SAFETY: The same uninterrupted lock acquisition still protects done.
        if unsafe { locked_done(completion) } == 0 {
            return timeout;
        }
    }

    // SAFETY: wait.lock is held; either the initial load was positive or the
    // post-wait load was. No concurrent writer can change it before consumption.
    let count = unsafe { locked_done(completion) };
    // SAFETY: count is the current positive value under the uninterrupted lock.
    unsafe { consume_locked(completion, count) };
    // Preserve the C GNU ?: expression: completion observed at timeout returns
    // one; every other signed value is retained. Final guard drop enables IRQs.
    if timeout != 0 {
        timeout
    } else {
        1
    }
}

/// Waits uninterruptibly until a completion token is available.
///
/// # Safety
///
/// Caller must satisfy wait_for_common's storage, quiescent-reset, lifetime and
/// sleepable-context requirements. Storage must survive the entire blocking wait.
// SAFETY: Selection excludes the matching C body; pointer/void ABI is unchanged.
#[unsafe(no_mangle)]
#[unsafe(link_section = ".sched.text")]
unsafe extern "C" fn wait_for_completion(completion: *mut bindings::completion) {
    // SAFETY: Caller provides the shared contract; these are the baseline action,
    // infinite timeout and uninterruptible state.
    unsafe {
        wait_for_common(
            completion,
            bindings::schedule_timeout,
            c_long::MAX,
            bindings::TASK_UNINTERRUPTIBLE,
        )
    };
}

/// Waits uninterruptibly, returning zero on timeout or remaining positive jiffies.
///
/// # Safety
///
/// The storage and context requirements of wait_for_completion apply; a timeout
/// does not release callers from the lifetime needs of concurrent producers.
// SAFETY: Matching C body is excluded; pointer/unsigned-long ABI is preserved.
#[unsafe(no_mangle)]
#[unsafe(link_section = ".sched.text")]
unsafe extern "C" fn wait_for_completion_timeout(
    completion: *mut bindings::completion,
    timeout: c_ulong,
) -> c_ulong {
    // SAFETY: Caller provides the shared contract. Casts preserve the baseline
    // unsigned timeout -> signed scheduler value -> unsigned result conversions.
    unsafe {
        wait_for_common(
            completion,
            bindings::schedule_timeout,
            timeout as c_long,
            bindings::TASK_UNINTERRUPTIBLE,
        ) as c_ulong
    }
}

/// Waits uninterruptibly with the baseline scheduler's I/O wait accounting.
///
/// # Safety
///
/// The storage and context requirements of wait_for_completion apply.
// SAFETY: Matching C body is excluded; pointer/void ABI is preserved.
#[unsafe(no_mangle)]
#[unsafe(link_section = ".sched.text")]
unsafe extern "C" fn wait_for_completion_io(completion: *mut bindings::completion) {
    // SAFETY: Caller provides the shared contract; the I/O scheduler preserves
    // the original accounting with an infinite uninterruptible timeout.
    unsafe {
        wait_for_common(
            completion,
            bindings::io_schedule_timeout,
            c_long::MAX,
            bindings::TASK_UNINTERRUPTIBLE,
        )
    };
}

/// Waits with I/O accounting and a timeout, returning the baseline jiffy result.
///
/// # Safety
///
/// The storage and context requirements of wait_for_completion_timeout apply.
// SAFETY: Matching C body is excluded; pointer/unsigned-long ABI is preserved.
#[unsafe(no_mangle)]
#[unsafe(link_section = ".sched.text")]
unsafe extern "C" fn wait_for_completion_io_timeout(
    completion: *mut bindings::completion,
    timeout: c_ulong,
) -> c_ulong {
    // SAFETY: Caller provides the shared contract; casts and I/O action retain
    // the baseline timeout conversion and scheduler accounting.
    unsafe {
        wait_for_common(
            completion,
            bindings::io_schedule_timeout,
            timeout as c_long,
            bindings::TASK_UNINTERRUPTIBLE,
        ) as c_ulong
    }
}

/// Waits interruptibly, returning -ERESTARTSYS on interruption and zero otherwise.
///
/// # Safety
///
/// The storage and context requirements of wait_for_completion apply. An
/// interrupted wait does not by itself prove producer/storage quiescence.
// SAFETY: Matching C body is excluded; pointer/int ABI is preserved.
#[unsafe(no_mangle)]
#[unsafe(link_section = ".sched.text")]
unsafe extern "C" fn wait_for_completion_interruptible(
    completion: *mut bindings::completion,
) -> c_int {
    // SAFETY: Caller provides the shared contract; the state/action match C.
    let result = unsafe {
        wait_for_common(
            completion,
            bindings::schedule_timeout,
            c_long::MAX,
            bindings::TASK_INTERRUPTIBLE,
        )
    };
    if result == RESTART_SYS {
        result as c_int
    } else {
        0
    }
}

/// Waits interruptibly with a timeout, retaining signed interruption results.
///
/// # Safety
///
/// The storage and context requirements of wait_for_completion_interruptible
/// apply. Timeout or interruption does not prove producer/storage quiescence.
// SAFETY: Matching C body is excluded; pointer/unsigned-long/long ABI is preserved.
#[unsafe(no_mangle)]
#[unsafe(link_section = ".sched.text")]
unsafe extern "C" fn wait_for_completion_interruptible_timeout(
    completion: *mut bindings::completion,
    timeout: c_ulong,
) -> c_long {
    // SAFETY: Caller provides the shared contract; timeout cast preserves C.
    unsafe {
        wait_for_common(
            completion,
            bindings::schedule_timeout,
            timeout as c_long,
            bindings::TASK_INTERRUPTIBLE,
        )
    }
}

/// Waits for completion or a fatal signal, returning -ERESTARTSYS or zero.
///
/// # Safety
///
/// The storage and context requirements of wait_for_completion_interruptible apply.
// SAFETY: Matching C body is excluded; pointer/int ABI is preserved.
#[unsafe(no_mangle)]
#[unsafe(link_section = ".sched.text")]
unsafe extern "C" fn wait_for_completion_killable(completion: *mut bindings::completion) -> c_int {
    // SAFETY: Caller provides the shared contract; state distinguishes fatal
    // signals exactly through the retained C signal_pending_state primitive.
    let result = unsafe {
        wait_for_common(
            completion,
            bindings::schedule_timeout,
            c_long::MAX,
            bindings::TASK_KILLABLE,
        )
    };
    if result == RESTART_SYS {
        result as c_int
    } else {
        0
    }
}

/// Waits using the caller's task-state mask, returning -ERESTARTSYS or zero.
///
/// # Safety
///
/// The storage and context requirements of wait_for_completion_interruptible
/// apply. Caller must supply a state valid for the baseline completion wait API.
// SAFETY: Matching C body is excluded; pointer/unsigned-int/int ABI is preserved.
#[unsafe(no_mangle)]
#[unsafe(link_section = ".sched.text")]
unsafe extern "C" fn wait_for_completion_state(
    completion: *mut bindings::completion,
    state: c_uint,
) -> c_int {
    // SAFETY: Caller provides shared lifetime/context and state requirements.
    // C's intermediate unsigned->int->unsigned state conversion preserves these
    // same bits; retaining u32 avoids changing the task-state mask.
    let result =
        unsafe { wait_for_common(completion, bindings::schedule_timeout, c_long::MAX, state) };
    if result == RESTART_SYS {
        result as c_int
    } else {
        0
    }
}

/// Waits with a fatal-signal interruption policy and a finite timeout.
///
/// # Safety
///
/// The storage and context requirements of wait_for_completion_interruptible_timeout apply.
// SAFETY: Matching C body is excluded; pointer/unsigned-long/long ABI is preserved.
#[unsafe(no_mangle)]
#[unsafe(link_section = ".sched.text")]
unsafe extern "C" fn wait_for_completion_killable_timeout(
    completion: *mut bindings::completion,
    timeout: c_ulong,
) -> c_long {
    // SAFETY: Caller provides the shared contract; cast and state preserve C.
    unsafe {
        wait_for_common(
            completion,
            bindings::schedule_timeout,
            timeout as c_long,
            bindings::TASK_KILLABLE,
        )
    }
}
