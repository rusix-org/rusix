# Disabled retained teardown KUnit C reinspection

Original matrix 001 failed at the unexpected native fixture archive member before
any KUnit guest boot. The ordinary C/Rust nine-case runs do not establish the
required KUnit acceptance. The original source and failed raw run remain immutable.

This draft mounts original source 0ff7a933c198dda0c3e2c0005e4bb97db3867acc and
retained KUnit C objects/logs read-only. Fixed verifier code is loaded separately
from linux-mm-exit-mmap-fix, with each executed Python module hashed explicitly.
Only verify-exit-mmap.py and exit_kunit_elf.py differ; all other verifier scripts equal the original. Original source/config/artifact
hash attribution remains 0ff7; the corrected checker is not mislabeled as code
that ran during the original build. Only a new inspection output is writable.

The script validates all four original preprocessing provenance records, statuses
and diagnostics, then constructs only path-remapped record copies in new evidence.
It never generates or changes .i files. Saved nested lifecycle/dup/copy proofs
must agree before inspection; the complete reinspected nested result must compare
exactly after remapping only typed path maps. The actual top-level verifier runs
all object/archive/linked checks and existing native fixture ELF registration,
helper and payload proof. No KUnit logs are synthesized and no guest is executed.
Exhaustive retained raw hashes and both source/tooling identities must remain
unchanged throughout. A new successful result does not change matrix 001's failure
or accept copy/PFN runtime prerequisites; a fresh retry at the fixed commit is needed.

Readiness is false. Root review is required before enabling or running. Bounds:
pinned c02 image, one CPU, 2 GiB, 128 PIDs, five minutes, no network, capabilities,
KVM device, compiler invocation or VM. Docker inspect and exit records are retained.

This second draft also carries the narrowly corrected canonical Rust case terminator
check: NORMAL speed is 3 at offset 24; all other bytes must be zero, no relocation
is allowed, and original C enum definitions/generated values plus the exact pinned
Rust constructor are validated. Prior reinspection 001 failed at the all-zero
terminator assumption; its output and the original matrix remain untouched.
