# Copy-VMA configuration check — disabled draft

Source is clean `344b3b272c4e94ac5f7d337baa47dbd244bef191` in
`linux-mm-copy-vma`. Root review and explicit readiness enablement are required.
Do not run the launcher yet. Fresh output: `linux-out/copy-vma-config-001`.

The launcher archives exact committed source with `git archive`, excluding only
`rusix/docs/evidence`. The omitted prior evidence is referenced by source commit
and Git tree identity in `snapshot.json`, not recursively copied. The archived
files, modes and symlinks must match the extracted read-only snapshot exactly.
Input inventories are rehashed before and after config resolution.

Pinned image c02 runs for at most five minutes, with 1 CPU/1 GiB, no network,
capabilities, KVM or other devices, and a read-only root/source. Only fresh output
and scratch directories are writable. Owned-container cleanup records actual
exit/inspect evidence, including interrupted runs. No shared mutable build cache.

Only `make LLVM=1 KCONFIG_ALLCONFIG=... allnoconfig` is requested, separately for
`copy-vma-c` and `copy-vma-rust`. Every requested fragment value must survive;
`verify-copy-vma.py` checks each actual configuration and the pair may differ only
by `CONFIG_RUSIX_COPY_VMA_RUST`. MEMFD_CREATE must be enabled for the unchanged
native shmem case; KUnit and all Rusix test fixtures must remain disabled.

Record commands, tool/package versions, resolved configurations, statuses,
source archive/inventories, launcher hashes and original source cleanliness.
Generated dependencies remain in raw output with exhaustive identities for a
future concise archive. No kernel objects, guest compilation, ELF selection or
VM execution are requested or established by this configuration check.

Root review caught a wrong verifier import in the original disabled checker.
`pre-review/` preserves that checker byte-identically against its original prepared
hash and records the review finding; no container was run. The corrected checker
requires exactly the two copy-VMA profiles. `host-check.py` evaluates its actual
import expression, validates both fragments with explicit modeled derived flags,
rejects a foreign profile, and proves the archive paths include every selected
source dependency. This is a host wiring check, not Kconfig evidence.
