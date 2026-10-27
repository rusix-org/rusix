# VMA modification runtime tooling

Source parent 3a61f8200275b561b5fcf3689874b4fbf2c941b0. This checkpoint implements
an executable verification pipeline; it has not compiled guest fixtures, built a
kernel or booted a VM. Kernel/configuration/selection-gate and native fixture
code are unchanged. Host results: 40 suites/433 cases and two shell syntax checks
pass, with 4,150 source/tool/config/test inputs and HEAD stable before/after.

The explicit --vma-modify mode routes only the new profiles to their actual
modification config/ELF gate; historical lifecycle defaults remain strict.
Actual four-unit preprocessing records, the complete saved nested build proof
and a fresh actual selection check must agree before each boot. Native source
identity binds seven unchanged Linux baseline files and exactly the committed
five -r filters; the ordinary boot uses the existing nine-case contract.

The runner discovers the compiler's 187 dependency inputs before native compilation,
compiles merge.c/vm_util.c/thp_settings.c, and requires matching emitted closure
and hashes afterward. Packages, Rust libraries and actual static link inputs are
recorded. Static x86-64 init/probe artifacts stay 0644 on the host, then enter a
guest-only executable initramfs. Each KVM boot is 512MiB/SMP2/180seconds with strict
exit, warning, extra/duplicate/missing/skip rejection. Failures preserve records;
generated guest executables never appear as host subprocess commands.

Native harness descendants may create separate process groups. The unchanged
reviewed PID1's strict three-second adopted-child cleanup deadline and external
VM timeout contain surviving children and fail closed; this does not certify
unexecuted cleanup races. Allocation rollback, broader MM behavior and actual
kernel compilation/ownership/runtime remain open. Ancestor acceptance and an
independently reviewed launch are still required. Canonical server integration
scope is unchanged. No hosted CI, push, stage or commit occurred during this work.

Source snapshots and raw host logs are current; prior evidence is not copied.
The host dependency inventory is deterministically compressed; manifest hashes
bind both compressed and expanded bytes. Host models do not stand in for actual
preprocessed files, ELF metadata or guest output in the runtime pipeline.
