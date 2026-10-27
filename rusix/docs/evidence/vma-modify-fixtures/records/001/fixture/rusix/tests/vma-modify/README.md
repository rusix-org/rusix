# VMA modification native fixture

Run the unchanged pinned Linux `tools/testing/selftests/mm/merge.c` with five
explicit `-r merge.<case>` filters from `upstream.json`. Its original
`kselftest_harness.h` matches these complete names and excludes other cases.
`vm_util` supplies the native PROCMAP_QUERY topology assertions; no test bodies
are copied or changed. Baseline source/blob hashes bind the seven native inputs.

Guest-only x86-64 PID1 mounts proc, requires exactly one
`rusix.vma_modify_probe=1` token, and runs the child with a cleared environment.
A 60-second watchdog preserves the unreaped leader before process-group cleanup;
PID1 then bounds adopted-descendant reaping. The native harness creates extra
process groups: surviving children cause cleanup failure, and the disposable
VM deadline/poweroff contains them. Never execute these binaries on the host or
in a container. Supply `/proc`, `/dev/console`, `/init` and `/probe` in the archive.

Source construction is complete; static compilation, exact console acceptance,
linked policy selection and C/Rust VM execution remain pending. These five
success cases do not certify allocation rollback, callback counts, optional
configuration paths or complete MM behavior.
