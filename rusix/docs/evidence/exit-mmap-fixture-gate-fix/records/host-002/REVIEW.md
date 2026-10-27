# Canonical Rust KUnit terminator metadata fix

Original source is frozen 0ff7a933c198dda0c3e2c0005e4bb97db3867acc. No production
source changed. Prior archive-fix review 001 and failed retained reinspection 001
remain separate and untouched. Actual object and linked sentinel diagnosis is
../exit-mmap-kunit-sentinel-review-001/actual.json: only byte 24 is nonzero (3),
run_case is null and no relocations exist. Pinned kunit_case_null uses NORMAL speed
and SUCCESS status; the actual generated values are 3 and 0 respectively.

The checker now requires exact canonical C enum definitions, generated u32 enum
aliases and these two values, plus the normalized SHA256 of the exact pinned Rust
constructor. Existing struct-layout signatures still bind offsets. Exactly 72
bytes are compared with speed3 at offset24 and every other byte zero; all sentinel
relocations remain rejected. It does not accept arbitrary NULL-run-case records.
New synthetic negatives reject all-zero/wrong-speed/status/pointer/padding records,
relocations, truncation and changed enum values/types or constructor behavior.

Focused fixture suite: 11 cases PASS. Full host interval: 32 suites / 338 cases
PASS, 4,034 input hashes and parent HEAD stable. New disabled reinspection draft
../exit-mmap-fixture-gate-reinspection-002-draft pins the same 694 original source
inputs and 4,673 original raw inputs, while separately attributing 40 fixed tooling
modules (only archive verifier and fixture ELF checker differ). Full nested actual
reinspection remains required; it has not been run. Original matrix remains failed.

PFN's separate old checker shares this all-zero assumption. Its old runtime draft
must remain disabled until a separately reviewed fix propagation and prerequisites
are complete. No PFN source changed here. No build, VM, commit or reinspection run.
