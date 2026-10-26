// SPDX-License-Identifier: GPL-2.0-only
//! Owned sparse backing pages for the Rust BRD implementation.
//!
//! The index owns one Arc per resident page. A request clones that Arc under
//! the index lock and drops the index lock before accessing page contents.
//! Discard removes only the index's reference: in-flight requests keep detached
//! pages alive. A newly inserted page at that index has independent ownership.

use kernel::{
    alloc::{self, Flags},
    page::Page,
    prelude::*,
    sync::{
        atomic::{Atomic, Relaxed},
        Arc, SpinLock,
    },
    xarray::{AllocKind, XArray},
};

/// A private backing page, never published as a bio payload page.
///
/// Every access to its bytes is made while `page` is locked. The allocation is
/// zero-initialized before publication. Its sole Page owner lives in this slot;
/// callers own Arcs to the slot rather than independent C page references.
#[pin_data]
pub(super) struct PageSlot {
    #[pin]
    page: SpinLock<Page>,
}

impl PageSlot {
    fn new(page: Page) -> impl PinInit<Self> {
        pin_init!(Self {
            page <- kernel::new_spinlock!(page, "brd_rust_page"),
        })
    }

    /// Accesses the private initialized page while holding its content lock.
    ///
    /// The callback must not acquire the store's index lock or allocate. Bio
    /// transfer callers must additionally uphold their primitive's external
    /// payload and non-aliasing requirements. This method alone does not make
    /// externally mutable bio bytes into an exclusive Rust reference.
    pub(super) fn with_page<T>(&self, f: impl FnOnce(&Page) -> T) -> T {
        let page = self.page.lock();
        f(&page)
    }
}

/// A pinned sparse page index with an independently readable resident count.
///
/// The xarray lock serializes insertion/removal and the associated count update.
/// `count` is an LKMM atomic, never an unsynchronized field exposed to C debugfs.
/// Only this module mutates the array; it never stores reservations. Index and
/// page locks are never held together by the data path.
#[pin_data]
pub(super) struct Store {
    #[pin]
    pages: XArray<Arc<PageSlot>>,
    count: Atomic<u64>,
}

impl Store {
    /// Initializes an empty store. Its owner must quiesce users before teardown.
    pub(super) fn new() -> impl PinInit<Self> {
        pin_init!(Self {
            pages <- XArray::new(AllocKind::Alloc),
            count: Atomic::new(0),
        })
    }

    /// Acquires an operation-owned reference while the index still owns a slot.
    pub(super) fn lookup(&self, index: usize) -> Option<Arc<PageSlot>> {
        self.pages.lock().get(index).map(Arc::from)
    }

    /// Returns the resident slot or atomically inserts a newly zeroed page.
    ///
    /// Use `GFP_NOWAIT` for a NOWAIT request, `GFP_KERNEL` otherwise. The NOIO
    /// task scope covers *all* nested allocations, including xarray nodes and
    /// the Arc/lock metadata. HIGHMEM is applied only to the page allocation;
    /// it must never be passed to the kmalloc-backed slot allocation.
    pub(super) fn get_or_insert(&self, index: usize, flags: Flags) -> Result<Arc<PageSlot>> {
        if let Some(slot) = self.lookup(index) {
            return Ok(slot);
        }

        alloc::with_noio(|| {
            // Both allocations occur before taking the xarray lock.
            let page = Page::alloc_page(flags | __GFP_ZERO | __GFP_HIGHMEM)?;
            let candidate = Arc::pin_init(PageSlot::new(page), flags)?;
            let mut index_guard = self.pages.lock();
            match index_guard.insert(index, candidate.clone(), flags) {
                Ok(()) => {
                    self.count.fetch_add(1, Relaxed);
                    drop(index_guard);
                    Ok(candidate)
                }
                Err(rejected) => {
                    // __xa_insert may drop/reacquire its lock to allocate nodes.
                    // On EBUSY it leaves the competing entry in place. Clone it
                    // before dropping the lock so a concurrent discard cannot
                    // free it between observation and reference acquisition.
                    let result = if rejected.error == EBUSY {
                        // Reservations are impossible through this store's API.
                        // Still fail safely instead of assuming EBUSY implies a
                        // normal visible entry in the generic XArray interface.
                        index_guard.get(index).map(Arc::from).ok_or(EIO)
                    } else {
                        Err(rejected.error)
                    };
                    drop(index_guard);
                    drop(rejected.value);
                    result
                }
            }
        })
    }

