# VMA modification tooling checkpoint

Final host regressions: 39 suites / 421 cases, 4,157 unchanged inputs. Earlier
independent 39/416 results and the implementer after-only sweep retain their own
identities and scope. The only post-review source changes are the four approved
teardown archive/sentinel gate and regression files, tracked by AST equivalence
and full-file equality where appropriate. Production remains committed 966869b.

This verifies tooling source/models, not an emitted VMA-modify kernel. Build-only
profiles preserve CI refusal until the actual ordinary runner exists. Ten Rust
exports represent eleven native policies (the shared modify policy can inline);
actual selection proof is implemented but has not run on this candidate.

The referenced teardown fix was inspected against retained source0ff7 KUnit C
artifacts, not a new VMA-modify build. The original teardown attempt failed and
requires its own retry. Do not infer VM acceptance from that ELF reinspection.

Prior evidence is referenced by commit and manifest, never recursively included.
Native dependency inputs are exhaustive hashes bound to unchanged source HEAD;
project source/config/test/tool snapshots are included once. Pre-fix project
sources reconstruct from the final snapshots plus four source-pre-fix files.
No generated build tree, binaries, VM, hosted CI, staging or commit was produced
by this archive operation.
