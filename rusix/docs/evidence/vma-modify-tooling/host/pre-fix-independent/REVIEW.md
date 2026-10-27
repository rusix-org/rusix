# Independent VMA modification tooling review

Verdict: no concrete blocker found in the frozen 13-file source/tooling change.
Scope is tooling source review and host regressions, not successful emitted-kernel
ownership or runtime evidence. No build, container, VM or guest probe was run.

Production source remains commit 966869b130e8d453b00dc24224e4ff59a415379a;
`git diff --name-only -- mm kernel rust init` is empty. Full interval HEAD is
identical before/after. The 13 tooling/config/test hashes are in reviewed-files.json.
The corrected full-interval sweep passes 39 suites / 416 cases plus shell syntax,
with 4,157 script/config/test and source dependency hashes unchanged. Project
scripts/configs/tests/CI snapshots are retained under full-interval/inputs; native
source paths are exhaustively hashed and bound to the unchanged commit. The first
successful sweep covered only 95 direct inputs and is retained without claiming
the broader interval. No test failures occurred. Whitespace checks pass.

Reviewed proof chain:

- vma-modify-v1 is explicit in source, copy, teardown and ancestor restoration.
  Unknown contexts reject; default historical source scope rejects modified vma.c.
  Exact selected-region and whole-file restoration preserves all 11 C policies;
  canonical ABI, Rust implementation and 70-primitive source hashes are pinned.
- Four original compiler units use saved actual commands, freshly generated .i
  files, exact input/output/argv/cwd provenance records and zero-status diagnostics
  checks. The new gate reads actual vma.i; no synthetic prepare body is substituted.
- Ten Rust exported owners cover the 11-policy inventory because private modify
  can inline into four reviewed public consumers. Exact source identity binds that
  private policy. C wrappers, original-policy exclusion, critical primitive bodies,
  canonical declarations and native merge/shrink dispatch are checked.
- Actual archive membership is unique and extracted member hashes match inspected
  objects. llvm-nm and actual llvm-readobj executable-function metadata bind C,
  Rust and linked owners; all 70 primitives have Rust executable calls. No metadata
  is constructed to stand in for an actual artifact.
- Split callback transfer checks require the two actual transfers and getter calls.
  Rust control flow is pinned by reviewed source hashes; this does not establish
  dynamic callback/race behavior.
- Inherited copy verification declares exactly the deferred Rust-prepare obligation.
  The outer gate requires that declaration, then checks real Rust prepare lock and
  locked-file-link executable relocations exactly once and in order before returning
  PASS with consumed_outer_obligations. The inner scope explicitly limits its claim.
- Config fragments retain all inherited selectors and differ solely on modification.
  Modeled host config tests are not Kconfig resolution. Build routing checks config
  before and after build, preprocesses, then runs the object checker. No CI/runtime
  stub is added and legacy runner profiles remain unchanged.

The actual compiler may expose a fail-closed ABI/disassembly expectation mismatch;
no object checker success is claimed before real compilation. Resolve such failures
against original artifacts, retaining failed results, rather than fabricating
expected metadata or relaxing the contract without review. Dynamic split/merge,
failure, race and userspace behavior remain subsequent gates.
