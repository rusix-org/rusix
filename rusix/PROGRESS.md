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

Build, image, configuration, tool and raw result identities are in those records.
Known historical failures/warnings and session details are in the
[bootstrap record](docs/history/2026-10-25-bootstrap.md). Unsafe design obligations
and upstream abstraction research are in [BRD.md](docs/BRD.md).

## Current work

- ADR 0002 approved; active docs consolidated around it. BRD baseline and evidence
  published through `11789442b`.
- Pinned Debian container built locally; container preflight, native host tests
  and tooling regressions pass. Full container/hosted CI verification is pending.
- Linked-language measurement script implemented; declared-target build/report
  is pending. Report retained executable, file-backed allocated and BSS bytes
  separately, including assembly/generated/unknown contributions. Inherited Rust
  support code must not be presented as newly rewritten code.
- Outer script stubs and unpublished module runner/tests removed. The apparent
  outer `.git` is a sandbox-only read-only mount; that path is absent outside the
  sandbox. The real repository is `linux/.git`.

## Next executable work

1. Complete container and hosted CI verification, build the declared x86_64
   configuration and record its linked-language report.
2. Import/review the pinned LTS on a separate branch, inventory required newer
   Rust interfaces, and rerun existing compatibility evidence before adoption.
3. Audit/reuse upstream xarray, allocation-scope, bio and SafePage proposals before
   implementing the complete Rust BRD data path and lifecycle.
4. Run the same BRD tests on Rust, add ordinary userspace/ext4, then execute the
   early core-ownership spike and Phase 1b hardening described in the roadmap.
