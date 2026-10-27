# Teardown fixture archive gate correction

Source parent: 0ff7a933c198dda0c3e2c0005e4bb97db3867acc. Production files unchanged.
Actual retained archive lists exit_mmap_test.o while old archive_members rejects
any exit_mmap-like object other than exit_mmap_rust.o. Existing KUnit config and
ELF fixture checker already require the native fixture. The fix narrowly threads
the existing validated test context to archive_members and requires the exact
fixture count there. It does not remove the later fixture registration/payload check.

Focused selection suite: 14 cases PASS. Full host interval: 32 suites, 335 cases
PASS, 4,034 source/tool/config/test hashes stable, exact parent HEAD before/after.
New regressions reject fixture leakage into ordinary profiles, missing/duplicate
fixtures, unknown contexts, alternate objects and incorrect Rust ownership in both
C and Rust contexts. All original tests remain; changed snapshots/diff retained.

Disabled retained artifact reinspection is prepared separately at
../exit-mmap-fixture-gate-reinspection-draft. It has not run. Original matrix 001
remains failed; all downstream runtime prerequisites remain unaccepted. No kernel
build, VM, commit, source reset or original-run modification was performed.
