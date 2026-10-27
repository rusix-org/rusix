# MM release lifecycle fixtures

Source fixtures only; paired C-first kernel execution remains pending. The
isolated `rusix_mm_release` inventory has four cases. The strict combined gate
requires these plus the existing nine BRD and 67 core cases (80 total).

Each case runs in a private kthread with a retained task reference acquired
before wake. The worker and controller separately retain fixture storage. The
controller waits at most ten seconds, reads results only after completion, and
releases its reference before KUnit assertions. It never performs `mmput`,
`mmdrop` or `flush_work`. A blocked worker retains its reference; uncertain
teardown records failure and retains MM/fixture/task references. Kernel deadlock
or broken reclamation still requires the external VM timeout for containment.

- Nonfinal synchronous and asynchronous user releases preserve the same actual
  anonymous stack VMA after `mmget`. No work flush is attempted for a nonfinal
  asynchronous release, since that path does not initialize its work item.
- Final users release destroys the VMA tree while an explicit `mmgrab` preserves
  MM storage, PGD and RSS counter backing. Final `mmdrop` runs only after these
  observations. Stale `map_count` and `total_vm` are not cleanup oracles.
- Final `mmput_async` runs with IRQs disabled, restores caller IRQ state, then
  the retained worker uses `flush_work` to observe completed process-context
  cleanup. The extra storage reference keeps embedded work alive throughout.
- A fresh initialized MM with no inserted VMA follows the exec-error-style
  direct `mmdrop` path with `mm_users == 1`. Successful return is observed without
  accessing the freed descriptor. This does not induce an actual exec failure.

The fixture uses canonical `mm_alloc` and `create_init_stack_vma`, not fabricated
refcounts or production test hooks. It never adopts the MM as `current->mm` or
faults user pages into it. Fresh private-futex fields are NULL, so these cases do
not establish quiescence for live-MM private-futex RCU callbacks. Ordinary COW
and exec consumers, attributable allocation failures, linked selection proof and
paired runtime validation remain separate requirements.