    /// Removes the whole backing pages in `[start, end)`.
    ///
    /// The driver computes these indices by rounding the requested byte/sector
    /// interval inward. Partial edge pages must not reach this method.
    pub(super) fn discard(&self, start: usize, end: usize) {
        let mut guard = self.pages.lock();
        for index in start..end {
            if let Some(detached) = guard.remove(index) {
                // Updates are serialized by this same index guard. A successful
                // removal implies one resident page, so subtraction cannot wrap.
                self.count.store(self.count.load(Relaxed) - 1, Relaxed);
                // No page lock is acquired here. Last-owner destruction only
                // drops Page (__free_pages) and Arc metadata (kfree), both of
                // which are non-sleeping; in-flight Arcs defer this destruction.
                drop(detached);
            }
        }
    }

    /// Returns a count consistent with the index at this locking point.
    pub(super) fn count(&self) -> u64 {
        let _guard = self.pages.lock();
        self.count.load(Relaxed)
    }
}

#[kunit_tests(rusix_brd_store)]
mod tests {
    use super::*;

    fn read_byte(slot: &PageSlot) -> Result<u8> {
        slot.with_page(|page| {
            let mut byte = 0;
            // SAFETY: The destination is one writable byte on this stack. The
            // private, initialized source page is held under its content lock.
            unsafe { page.read_raw(&mut byte, 0, 1)? };
            Ok(byte)
        })
    }

    fn write_byte(slot: &PageSlot, byte: u8) -> Result {
        slot.with_page(|page| {
            // SAFETY: `byte` is initialized stack storage, distinct from the
            // private backing page. Its destination is held exclusively locked.
            unsafe { page.write_raw(&byte, 0, 1) }
        })
    }

    #[test]
    fn lookup_and_repeated_insert_preserve_page() -> Result {
        let store = KBox::pin_init(Store::new(), GFP_KERNEL)?;
        assert!(store.lookup(7).is_none());
        assert_eq!(store.count(), 0);
        let first = store.get_or_insert(7, GFP_KERNEL)?;
        assert_eq!(read_byte(&first)?, 0);
        write_byte(&first, 0xa5)?;
        let second = store.get_or_insert(7, GFP_NOWAIT)?;
        assert!(core::ptr::eq(&*first, &*second));
        assert_eq!(read_byte(&second)?, 0xa5);
        assert_eq!(store.count(), 1);
        Ok(())
    }

    #[test]
    fn discard_keeps_inflight_page_alive_and_reinsert_is_independent() -> Result {
        let store = KBox::pin_init(Store::new(), GFP_KERNEL)?;
        let old = store.get_or_insert(1, GFP_KERNEL)?;
        write_byte(&old, 0x31)?;
        store.discard(1, 2);
        assert!(store.lookup(1).is_none());
        assert_eq!(store.count(), 0);
        let new = store.get_or_insert(1, GFP_KERNEL)?;
        assert!(!core::ptr::eq(&*old, &*new));
        assert_eq!(read_byte(&new)?, 0);
        write_byte(&old, 0x42)?;
        assert_eq!(read_byte(&new)?, 0);
        drop(store);
        assert_eq!(read_byte(&old)?, 0x42);
        assert_eq!(read_byte(&new)?, 0);
        Ok(())
    }

    #[test]
    fn discard_excludes_end_and_is_idempotent() -> Result {
        let store = KBox::pin_init(Store::new(), GFP_KERNEL)?;
        for index in 1..5 {
            store.get_or_insert(index, GFP_KERNEL)?;
        }
        store.discard(2, 4);
        assert!(store.lookup(1).is_some());
        assert!(store.lookup(2).is_none());
        assert!(store.lookup(3).is_none());
        assert!(store.lookup(4).is_some());
        assert_eq!(store.count(), 2);
        store.discard(2, 4);
        store.discard(4, 4);
        assert_eq!(store.count(), 2);
        Ok(())
    }
}
