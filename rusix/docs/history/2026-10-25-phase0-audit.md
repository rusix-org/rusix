# Published bootstrap audit — 2026-10-25

Inspected public revision `5520dd71ea4637bca9e82761463c0df53f3feb46` against
upstream `21a7f44fd0765fcc5194130b28767786eba1d1e7`. Local later changes at
review time were publication-record documentation only.

## Verdict

The code is a defensible **Phase 0 integration proof**, not completed Phase 1.
Retain the square-root implementation. Its runtime change is 60 Rust lines plus
a nine-line C export-metadata shim: it proves bounded ABI/build/test integration,
but exercises no allocation, resource ownership, locks, or device lifecycle.

Two independent agents reviewed the base and a candidate complete component.
This was AI-assisted review, not outside human-maintainer approval. The recorded
arithmetic results remain valid; the findings do not retroactively invalidate them.

## Retain

- Actual Kbuild selection, preserved C ABI/export intent, upstream C reference,
  attribution, and original tests.
- Pinned-C host comparisons plus independent mathematical checks and matching
  C/Rust VM configurations.
- Unsafe invariants, strict case inventories, immutable labels, provenance,
  and explicit limitations.
- Seed evidence (about 472 KiB across 65 files). Future routine output should
  use CI artifacts with committed manifests and durable milestone summaries.

## Material gaps

| Finding | Required correction |
| --- | --- |
| Laptop-specific repository layout | Scripts require `WORKSPACE/linux` and mirrored files outside Git. Make the tracked checkout canonical and relocatable. |
| Observed rather than reproducibly supplied tools | Local package extraction depends on the original host and active Rust toolchain. Supply a pinned independent environment and control identity/time/path inputs using Linux's reproducible-build guidance. |
| No project CI enforcement | Add continuous migration gates, a declared matrix, and retained failure evidence. |
| No useful system workload | The test kernel runs KUnit then reboots. The prepared module-probe init is not ordinary userspace or a stateful subsystem workload. |
| Passing tests do not automatically prove Rust selection | The boot runner can accept the same suites on C. Published manual archive/symbol proof is valid; future automation must require the expected implementation and bind it to the tested image. |
| Narrow architecture/unsafe coverage | i686 host tests are not a 32-bit kernel boot. Module/CRC, CFI/LTO, stateful concurrency and resource/failure behavior remain unverified. Instrumentation must cover the claimed Rust paths. |
| Upstream maintenance is currently a policy | Demonstrate semantic-drift detection and parity restoration for a stateful component. |

## Next direction

[PHASE1.md](../PHASE1.md) defines a reproducible migration base and complete Rust RAM-backed
block driver exercised by Linux userspace. Source inspection confirms real
bio/non-MQ and page-lifetime work is needed; upstream `rnull` is not BRD parity.
The surrounding C block layer/filesystem/allocator remain explicit dependencies.

Immediate priorities are repository-native tooling, a reproducible environment
and implementation-selection checks, then the C baseline contract/workloads and
reviewed ownership design. More disconnected helper ports do not close these gaps.

## Remediation update

Repository-native tooling at `ed5bb5239` removes the parent mirror requirement.
A fresh renamed Git worktree built and passed 26 VM tests using tracked scripts
and default sibling output. Host/path/gate tests also passed; see
[evidence](../evidence/repository-layout/manifest.json). Existing tools were reused,
so the independent-environment and reproducibility findings remain open.
