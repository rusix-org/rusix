# MM construction guest consumers

Source candidate only: twelve host gate tests pass; no guest compilation or VM execution yet. These five
ordinary-userspace cases exercise successful constructor paths; they do not
provide allocation-failure coverage or establish ownership of live address spaces.

| Exact case | Observable contract |
| --- | --- |
| `anonymous_private_fork_cow` | Three populated anonymous private pages survive fork; child observes then changes every byte and unmaps, while parent retains its original bytes. |
| `child_mapping_survives_parent_unmap` | Parent unmaps before sending a pipe token; only then does child read/write its inherited mapping and unmap. |
| `repeated_fork_exec_reap` | 32 fork/exec/reap iterations preserve the parent's mapping; an initialized global sentinel proves the child ran a fresh ELF image. |
| `mdwe_inherited_fork_exec` | REFUSE_EXEC_GAIN remains in the parent, fork child, fork+exec child and direct-exec worker; writable-to-executable mprotect fails EACCES. |
| `mdwe_no_inherit_fork_exec` | Parent retains both flags, fork child and fork+exec child see zero; direct exec from the still-flagged parent also clears both. Writable-to-executable mprotect succeeds only in cleared contexts. |

The oracle is pinned Linux 6.18.58: `kernel/sys.c:prctl_set_mdwe` rejects
NO_INHERIT without REFUSE_EXEC_GAIN with EINVAL and changing established flags
with EPERM. `include/linux/mm_types.h:mmf_init_legacy_flags` clears both MDWE bits
when NO_INHERIT is set; both copied `dup_mm` and fresh exec `mm_alloc` reach this
policy. `include/linux/mman.h:map_deny_write_exec` and `mm/mprotect.c` enforce
EACCES on execute permission gain. The test never executes generated code.
Unsupported behavior fails; it is never converted to a skip or pass.

The supervisor requires direct parent PID 1. All processes independently check
one exact `rusix.mm_construction_probe=1` cmdline token and PID1 comm
`rusix-mm-init`. Static Rust init mounts proc, sets that comm, directly runs the
static C `/probe`, then powers off. No guest executable may run on the host.
Each case runs in its own process group; irreversible MDWE state cannot affect
later cases. The subreaper observes the worker with WNOWAIT, retaining PID/PGID
until owned-group cleanup completes. Observation is bounded to ten seconds per
case, child waits to two/three seconds and cleanup to one second. The external
180-second q35/KVM watchdog contains a stuck kernel. Time is supervision, not
proof of COW or synchronization.

`test-mm-construction-vm.py BUILD LABEL --build-evidence EVIDENCE` requires
clean recorded source, matching successful build/config, diagnostic-free logs,
actual rechecked MM/task ELF and preprocessed selection, pinned ext4-image
package inventory, static x86_64 executables and immutable copied kernel. It
reuses the frozen task runner's compilation/newc/ELF helpers without changing
its fixtures. Imported tools, source fixtures, selected artifacts and commands
are hashed before compilation and rechecked after compilation and VM execution. KVM SMP2 and 512 MiB are mandatory. The exact five ordered case
markers and final overall marker must all pass; missing, duplicate, unknown,
failed, skipped, reordered or diagnostic-bearing results are rejected.

Example (inside the reviewed pinned container, after a successful kernel build):

```
python3 rusix/scripts/test-mm-construction-vm.py /out/builds/ci-mm-construction-c \
  ci-mm-construction-c --build-evidence /out/logs/ci-mm-construction-c-build.UNIQUE
```

Requires `RUSIX_QEMU_ACCEL=kvm` and inspected `RUSIX_EXT4_IMAGE_ID`. Keep the
corresponding C/Rust profiles identical except the MM selector. Host gate tests
exercise parser/config/staging behavior only; source compilation, boot,
constructor selection and observed userspace behavior remain separate gates.
