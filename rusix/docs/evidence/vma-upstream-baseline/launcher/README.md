# Pristine upstream VMA baseline — prepared, not executed

The inputs are Linux `2926d88bb7fc4608fd942453d929c39e4e5ec006`, not the
Rust candidate. The VMA/shared harness and imported VMA implementation files
match reviewed branch `9cf27ef36d1d58cb65bd866d9f046ed2e56b045a` exactly.
The conservative include/lib closure contains six unrelated branch changes;
using pristine Git inputs avoids importing these into the baseline.

`../vma-upstream-baseline-001/inputs/manifest.json` records all 7,748 regular
files/symlinks, modes, hashes, closure paths, source comparison and tooling
provenance. `upstream.tar` SHA256 is
`1ef026291698e8b48ab76925830e4ca4b093dd084375d4cfee8f4426cb590147`.
Manifest SHA256 is
`951c7bd0d8c0faab72e8c0f3d714b41ca1131a5dbb6481bb9e8a727bfadff0a3`.
The first extraction rejected tar data-filter mode stripping; the original
`preparation-failure.json` remains. Explicit retry restored validated Git modes
without changing archive bytes. No compilation occurred during preparation.

The derived image is pinned to
`sha256:3cb67848e1aad76fb1451ebd3b1952961ee9665f73620d4ca8a467aa5e5eb55e`.
`../vma-tooling-001` records installation of liburcu 0.15.2 from the signed dated
snapshot, package inventory and image identity. No host dependency installation.

After parent review and a free shared build/test slot, `run.sh` would acquire
`.wait-owner-remaining.lock`, require a fresh execution directory, and copy the
read-only prepared inputs into its own on-disk output. Container limits are two
CPUs, 2 GiB memory including swap, 15 minutes overall; build/test timeouts are
600/120 seconds. Networking, capabilities and writable root are disabled; no
KVM or host kernel interfaces are provided. Owned-CID signal cleanup preserves
130/143 and all raw logs/statuses. Nothing has been launched.

The unmodified Makefile builds with GCC, ASan and UBSan, `-g -Og -Wall`, and
links pthread/liburcu. Its prescribed sed-generated sources and headers remain
permitted build outputs. Overrides of compiler, make, architecture-size and
sanitizer settings are rejected. Package inventory is normalized with the same
`sort` as the image installation. Every original input type/mode/hash and every
new generated artifact across the entire copied tree is checked after execution.

`check.py` binds the literal upstream 16-case inventory and requires exactly one
`16 tests run, 16 passed, 0 failed.` aggregate, zero exit statuses, no test stderr
and no compiler/sanitizer diagnostics. Build commands, environment, binary,
generated objects, package inventory and launcher inputs are recorded. Failures
remain evidence, never converted to passing or unsupported cases.

This is an upstream **C userspace VMA harness** importing `mm/vma.c`,
`vma_init.c` and `vma_exec.c`. It neither executes `dup_mmap` nor tests Rust
selection, guest kernels, or full Linux behavior. All execution results remain
pending. The only checks run so far are source/archive equality, input manifest
rehashing and Python/shell syntax checks.
