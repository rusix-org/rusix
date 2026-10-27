# Disabled four-profile configuration check

Preparation only. Await the final clean routing commit; run.sh has ready=0 and
source_commit=REVIEW_PENDING. Root must review and enable both after validating
the complete profile/config gate source. No configuration execution has occurred.

The candidate uses a fresh immutable git archive, pinned c02 toolchain image,
1 CPU/1 GiB, no network/KVM/capabilities, and a five-minute owned-container timeout.
It may coexist with the heavy verification queue only under this explicit
configuration-only authorization: source is the fixed archive, never a mutable
shared worktree. On-disk output and TMPDIR avoid tmpfs build storage.

Each of four profiles runs only allnoconfig, which builds host configuration
utilities. Exact requested settings including explicit n values, imported config
gates and C/Rust selector-only pair comparisons must pass. Expected resolved
ordinary→KUnit changes are exactly KUNIT, RUNTIME_TESTING_MENU,
KUNIT_DEFAULT_ENABLED, KUNIT_AUTORUN_ENABLED, RUSIX_EXIT_MMAP_TEST n→y, and
KUNIT_DEFAULT_TIMEOUT n→300. These derive from pinned KUnit Kconfig and existing
resolved ordinary/release evidence; the eventual actual resolution is mandatory.
GLOB is already enabled in ordinary profiles. Any additional delta fails closed.
The separate MM-release fixture stays disabled. Profile/derived-setting changes
require review, not automatic expected-delta regeneration.

All source files and symlink targets are inventoried before and after. Preserve
archive identity, actual commands/logs/exits, compiler/package versions, resolved
configs and launcher hashes. This provides no kernel compilation, ELF selection,
callback ABI, fixture execution, runtime parity or allocation-failure evidence.

Archive integrity is checked against each tar member (bytes, modes, symlink
targets and exact inventory) after extraction and again in-container before and
after configuration. GNU tar preserves the archived modes explicitly. The
manifest binds original source.tar by SHA256. Actual image inspect and retained
container inspect capture limits, mounts/devices and exit/OOM state before the
owned cleanup removes the stopped container; --rm is intentionally absent.
