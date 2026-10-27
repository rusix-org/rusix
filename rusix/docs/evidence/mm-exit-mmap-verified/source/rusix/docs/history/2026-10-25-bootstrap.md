# Bootstrap record — 2026-10-25

Historical results use source `21a7f44fd0765fcc5194130b28767786eba1d1e7`,
not the subsequently selected 6.18.58 LTS. Full earlier session entries remain
in Git history at `11789442b:rusix/PROGRESS.md`.

| Step | Result / record |
| --- | --- |
| Source and tools | Linux shallow clone; project branch and upstream remote established. System package install needed an unavailable sudo password, so hashed Arch packages were extracted locally without hooks. |
| Rust baseline | KUnit kernel built/booted; initial 23 cases passed. |
| First replacement | Rust integer square root selected through Kbuild with a metadata-only C export shim. Original C/header/tests preserved. Native and i686 differential host tests passed. |
| Committed parity | C `b46d927d0` and Rust `e87d0bc14` each passed the same 26 VM cases with identical configurations. [Evidence](../evidence/int-sqrt/manifest.json). |
| Module preparation | VM-only Rust init and non-GPL-compatible consumer fixture compiled/reviewed. Module runtime/CRC verification was not performed. Unpublished outer runner drafts were later deleted during workspace cleanup. |
| Publication | Empty standalone remote renamed to `rusix-empty-placeholder` after GitHub denied deletion without the token scope. Created the official Linux fork; first source push `5520dd71e`. GitHub retains ancestry although the local clone is shallow. |
| Independent reproduction | Fresh worktree reproduced build/26 VM cases with the same host tools. [Evidence](../evidence/publication-check/manifest.json). |
| Scope audit | The helper was classified as Phase 0, and the RAM-backed block driver selected for a stateful migration. The initial larger Phase 1 and continuous-upstream policy were subsequently superseded by ADR 0002. |
| Repository cleanup | Parent mirrors retired at `ed5bb5239`; renamed-worktree build/26 VM cases passed. [Evidence](../evidence/repository-layout/manifest.json). |
| BRD baseline | Source `976e2de80`: six C driver cases passed in a two-CPU VM, including 64 competing-insertion rounds. [Evidence](../evidence/brd-c-baseline/manifest.json). |

## Failures and limitations retained

- Initial sandbox clone failed DNS; authorized network access resolved it.
- Initial allnoconfig omitted the parent test menu; the build was interrupted,
  configuration corrected, and retained options checked thereafter.
- Initial KUnit parser invocation needed `--json=PATH` and an absolute path.
- Initial i686 checks lacked linker/runtime libraries; the sandbox also rejected
  native 32-bit syscalls. Explicit QEMU userspace emulation passed, and native
  execution passed outside the sandbox. Neither result is a 32-bit kernel test.
- The original Rust spinlock test prints an upstream deprecated-workqueue warning.
  Build records include a jobserver warning and unused `Flags::from_raw` warning;
  the latter also appears in the publication, relocation and BRD builds.
- Original local logs are retained under the workspace `logs/`; selected raw
  records and hashes are committed in the linked manifests. These builds reused
  the laptop's tools and did not establish clean-worker reproducibility.
