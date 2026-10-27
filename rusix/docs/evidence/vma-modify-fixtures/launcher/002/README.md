# VMA modification fixture compilation — disabled draft

Compile only; NEVER execute either guest binary. Mutable production candidate
`linux-mm-vma-modify` is not mounted. Native source is clean frozen
`linux-mm-copy-vma` at `99fd3dd96ac0b6131c34501dff9626e95b063037`, mounted read-only.
All seven merge/vm_util/thp_settings/harness inputs match baseline Linux
`2926d88bb7fc4608fd942453d929c39e4e5ec006` bytes and Git blobs. Exact reviewed
Rust PID1/gate/metadata/test/doc snapshots are copied to a separate read-only mount.
The snapshot includes the root's loop-top three-second adopted-child cleanup fix.

Review confirms five exact positive -r filters, one fixture/no variants, and
expected native TAP/RUN/OK formatting directly from the original harness.
This is inferred output, not runtime confirmation. The harness starts additional
process groups: PID1 kills its direct child's group before reaping the leader,
then treats live adopted survivors as cleanup failure. VM poweroff/deadline must
contain those groups in any later runtime job. No successful cleanup or case
execution is claimed by compilation.

Pinned c02 container, 1 CPU/1 GiB/no extra swap, 128 PIDs, five-minute deadline,
no KVM/network/caps, nonroot UID/GID and read-only root. Only evidence, artifacts
and on-disk temporary output are writable. Use pinned image system headers first;
compiler/header/link failures remain retained without patching native tests.

GCC compiles unchanged merge.c, vm_util.c and thp_settings.c separately with
native warning/optimization conventions, adds diagnostic rejection and links
statically with -lrt -lpthread -lm. Exact native dependencies (including system
headers), package/compiler versions and linker trace are recorded. Rust builds
PID1 for x86_64 with static CRT, panic-abort and optimization. readelf checks both
for ELF64 x86-64 and absent INTERP/NEEDED. Resulting binaries are mode0644 and are
never invoked, including in the container. Timeout/failure cleanup retains logs
and applies mode0644 to any partial binaries.

REVIEWED_LAUNCH_READY is False. Root review of this concrete launcher and frozen
snapshot is required before enablement. No Docker command or compile has run.
