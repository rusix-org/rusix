# Progress

**Active: Phase 1a.** The Rust integer-square-root replacement and C BRD baseline
are verified. Rust BRD, the core rewrite and ordinary userspace/ext4 verification
are unfinished. [ADR 0002](docs/adr/0002.md) defines the target and completion rule;
[the roadmap](docs/ROADMAP.md) defines the order.

## Source and target

- Behavioral target: Linux **6.18.58 LTS**, commit
  `2926d88bb7fc4608fd942453d929c39e4e5ec006`.
- Current engineering source: `21a7f44fd0765fcc5194130b28767786eba1d1e7`.
  The LTS transition has not been performed; existing results do not certify it.
- Public fork: [rusix-org/rusix](https://github.com/rusix-org/rusix), branch
  `rusix/main`. Tracked `rusix/` is canonical. The local checkout is shallow.
- Declared scope: x86_64/arm64 SMP, 4 KiB pages, virtio block/network, ext4 and
  the process/memory/network core in ADR 0002. Other drivers are outside scope.

## Verified evidence

| Candidate | Result | Evidence |
| --- | --- | --- |
| C `b46d927d0` / Rust `e87d0bc14` | Same 26 KUnit cases pass; native 3 / emulated i686 5 host cases pass | [Math parity](docs/evidence/int-sqrt/manifest.json) |
| `ed5bb5239` | Renamed worktree builds; 26 VM, 3 native, 5 i686, 9 gate and 6 path tests pass | [Repository workflow](docs/evidence/repository-layout/manifest.json) |
| `976e2de80` | C BRD: 6 VM cases, 64 competing-insertion rounds; 15 runner regressions pass | [BRD baseline](docs/evidence/brd-c-baseline/manifest.json) |
| `41f9d1ce2` | Fresh pinned-container BRD build and 6 cases pass locally under KVM; native 3 and tooling 40 pass | [Container verification](docs/evidence/container-verification/manifest.json) |
| Kernel `4dd0b2c9f`, runner `41f9d1ce2` | Existing KUnit image replayed locally under KVM: 26/26 pass | [Replay identities](docs/evidence/container-verification/local-kunit-replay/replay-inputs.json) |

Build, image, configuration, tool and raw result identities are in those records.
Known historical failures/warnings and session details are in the
[bootstrap record](docs/history/2026-10-25-bootstrap.md). Unsafe design obligations
and upstream abstraction research are in [BRD.md](docs/BRD.md).

## Linked-language baseline

The declared **x86_64 server** profile built at `4dd0b2c9f` in the pinned
container. Retained executable-section bytes from its recorded ELF/link map:

| Attribution | Bytes |
| --- | ---: |
| C compilation units | 5,993,765 |
| Rust compilation units | 151,830 |
| Assembly | 44,780 |
| Generated units | 28 |
| Linker script/alignment | 2,109,639 |
| Unknown | 0 |

Rust includes inherited support code; the new `int_sqrt` port contributes 109
executable bytes. [The full report](docs/evidence/container-verification/server-measurement/languages.json)
separates file-backed data/BSS and records hashes, object provenance and exclusions
(including the bzImage decompressor). Arm64 configuration resolves but has not
been built or measured. These figures precede the LTS transition.

## Execution policy and current state

- **Local testing only for now.** Hosted workflow disabled and manual-only;
  revisit at Phase 1a review readiness only with an explicit request. See
  [execution policy](ci/README.md).
- The first hosted run completed with KUnit/server passing and BRD failing; the
  replacement run was cancelled for budget. Neither is an overall green CI claim.
- Initial container BRD failed because the guest saw one CPU. TCG/KVM diagnostics
  isolated ACPI enumeration and a separate host-CPU feature warning. ACPI and the
  portable `qemu64` KVM model fixed both; failure evidence is retained alongside
  the successful local run above.
- ADR 0002 applied; outer script stubs and unpublished module-runner drafts removed.
  The apparent outer `.git` is a sandbox-only read-only mount, absent on the host.

## Next executable work

1. Import/review the pinned LTS on a separate branch, inventory required newer
   Rust interfaces, and rerun existing compatibility evidence before adoption.
2. Audit/reuse upstream xarray, allocation-scope, bio and SafePage proposals before
   implementing the complete Rust BRD data path and lifecycle.
3. Run the same BRD tests on Rust, add ordinary userspace/ext4, then execute the
   early core-ownership spike and Phase 1b hardening described in the roadmap.
