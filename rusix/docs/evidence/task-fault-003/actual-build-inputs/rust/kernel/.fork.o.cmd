savedcmd_kernel/fork.o := clang -Wp,-MMD,kernel/.fork.o.d -nostdinc -I/src/arch/x86/include -I./arch/x86/include/generated -I/src/include -I./include -I/src/arch/x86/include/uapi -I./arch/x86/include/generated/uapi -I/src/include/uapi -I./include/generated/uapi -include /src/include/linux/compiler-version.h -include /src/include/linux/kconfig.h -include /src/include/linux/compiler_types.h -D__KERNEL__ --target=x86_64-linux-gnu -fintegrated-as -Werror=unknown-warning-option -Werror=ignored-optimization-argument -Werror=option-ignored -Werror=unused-command-line-argument -fmacro-prefix-map=/src/= -std=gnu11 -fshort-wchar -funsigned-char -fno-common -fno-PIE -fno-strict-aliasing -mno-sse -mno-mmx -mno-sse2 -mno-3dnow -mno-avx -mno-sse4a -fcf-protection=none -m64 -falign-loops=1 -mno-80387 -mno-fp-ret-in-387 -mstack-alignment=8 -mskip-rax-setup -march=x86-64 -mtune=generic -mno-red-zone -mcmodel=kernel -mstack-protector-guard-reg=gs -mstack-protector-guard-symbol=__ref_stack_chk_guard -Wno-sign-compare -fno-asynchronous-unwind-tables -mretpoline-external-thunk -mindirect-branch-cs-prefix -mfunction-return=thunk-extern -fpatchable-function-entry=16,16 -fno-delete-null-pointer-checks -O2 -fstack-protector-strong -fomit-frame-pointer -ftrivial-auto-var-init=zero -fno-stack-clash-protection -falign-functions=16 -fstrict-flex-arrays=3 -fno-strict-overflow -fno-stack-check -fno-builtin-wcslen -Wall -Wextra -Wundef -Werror=implicit-function-declaration -Werror=implicit-int -Werror=return-type -Werror=strict-prototypes -Wno-format-security -Wno-trigraphs -Wno-frame-address -Wno-address-of-packed-member -Wmissing-declarations -Wmissing-prototypes -Wframe-larger-than=2048 -Wno-gnu -Wno-format-overflow-non-kprintf -Wno-format-truncation-non-kprintf -Wno-pointer-sign -Wcast-function-type -Wimplicit-fallthrough -Werror=date-time -Werror=incompatible-pointer-types -Wenum-conversion -Wunused -Wno-unused-but-set-variable -Wno-unused-const-variable -Wno-format-overflow -Wno-override-init -Wno-pointer-to-enum-cast -Wno-tautological-constant-out-of-range-compare -Wno-unaligned-access -Wno-enum-compare-conditional -Wno-missing-field-initializers -Wno-type-limits -Wno-shift-negative-value -Wno-enum-enum-conversion -Wno-sign-compare -Wno-unused-parameter -I/src/kernel -Ikernel    -DKBUILD_MODFILE='"kernel/fork"' -DKBUILD_BASENAME='"fork"' -DKBUILD_MODNAME='"fork"' -D__KBUILD_MODNAME=kmod_fork -c -o kernel/fork.o /src/kernel/fork.c   ; ./tools/objtool/objtool --hacks=jump_label --hacks=noinstr --hacks=skylake --orc --retpoline --rethunk --static-call --uaccess --prefix=16   kernel/fork.o

source_kernel/fork.o := /src/kernel/fork.c

deps_kernel/fork.o := \
    $(wildcard include/config/PROVE_RCU) \
    $(wildcard include/config/VMAP_STACK) \
    $(wildcard include/config/THREAD_INFO_IN_TASK) \
    $(wildcard include/config/SECCOMP) \
    $(wildcard include/config/MMU) \
    $(wildcard include/config/MM_ID) \
    $(wildcard include/config/TRANSPARENT_HUGEPAGE) \
    $(wildcard include/config/SPLIT_PMD_PTLOCKS) \
    $(wildcard include/config/MMU_LAZY_TLB_SHOOTDOWN) \
    $(wildcard include/config/DEBUG_VM_SHOOT_LAZIES) \
    $(wildcard include/config/ARCH_WANTS_DYNAMIC_TASK_STRUCT) \
    $(wildcard include/config/RUSIX_TASK_CONSTRUCTION_RUST) \
    $(wildcard include/config/STACKPROTECTOR) \
    $(wildcard include/config/BLK_DEV_IO_TRACE) \
    $(wildcard include/config/FAULT_INJECTION) \
    $(wildcard include/config/BLK_CGROUP) \
    $(wildcard include/config/ARCH_HAS_CPU_PASID) \
    $(wildcard include/config/MEMCG) \
    $(wildcard include/config/X86_BUS_LOCK_DETECT) \
    $(wildcard include/config/SCHED_MM_CID) \
    $(wildcard include/config/BPF_SYSCALL) \
    $(wildcard include/config/AIO) \
    $(wildcard include/config/UPROBES) \
    $(wildcard include/config/PER_VMA_LOCK) \
    $(wildcard include/config/FUTEX_PRIVATE_HASH) \
    $(wildcard include/config/DETECT_HUNG_TASK) \
    $(wildcard include/config/POSIX_TIMERS) \
    $(wildcard include/config/CGROUPS) \
    $(wildcard include/config/RT_MUTEXES) \
    $(wildcard include/config/PREEMPT_RCU) \
    $(wildcard include/config/TASKS_RCU) \
    $(wildcard include/config/TASKS_TRACE_RCU) \
    $(wildcard include/config/RV) \
    $(wildcard include/config/PROVE_LOCKING) \
    $(wildcard include/config/ARCH_HAS_SCALED_CPUTIME) \
    $(wildcard include/config/VIRT_CPU_ACCOUNTING_GEN) \
    $(wildcard include/config/IO_URING) \
    $(wildcard include/config/PSI) \
    $(wildcard include/config/NUMA) \
    $(wildcard include/config/CPUSETS) \
    $(wildcard include/config/TRACE_IRQFLAGS) \
    $(wildcard include/config/BCACHE) \
    $(wildcard include/config/BLOCK) \
    $(wildcard include/config/GENERIC_ENTRY) \
    $(wildcard include/config/KRETPROBES) \
    $(wildcard include/config/RETHOOK) \
    $(wildcard include/config/LRU_GEN_WALKS_MMU) \
    $(wildcard include/config/CLONE_BACKWARDS) \
    $(wildcard include/config/CLONE_BACKWARDS2) \
    $(wildcard include/config/CLONE_BACKWARDS3) \
    $(wildcard include/config/STACK_GROWSUP) \
  /src/include/linux/compiler-version.h \
    $(wildcard include/config/CC_VERSION_TEXT) \
  /src/include/linux/kconfig.h \
    $(wildcard include/config/CPU_BIG_ENDIAN) \
    $(wildcard include/config/BOOGER) \
    $(wildcard include/config/FOO) \
  /src/include/linux/compiler_types.h \
    $(wildcard include/config/DEBUG_INFO_BTF) \
    $(wildcard include/config/PAHOLE_HAS_BTF_TAG) \
    $(wildcard include/config/FUNCTION_ALIGNMENT) \
    $(wildcard include/config/CC_HAS_SANE_FUNCTION_ALIGNMENT) \
    $(wildcard include/config/X86_64) \
    $(wildcard include/config/ARM64) \
    $(wildcard include/config/LD_DEAD_CODE_DATA_ELIMINATION) \
    $(wildcard include/config/LTO_CLANG) \
    $(wildcard include/config/HAVE_ARCH_COMPILER_H) \
    $(wildcard include/config/KCSAN) \
    $(wildcard include/config/CC_HAS_ASSUME) \
    $(wildcard include/config/CC_HAS_COUNTED_BY) \
    $(wildcard include/config/CC_HAS_MULTIDIMENSIONAL_NONSTRING) \
    $(wildcard include/config/UBSAN_INTEGER_WRAP) \
    $(wildcard include/config/CFI) \
    $(wildcard include/config/ARCH_USES_CFI_GENERIC_LLVM_PASS) \
    $(wildcard include/config/CC_HAS_ASM_INLINE) \
  /src/include/linux/compiler-context-analysis.h \
  /src/include/linux/compiler_attributes.h \
  /src/include/linux/compiler-clang.h \
    $(wildcard include/config/ARCH_USE_BUILTIN_BSWAP) \
    $(wildcard include/config/CLANG_VERSION) \
    $(wildcard include/config/CC_HAS_TYPEOF_UNQUAL) \
  /src/include/linux/anon_inodes.h \
  /src/include/linux/types.h \
    $(wildcard include/config/HAVE_UID16) \
    $(wildcard include/config/UID16) \
    $(wildcard include/config/ARCH_DMA_ADDR_T_64BIT) \
    $(wildcard include/config/PHYS_ADDR_T_64BIT) \
    $(wildcard include/config/64BIT) \
    $(wildcard include/config/ARCH_32BIT_USTAT_F_TINODE) \
  /src/include/uapi/linux/types.h \
  arch/x86/include/generated/uapi/asm/types.h \
  /src/include/uapi/asm-generic/types.h \
  /src/include/asm-generic/int-ll64.h \
  /src/include/uapi/asm-generic/int-ll64.h \
  /src/arch/x86/include/uapi/asm/bitsperlong.h \
  /src/include/asm-generic/bitsperlong.h \
  /src/include/uapi/asm-generic/bitsperlong.h \
  /src/include/uapi/linux/posix_types.h \
  /src/include/linux/stddef.h \
  /src/include/uapi/linux/stddef.h \
  /src/arch/x86/include/asm/posix_types.h \
    $(wildcard include/config/X86_32) \
  /src/arch/x86/include/uapi/asm/posix_types_64.h \
  /src/include/uapi/asm-generic/posix_types.h \
  /src/include/linux/slab.h \
    $(wildcard include/config/DEBUG_OBJECTS) \
    $(wildcard include/config/FAILSLAB) \
    $(wildcard include/config/KASAN_GENERIC) \
    $(wildcard include/config/KFENCE) \
    $(wildcard include/config/SLUB_TINY) \
    $(wildcard include/config/SLAB_OBJ_EXT) \
    $(wildcard include/config/SLUB_DEBUG) \
    $(wildcard include/config/PRINTK) \
    $(wildcard include/config/RANDOM_KMALLOC_CACHES) \
    $(wildcard include/config/ZONE_DMA) \
    $(wildcard include/config/PROFILE_ALL_BRANCHES) \
    $(wildcard include/config/SLAB_BUCKETS) \
    $(wildcard include/config/KVFREE_RCU_BATCHED) \
  /src/include/linux/bug.h \
    $(wildcard include/config/GENERIC_BUG) \
    $(wildcard include/config/BUG_ON_DATA_CORRUPTION) \
  /src/arch/x86/include/asm/bug.h \
    $(wildcard include/config/DEBUG_BUGVERBOSE) \
  /src/include/linux/stringify.h \
  /src/include/linux/instrumentation.h \
    $(wildcard include/config/NOINSTR_VALIDATION) \
  /src/include/linux/objtool.h \
    $(wildcard include/config/OBJTOOL) \
    $(wildcard include/config/FRAME_POINTER) \
    $(wildcard include/config/MITIGATION_UNRET_ENTRY) \
    $(wildcard include/config/MITIGATION_SRSO) \
  /src/include/linux/objtool_types.h \
  /src/arch/x86/include/asm/asm.h \
    $(wildcard include/config/KPROBES) \
  /src/arch/x86/include/asm/extable_fixup_types.h \
  /src/include/asm-generic/bug.h \
    $(wildcard include/config/BUG) \
    $(wildcard include/config/GENERIC_BUG_RELATIVE_POINTERS) \
    $(wildcard include/config/SMP) \
  /src/include/linux/compiler.h \
    $(wildcard include/config/TRACE_BRANCH_PROFILING) \
  arch/x86/include/generated/asm/rwonce.h \
  /src/include/asm-generic/rwonce.h \
  /src/include/linux/kasan-checks.h \
    $(wildcard include/config/KASAN_SW_TAGS) \
  /src/include/linux/kcsan-checks.h \
    $(wildcard include/config/KCSAN_WEAK_MEMORY) \
    $(wildcard include/config/KCSAN_IGNORE_ATOMICS) \
  /src/include/linux/once_lite.h \
  /src/include/linux/panic.h \
    $(wildcard include/config/PANIC_TIMEOUT) \
  /src/include/linux/stdarg.h \
  /src/include/linux/printk.h \
    $(wildcard include/config/MESSAGE_LOGLEVEL_DEFAULT) \
    $(wildcard include/config/CONSOLE_LOGLEVEL_DEFAULT) \
    $(wildcard include/config/CONSOLE_LOGLEVEL_QUIET) \
    $(wildcard include/config/EARLY_PRINTK) \
    $(wildcard include/config/PRINTK_INDEX) \
    $(wildcard include/config/DYNAMIC_DEBUG) \
    $(wildcard include/config/DYNAMIC_DEBUG_CORE) \
  /src/include/linux/init.h \
    $(wildcard include/config/MEMORY_HOTPLUG) \
    $(wildcard include/config/HAVE_ARCH_PREL32_RELOCATIONS) \
  /src/include/linux/build_bug.h \
  /src/include/linux/kern_levels.h \
  /src/include/linux/linkage.h \
    $(wildcard include/config/ARCH_USE_SYM_ANNOTATIONS) \
  /src/include/linux/export.h \
    $(wildcard include/config/MODVERSIONS) \
    $(wildcard include/config/GENDWARFKSYMS) \
  /src/arch/x86/include/asm/linkage.h \
    $(wildcard include/config/CALL_PADDING) \
    $(wildcard include/config/MITIGATION_RETHUNK) \
    $(wildcard include/config/MITIGATION_RETPOLINE) \
    $(wildcard include/config/MITIGATION_SLS) \
    $(wildcard include/config/FUNCTION_PADDING_BYTES) \
    $(wildcard include/config/UML) \
  /src/arch/x86/include/asm/ibt.h \
    $(wildcard include/config/X86_KERNEL_IBT) \
  /src/include/linux/ratelimit_types.h \
  /src/include/linux/bits.h \
  /src/include/vdso/bits.h \
  /src/include/vdso/const.h \
  /src/include/uapi/linux/const.h \
  /src/include/uapi/linux/bits.h \
  /src/include/linux/overflow.h \
  /src/include/linux/limits.h \
  /src/include/uapi/linux/limits.h \
  /src/include/vdso/limits.h \
  /src/include/linux/const.h \
  /src/include/uapi/linux/param.h \
  arch/x86/include/generated/uapi/asm/param.h \
  /src/include/asm-generic/param.h \
    $(wildcard include/config/HZ) \
  /src/include/uapi/asm-generic/param.h \
  /src/include/linux/spinlock_types_raw.h \
    $(wildcard include/config/DEBUG_SPINLOCK) \
    $(wildcard include/config/DEBUG_LOCK_ALLOC) \
  /src/arch/x86/include/asm/spinlock_types.h \
  /src/include/asm-generic/qspinlock_types.h \
    $(wildcard include/config/NR_CPUS) \
  /src/include/asm-generic/qrwlock_types.h \
  /src/arch/x86/include/uapi/asm/byteorder.h \
  /src/include/linux/byteorder/little_endian.h \
  /src/include/uapi/linux/byteorder/little_endian.h \
  /src/include/linux/swab.h \
  /src/include/uapi/linux/swab.h \
  /src/arch/x86/include/uapi/asm/swab.h \
  /src/include/linux/byteorder/generic.h \
  /src/include/linux/lockdep_types.h \
    $(wildcard include/config/PROVE_RAW_LOCK_NESTING) \
    $(wildcard include/config/LOCKDEP) \
    $(wildcard include/config/LOCK_STAT) \
  /src/include/linux/cache.h \
    $(wildcard include/config/ARCH_HAS_CACHE_LINE_SIZE) \
  /src/include/uapi/linux/kernel.h \
  /src/include/uapi/linux/sysinfo.h \
  /src/include/vdso/cache.h \
  /src/arch/x86/include/asm/cache.h \
    $(wildcard include/config/X86_L1_CACHE_SHIFT) \
    $(wildcard include/config/X86_INTERNODE_CACHE_SHIFT) \
    $(wildcard include/config/X86_VSMP) \
  /src/include/linux/gfp.h \
    $(wildcard include/config/HIGHMEM) \
    $(wildcard include/config/ZONE_DMA32) \
    $(wildcard include/config/ZONE_DEVICE) \
    $(wildcard include/config/COMPACTION) \
    $(wildcard include/config/CONTIG_ALLOC) \
  /src/include/linux/gfp_types.h \
    $(wildcard include/config/KASAN_HW_TAGS) \
  /src/include/linux/mmzone.h \
    $(wildcard include/config/ARCH_FORCE_MAX_ORDER) \
    $(wildcard include/config/PAGE_BLOCK_MAX_ORDER) \
    $(wildcard include/config/CMA) \
    $(wildcard include/config/MEMORY_ISOLATION) \
    $(wildcard include/config/ZSMALLOC) \
    $(wildcard include/config/UNACCEPTED_MEMORY) \
    $(wildcard include/config/SHADOW_CALL_STACK) \
    $(wildcard include/config/IOMMU_SUPPORT) \
    $(wildcard include/config/SWAP) \
    $(wildcard include/config/NUMA_BALANCING) \
    $(wildcard include/config/HUGETLB_PAGE) \
    $(wildcard include/config/LRU_GEN) \
    $(wildcard include/config/LRU_GEN_STATS) \
    $(wildcard include/config/SPARSEMEM) \
    $(wildcard include/config/MEMORY_FAILURE) \
    $(wildcard include/config/FLATMEM) \
    $(wildcard include/config/PAGE_EXTENSION) \
    $(wildcard include/config/DEFERRED_STRUCT_PAGE_INIT) \
    $(wildcard include/config/HAVE_MEMORYLESS_NODES) \
    $(wildcard include/config/SPARSEMEM_VMEMMAP) \
    $(wildcard include/config/SPARSEMEM_EXTREME) \
    $(wildcard include/config/SPARSEMEM_VMEMMAP_PREINIT) \
    $(wildcard include/config/HAVE_ARCH_PFN_VALID) \
  /src/include/linux/spinlock.h \
    $(wildcard include/config/PREEMPTION) \
    $(wildcard include/config/PREEMPT_RT) \
  /src/include/linux/typecheck.h \
  /src/include/linux/preempt.h \
    $(wildcard include/config/PREEMPT_COUNT) \
    $(wildcard include/config/DEBUG_PREEMPT) \
    $(wildcard include/config/TRACE_PREEMPT_TOGGLE) \
    $(wildcard include/config/PREEMPT_NOTIFIERS) \
    $(wildcard include/config/PREEMPT_DYNAMIC) \
    $(wildcard include/config/PREEMPT_NONE) \
    $(wildcard include/config/PREEMPT_VOLUNTARY) \
    $(wildcard include/config/PREEMPT) \
    $(wildcard include/config/PREEMPT_LAZY) \
  /src/include/linux/cleanup.h \
  /src/include/linux/err.h \
  arch/x86/include/generated/uapi/asm/errno.h \
  /src/include/uapi/asm-generic/errno.h \
  /src/include/uapi/asm-generic/errno-base.h \
  /src/include/linux/args.h \
  /src/arch/x86/include/asm/preempt.h \
  /src/arch/x86/include/asm/rmwcc.h \
  /src/arch/x86/include/asm/percpu.h \
    $(wildcard include/config/CC_HAS_NAMED_AS) \
    $(wildcard include/config/USE_X86_SEG_SUPPORT) \
  /src/include/asm-generic/percpu.h \
    $(wildcard include/config/HAVE_SETUP_PER_CPU_AREA) \
  /src/include/linux/threads.h \
    $(wildcard include/config/BASE_SMALL) \
  /src/include/linux/percpu-defs.h \
    $(wildcard include/config/ARCH_MODULE_NEEDS_WEAK_PER_CPU) \
    $(wildcard include/config/DEBUG_FORCE_WEAK_PER_CPU) \
    $(wildcard include/config/AMD_MEM_ENCRYPT) \
  /src/include/linux/static_call_types.h \
    $(wildcard include/config/HAVE_STATIC_CALL) \
    $(wildcard include/config/HAVE_STATIC_CALL_INLINE) \
  /src/include/linux/irqflags.h \
    $(wildcard include/config/IRQSOFF_TRACER) \
    $(wildcard include/config/PREEMPT_TRACER) \
    $(wildcard include/config/DEBUG_IRQFLAGS) \
    $(wildcard include/config/TRACE_IRQFLAGS_SUPPORT) \
  /src/include/linux/irqflags_types.h \
  /src/arch/x86/include/asm/irqflags.h \
    $(wildcard include/config/PARAVIRT) \
    $(wildcard include/config/PARAVIRT_XXL) \
    $(wildcard include/config/DEBUG_ENTRY) \
  /src/arch/x86/include/asm/processor-flags.h \
    $(wildcard include/config/VM86) \
    $(wildcard include/config/MITIGATION_PAGE_TABLE_ISOLATION) \
  /src/arch/x86/include/uapi/asm/processor-flags.h \
  /src/include/linux/mem_encrypt.h \
    $(wildcard include/config/ARCH_HAS_MEM_ENCRYPT) \
  /src/arch/x86/include/asm/mem_encrypt.h \
    $(wildcard include/config/X86_MEM_ENCRYPT) \
  /src/include/linux/cc_platform.h \
    $(wildcard include/config/ARCH_HAS_CC_PLATFORM) \
  /src/arch/x86/include/asm/nospec-branch.h \
    $(wildcard include/config/CALL_THUNKS_DEBUG) \
    $(wildcard include/config/MITIGATION_CALL_DEPTH_TRACKING) \
    $(wildcard include/config/MITIGATION_IBPB_ENTRY) \
    $(wildcard include/config/MITIGATION_ITS) \
    $(wildcard include/config/BPF_JIT) \
  /src/include/linux/static_key.h \
  /src/include/linux/jump_label.h \
    $(wildcard include/config/JUMP_LABEL) \
    $(wildcard include/config/HAVE_ARCH_JUMP_LABEL_RELATIVE) \
  /src/include/linux/atomic.h \
  /src/arch/x86/include/asm/atomic.h \
  /src/arch/x86/include/asm/alternative.h \
    $(wildcard include/config/CALL_THUNKS) \
  /src/arch/x86/include/asm/cmpxchg.h \
  /src/arch/x86/include/asm/cpufeatures.h \
  /src/arch/x86/include/asm/cmpxchg_64.h \
  /src/arch/x86/include/asm/barrier.h \
  /src/arch/x86/include/asm/nops.h \
  /src/include/asm-generic/barrier.h \
  /src/arch/x86/include/asm/atomic64_64.h \
  /src/include/linux/atomic/atomic-arch-fallback.h \
    $(wildcard include/config/GENERIC_ATOMIC64) \
  /src/include/linux/atomic/atomic-long.h \
  /src/include/linux/atomic/atomic-instrumented.h \
  /src/include/linux/instrumented.h \
  /src/include/linux/kmsan-checks.h \
    $(wildcard include/config/KMSAN) \
  /src/arch/x86/include/asm/msr-index.h \
  /src/arch/x86/include/asm/unwind_hints.h \
  /src/arch/x86/include/asm/orc_types.h \
  /src/arch/x86/include/uapi/asm/ptrace-abi.h \
  /src/arch/x86/include/asm/asm-offsets.h \
  include/generated/asm-offsets.h \
  /src/arch/x86/include/asm/GEN-for-each-reg.h \
  /src/arch/x86/include/asm/segment.h \
    $(wildcard include/config/XEN_PV) \
  /src/include/linux/thread_info.h \
    $(wildcard include/config/ARCH_HAS_PREEMPT_LAZY) \
    $(wildcard include/config/HAVE_ARCH_WITHIN_STACK_FRAMES) \
    $(wildcard include/config/SH) \
  /src/include/linux/restart_block.h \
  /src/include/linux/errno.h \
  /src/include/uapi/linux/errno.h \
  /src/arch/x86/include/asm/current.h \
  /src/include/linux/bitops.h \
  /src/include/asm-generic/bitops/generic-non-atomic.h \
  /src/arch/x86/include/asm/bitops.h \
    $(wildcard include/config/X86_CMOV) \
  /src/include/asm-generic/bitops/sched.h \
  /src/arch/x86/include/asm/arch_hweight.h \
  /src/include/asm-generic/bitops/const_hweight.h \
  /src/include/asm-generic/bitops/instrumented-atomic.h \
  /src/include/asm-generic/bitops/instrumented-non-atomic.h \
    $(wildcard include/config/KCSAN_ASSUME_PLAIN_WRITES_ATOMIC) \
  /src/include/asm-generic/bitops/instrumented-lock.h \
  /src/include/asm-generic/bitops/le.h \
  /src/include/asm-generic/bitops/ext2-atomic-setbit.h \
  /src/arch/x86/include/asm/thread_info.h \
    $(wildcard include/config/X86_FRED) \
    $(wildcard include/config/X86_IOPL_IOPERM) \
    $(wildcard include/config/COMPAT) \
    $(wildcard include/config/IA32_EMULATION) \
  /src/arch/x86/include/asm/page.h \
  /src/arch/x86/include/asm/page_types.h \
    $(wildcard include/config/PHYSICAL_START) \
    $(wildcard include/config/PHYSICAL_ALIGN) \
    $(wildcard include/config/DYNAMIC_PHYSICAL_MASK) \
  /src/include/vdso/page.h \
    $(wildcard include/config/PAGE_SHIFT) \
  /src/arch/x86/include/asm/page_64_types.h \
    $(wildcard include/config/KASAN) \
    $(wildcard include/config/RANDOMIZE_BASE) \
  /src/arch/x86/include/asm/kaslr.h \
    $(wildcard include/config/RANDOMIZE_MEMORY) \
  /src/arch/x86/include/asm/page_64.h \
    $(wildcard include/config/DEBUG_VIRTUAL) \
    $(wildcard include/config/X86_VSYSCALL_EMULATION) \
  /src/include/linux/range.h \
  /src/include/asm-generic/memory_model.h \
  /src/include/linux/pfn.h \
  /src/include/asm-generic/getorder.h \
  /src/include/linux/log2.h \
    $(wildcard include/config/ARCH_HAS_ILOG2_U32) \
    $(wildcard include/config/ARCH_HAS_ILOG2_U64) \
  /src/arch/x86/include/asm/cpufeature.h \
  /src/arch/x86/include/asm/processor.h \
    $(wildcard include/config/X86_VMX_FEATURE_NAMES) \
    $(wildcard include/config/X86_USER_SHADOW_STACK) \
    $(wildcard include/config/X86_DEBUG_FPU) \
    $(wildcard include/config/CPU_SUP_AMD) \
    $(wildcard include/config/XEN) \
  /src/arch/x86/include/asm/math_emu.h \
  /src/arch/x86/include/asm/ptrace.h \
    $(wildcard include/config/X86_DEBUGCTLMSR) \
  /src/arch/x86/include/uapi/asm/ptrace.h \
  /src/arch/x86/include/asm/proto.h \
  /src/arch/x86/include/uapi/asm/ldt.h \
  /src/arch/x86/include/uapi/asm/sigcontext.h \
  /src/arch/x86/include/asm/cpuid/api.h \
  /src/arch/x86/include/asm/cpuid/types.h \
  /src/arch/x86/include/asm/string.h \
  /src/arch/x86/include/asm/string_64.h \
    $(wildcard include/config/ARCH_HAS_UACCESS_FLUSHCACHE) \
  /src/arch/x86/include/asm/pgtable_types.h \
    $(wildcard include/config/X86_INTEL_MEMORY_PROTECTION_KEYS) \
    $(wildcard include/config/X86_PAE) \
    $(wildcard include/config/MEM_SOFT_DIRTY) \
    $(wildcard include/config/HAVE_ARCH_USERFAULTFD_WP) \
    $(wildcard include/config/PGTABLE_LEVELS) \
    $(wildcard include/config/PROC_FS) \
  /src/arch/x86/include/asm/pgtable_64_types.h \
    $(wildcard include/config/DEBUG_KMAP_LOCAL_FORCE_MAP) \
  /src/arch/x86/include/asm/sparsemem.h \
  /src/arch/x86/include/asm/desc_defs.h \
  /src/arch/x86/include/asm/special_insns.h \
  /src/arch/x86/include/asm/fpu/types.h \
  /src/arch/x86/include/asm/vmxfeatures.h \
  /src/arch/x86/include/asm/vdso/processor.h \
  /src/arch/x86/include/asm/shstk.h \
  /src/include/linux/personality.h \
  /src/include/uapi/linux/personality.h \
  /src/include/linux/math64.h \
    $(wildcard include/config/ARCH_SUPPORTS_INT128) \
  /src/include/linux/math.h \
  /src/arch/x86/include/asm/div64.h \
  /src/include/asm-generic/div64.h \
    $(wildcard include/config/CC_OPTIMIZE_FOR_PERFORMANCE) \
  /src/include/vdso/math64.h \
  arch/x86/include/generated/asm/cpufeaturemasks.h \
  /src/include/asm-generic/thread_info_tif.h \
  /src/include/linux/bottom_half.h \
  /src/include/linux/instruction_pointer.h \
  /src/include/linux/lockdep.h \
    $(wildcard include/config/DEBUG_LOCKING_API_SELFTESTS) \
  /src/include/linux/smp.h \
    $(wildcard include/config/UP_LATE_INIT) \
    $(wildcard include/config/CSD_LOCK_WAIT_DEBUG) \
  /src/include/linux/list.h \
    $(wildcard include/config/LIST_HARDENED) \
    $(wildcard include/config/DEBUG_LIST) \
  /src/include/linux/container_of.h \
  /src/include/linux/poison.h \
    $(wildcard include/config/ILLEGAL_POINTER_VALUE) \
  /src/include/linux/cpumask.h \
    $(wildcard include/config/FORCE_NR_CPUS) \
    $(wildcard include/config/HOTPLUG_CPU) \
    $(wildcard include/config/DEBUG_PER_CPU_MAPS) \
    $(wildcard include/config/CPUMASK_OFFSTACK) \
  /src/include/linux/kernel.h \
    $(wildcard include/config/PREEMPT_VOLUNTARY_BUILD) \
    $(wildcard include/config/HAVE_PREEMPT_DYNAMIC_CALL) \
    $(wildcard include/config/HAVE_PREEMPT_DYNAMIC_KEY) \
    $(wildcard include/config/PREEMPT_) \
    $(wildcard include/config/DEBUG_ATOMIC_SLEEP) \
    $(wildcard include/config/DYNAMIC_FTRACE) \
  /src/include/linux/align.h \
  /src/include/vdso/align.h \
  /src/include/linux/array_size.h \
  /src/include/linux/hex.h \
  /src/include/linux/kstrtox.h \
  /src/include/linux/minmax.h \
  /src/include/linux/sprintf.h \
  /src/include/linux/trace_printk.h \
    $(wildcard include/config/TRACING) \
  /src/include/linux/util_macros.h \
    $(wildcard include/config/FOO_SUSPEND) \
  /src/include/linux/wordpart.h \
  /src/include/linux/bitmap.h \
  /src/include/linux/find.h \
  /src/include/linux/string.h \
    $(wildcard include/config/BINARY_PRINTF) \
    $(wildcard include/config/FORTIFY_SOURCE) \
  /src/include/uapi/linux/string.h \
  /src/include/linux/fortify-string.h \
    $(wildcard include/config/CC_HAS_KASAN_MEMINTRINSIC_PREFIX) \
  /src/include/linux/bitfield.h \
  /src/include/linux/bitmap-str.h \
  /src/include/linux/cpumask_types.h \
  /src/include/linux/numa.h \
    $(wildcard include/config/NUMA_KEEP_MEMINFO) \
    $(wildcard include/config/HAVE_ARCH_NODE_DEV_GROUP) \
  /src/include/linux/nodemask.h \
  /src/include/linux/nodemask_types.h \
    $(wildcard include/config/NODES_SHIFT) \
  /src/include/linux/random.h \
    $(wildcard include/config/VMGENID) \
  /src/include/uapi/linux/random.h \
  /src/include/uapi/linux/ioctl.h \
  arch/x86/include/generated/uapi/asm/ioctl.h \
  /src/include/asm-generic/ioctl.h \
  /src/include/uapi/asm-generic/ioctl.h \
  /src/include/linux/irqnr.h \
  /src/include/uapi/linux/irqnr.h \
  /src/include/linux/smp_types.h \
  /src/include/linux/llist.h \
    $(wildcard include/config/ARCH_HAVE_NMI_SAFE_CMPXCHG) \
  /src/arch/x86/include/asm/smp.h \
    $(wildcard include/config/DEBUG_NMI_SELFTEST) \
  /src/arch/x86/include/asm/cpumask.h \
  /src/include/linux/debug_locks.h \
  /src/include/linux/stacktrace.h \
    $(wildcard include/config/ARCH_STACKWALK) \
    $(wildcard include/config/STACKTRACE) \
    $(wildcard include/config/HAVE_RELIABLE_STACKTRACE) \
  arch/x86/include/generated/asm/mmiowb.h \
  /src/include/asm-generic/mmiowb.h \
    $(wildcard include/config/MMIOWB) \
  /src/include/linux/spinlock_types.h \
  /src/include/linux/rwlock_types.h \
  /src/arch/x86/include/asm/spinlock.h \
  /src/arch/x86/include/asm/paravirt.h \
    $(wildcard include/config/PARAVIRT_SPINLOCKS) \
  /src/arch/x86/include/asm/paravirt_types.h \
    $(wildcard include/config/ZERO_CALL_USED_REGS) \
    $(wildcard include/config/PARAVIRT_DEBUG) \
  /src/arch/x86/include/asm/qspinlock.h \
  /src/include/asm-generic/qspinlock.h \
  /src/arch/x86/include/asm/qrwlock.h \
  /src/include/asm-generic/qrwlock.h \
  /src/include/linux/rwlock.h \
  /src/include/linux/spinlock_api_smp.h \
    $(wildcard include/config/INLINE_SPIN_LOCK) \
    $(wildcard include/config/INLINE_SPIN_LOCK_BH) \
    $(wildcard include/config/INLINE_SPIN_LOCK_IRQ) \
    $(wildcard include/config/INLINE_SPIN_LOCK_IRQSAVE) \
    $(wildcard include/config/INLINE_SPIN_TRYLOCK) \
    $(wildcard include/config/INLINE_SPIN_TRYLOCK_BH) \
    $(wildcard include/config/UNINLINE_SPIN_UNLOCK) \
    $(wildcard include/config/INLINE_SPIN_UNLOCK_BH) \
    $(wildcard include/config/INLINE_SPIN_UNLOCK_IRQ) \
    $(wildcard include/config/INLINE_SPIN_UNLOCK_IRQRESTORE) \
    $(wildcard include/config/GENERIC_LOCKBREAK) \
  /src/include/linux/rwlock_api_smp.h \
    $(wildcard include/config/INLINE_READ_LOCK) \
    $(wildcard include/config/INLINE_WRITE_LOCK) \
    $(wildcard include/config/INLINE_READ_LOCK_BH) \
    $(wildcard include/config/INLINE_WRITE_LOCK_BH) \
    $(wildcard include/config/INLINE_READ_LOCK_IRQ) \
    $(wildcard include/config/INLINE_WRITE_LOCK_IRQ) \
    $(wildcard include/config/INLINE_READ_LOCK_IRQSAVE) \
    $(wildcard include/config/INLINE_WRITE_LOCK_IRQSAVE) \
    $(wildcard include/config/INLINE_READ_TRYLOCK) \
    $(wildcard include/config/INLINE_WRITE_TRYLOCK) \
    $(wildcard include/config/INLINE_READ_UNLOCK) \
    $(wildcard include/config/INLINE_WRITE_UNLOCK) \
    $(wildcard include/config/INLINE_READ_UNLOCK_BH) \
    $(wildcard include/config/INLINE_WRITE_UNLOCK_BH) \
    $(wildcard include/config/INLINE_READ_UNLOCK_IRQ) \
    $(wildcard include/config/INLINE_WRITE_UNLOCK_IRQ) \
    $(wildcard include/config/INLINE_READ_UNLOCK_IRQRESTORE) \
    $(wildcard include/config/INLINE_WRITE_UNLOCK_IRQRESTORE) \
  /src/include/linux/list_nulls.h \
  /src/include/linux/wait.h \
  /src/include/linux/seqlock.h \
    $(wildcard include/config/CC_IS_GCC) \
    $(wildcard include/config/GCC_VERSION) \
    $(wildcard include/config/UBSAN_ALIGNMENT) \
  /src/include/linux/mutex.h \
    $(wildcard include/config/DEBUG_MUTEXES) \
  /src/include/linux/osq_lock.h \
  /src/include/linux/mutex_types.h \
    $(wildcard include/config/MUTEX_SPIN_ON_OWNER) \
  /src/include/linux/seqlock_types.h \
  /src/include/linux/pageblock-flags.h \
    $(wildcard include/config/HUGETLB_PAGE_SIZE_VARIABLE) \
  /src/include/linux/page-flags-layout.h \
  include/generated/bounds.h \
  /src/include/linux/mm_types.h \
    $(wildcard include/config/HAVE_ALIGNED_STRUCT_PAGE) \
    $(wildcard include/config/HUGETLB_PMD_PAGE_TABLE_SHARING) \
    $(wildcard include/config/SLAB_FREELIST_HARDENED) \
    $(wildcard include/config/USERFAULTFD) \
    $(wildcard include/config/ANON_VMA_NAME) \
    $(wildcard include/config/HAVE_ARCH_COMPAT_MMAP_BASES) \
    $(wildcard include/config/MEMBARRIER) \
    $(wildcard include/config/ARCH_HAS_ELF_CORE_EFLAGS) \
    $(wildcard include/config/MMU_NOTIFIER) \
    $(wildcard include/config/ARCH_WANT_BATCHED_UNMAP_TLB_FLUSH) \
    $(wildcard include/config/IOMMU_MM_DATA) \
    $(wildcard include/config/KSM) \
    $(wildcard include/config/CORE_DUMP_DEFAULT_ELF_HEADERS) \
  /src/include/linux/mm_types_task.h \
  /src/arch/x86/include/asm/tlbbatch.h \
  /src/include/linux/auxvec.h \
  /src/include/uapi/linux/auxvec.h \
  /src/arch/x86/include/uapi/asm/auxvec.h \
  /src/include/linux/kref.h \
  /src/include/linux/refcount.h \
  /src/include/linux/refcount_types.h \
  /src/include/linux/rbtree.h \
  /src/include/linux/rbtree_types.h \
  /src/include/linux/rcupdate.h \
    $(wildcard include/config/TINY_RCU) \
    $(wildcard include/config/RCU_STRICT_GRACE_PERIOD) \
    $(wildcard include/config/RCU_LAZY) \
    $(wildcard include/config/RCU_STALL_COMMON) \
    $(wildcard include/config/NO_HZ_FULL) \
    $(wildcard include/config/VIRT_XFER_TO_GUEST_WORK) \
    $(wildcard include/config/RCU_NOCB_CPU) \
    $(wildcard include/config/TASKS_RCU_GENERIC) \
    $(wildcard include/config/TASKS_RUDE_RCU) \
    $(wildcard include/config/TREE_RCU) \
    $(wildcard include/config/DEBUG_OBJECTS_RCU_HEAD) \
    $(wildcard include/config/ARCH_WEAK_RELEASE_ACQUIRE) \
  /src/include/linux/sched.h \
    $(wildcard include/config/VIRT_CPU_ACCOUNTING_NATIVE) \
    $(wildcard include/config/SCHED_INFO) \
    $(wildcard include/config/SCHEDSTATS) \
    $(wildcard include/config/SCHED_CORE) \
    $(wildcard include/config/FAIR_GROUP_SCHED) \
    $(wildcard include/config/RT_GROUP_SCHED) \
    $(wildcard include/config/UCLAMP_TASK) \
    $(wildcard include/config/UCLAMP_BUCKETS_COUNT) \
    $(wildcard include/config/KMAP_LOCAL) \
    $(wildcard include/config/MEM_ALLOC_PROFILING) \
    $(wildcard include/config/SCHED_CLASS_EXT) \
    $(wildcard include/config/CGROUP_SCHED) \
    $(wildcard include/config/CFS_BANDWIDTH) \
    $(wildcard include/config/MEMCG_V1) \
    $(wildcard include/config/COMPAT_BRK) \
    $(wildcard include/config/PAGE_OWNER) \
    $(wildcard include/config/EVENTFD) \
    $(wildcard include/config/TASK_DELAY_ACCT) \
    $(wildcard include/config/POSIX_CPUTIMERS) \
    $(wildcard include/config/POSIX_CPU_TIMERS_TASK_WORK) \
    $(wildcard include/config/KEYS) \
    $(wildcard include/config/SYSVIPC) \
    $(wildcard include/config/AUDIT) \
    $(wildcard include/config/AUDITSYSCALL) \
    $(wildcard include/config/DETECT_HUNG_TASK_BLOCKER) \
    $(wildcard include/config/UBSAN) \
    $(wildcard include/config/UBSAN_TRAP) \
    $(wildcard include/config/TASK_XACCT) \
    $(wildcard include/config/X86_CPU_RESCTRL) \
    $(wildcard include/config/FUTEX) \
    $(wildcard include/config/PERF_EVENTS) \
    $(wildcard include/config/RSEQ) \
    $(wildcard include/config/DEBUG_RSEQ) \
    $(wildcard include/config/LATENCYTOP) \
    $(wildcard include/config/KUNIT) \
    $(wildcard include/config/FUNCTION_GRAPH_TRACER) \
    $(wildcard include/config/KCOV) \
    $(wildcard include/config/LIVEPATCH) \
    $(wildcard include/config/SECURITY) \
    $(wildcard include/config/KSTACK_ERASE) \
    $(wildcard include/config/KSTACK_ERASE_METRICS) \
    $(wildcard include/config/RANDOMIZE_KSTACK_OFFSET) \
    $(wildcard include/config/X86_MCE) \
    $(wildcard include/config/ARCH_HAS_PARANOID_L1D_FLUSH) \
    $(wildcard include/config/RV_PER_TASK_MONITORS) \
    $(wildcard include/config/USER_EVENTS) \
    $(wildcard include/config/UNWIND_USER) \
    $(wildcard include/config/SCHED_PROXY_EXEC) \
    $(wildcard include/config/MEM_ALLOC_PROFILING_DEBUG) \
  /src/include/uapi/linux/sched.h \
  /src/include/linux/pid_types.h \
  /src/include/linux/sem_types.h \
  /src/include/linux/shm.h \
  /src/arch/x86/include/asm/shmparam.h \
  /src/include/linux/kmsan_types.h \
  /src/include/linux/plist_types.h \
  /src/include/linux/hrtimer_types.h \
  /src/include/linux/timerqueue_types.h \
  /src/include/linux/timer_types.h \
  /src/include/linux/seccomp_types.h \
  /src/include/linux/resource.h \
  /src/include/uapi/linux/resource.h \
  /src/include/uapi/linux/time_types.h \
  arch/x86/include/generated/uapi/asm/resource.h \
  /src/include/asm-generic/resource.h \
  /src/include/uapi/asm-generic/resource.h \
  /src/include/linux/latencytop.h \
  /src/include/linux/sched/prio.h \
  /src/include/linux/sched/types.h \
  /src/include/linux/signal_types.h \
    $(wildcard include/config/OLD_SIGACTION) \
  /src/include/uapi/linux/signal.h \
  /src/arch/x86/include/asm/signal.h \
  /src/arch/x86/include/uapi/asm/signal.h \
  /src/include/uapi/asm-generic/signal-defs.h \
  /src/arch/x86/include/uapi/asm/siginfo.h \
  /src/include/uapi/asm-generic/siginfo.h \
  /src/include/linux/syscall_user_dispatch_types.h \
  /src/include/linux/netdevice_xmit.h \
    $(wildcard include/config/NET_EGRESS) \
    $(wildcard include/config/NET_ACT_MIRRED) \
    $(wildcard include/config/NF_DUP_NETDEV) \
  /src/include/linux/task_io_accounting.h \
    $(wildcard include/config/TASK_IO_ACCOUNTING) \
  /src/include/linux/posix-timers_types.h \
  /src/include/uapi/linux/rseq.h \
  /src/include/linux/kcsan.h \
  /src/include/linux/rv.h \
    $(wildcard include/config/RV_LTL_MONITOR) \
    $(wildcard include/config/RV_REACTORS) \
  /src/include/linux/uidgid_types.h \
  /src/include/linux/tracepoint-defs.h \
    $(wildcard include/config/TRACEPOINTS) \
  /src/include/linux/unwind_deferred_types.h \
  arch/x86/include/generated/asm/kmap_size.h \
  /src/include/asm-generic/kmap_size.h \
    $(wildcard include/config/DEBUG_KMAP_LOCAL) \
  include/generated/rq-offsets.h \
  /src/include/linux/sched/ext.h \
    $(wildcard include/config/EXT_GROUP_SCHED) \
  /src/include/linux/context_tracking_irq.h \
    $(wildcard include/config/CONTEXT_TRACKING_IDLE) \
  /src/include/linux/rcutree.h \
  /src/include/linux/maple_tree.h \
    $(wildcard include/config/MAPLE_RCU_DISABLED) \
    $(wildcard include/config/DEBUG_MAPLE_TREE) \
  /src/include/linux/rwsem.h \
    $(wildcard include/config/RWSEM_SPIN_ON_OWNER) \
    $(wildcard include/config/DEBUG_RWSEMS) \
  /src/include/linux/completion.h \
  /src/include/linux/swait.h \
  /src/include/linux/uprobes.h \
  /src/include/linux/timer.h \
    $(wildcard include/config/DEBUG_OBJECTS_TIMERS) \
  /src/include/linux/ktime.h \
  /src/include/linux/jiffies.h \
  /src/include/linux/time.h \
  /src/include/linux/time64.h \
  /src/include/vdso/time64.h \
  /src/include/uapi/linux/time.h \
  /src/include/linux/time32.h \
  /src/include/linux/timex.h \
  /src/include/uapi/linux/timex.h \
  /src/arch/x86/include/asm/timex.h \
    $(wildcard include/config/X86_TSC) \
  /src/arch/x86/include/asm/tsc.h \
  /src/arch/x86/include/asm/msr.h \
  /src/arch/x86/include/uapi/asm/msr.h \
  /src/arch/x86/include/asm/shared/msr.h \
  /src/include/linux/percpu.h \
    $(wildcard include/config/MODULES) \
    $(wildcard include/config/PAGE_SIZE_4KB) \
    $(wildcard include/config/NEED_PER_CPU_PAGE_FIRST_CHUNK) \
  /src/include/linux/alloc_tag.h \
    $(wildcard include/config/MEM_ALLOC_PROFILING_ENABLED_BY_DEFAULT) \
  /src/include/linux/codetag.h \
    $(wildcard include/config/CODE_TAGGING) \
  /src/include/linux/mmdebug.h \
    $(wildcard include/config/DEBUG_VM) \
    $(wildcard include/config/DEBUG_VM_IRQSOFF) \
    $(wildcard include/config/DEBUG_VM_PGFLAGS) \
  /src/include/vdso/time32.h \
  /src/include/vdso/time.h \
  /src/include/vdso/jiffies.h \
  include/generated/timeconst.h \
  /src/include/vdso/ktime.h \
  /src/include/linux/timekeeping.h \
    $(wildcard include/config/POSIX_AUX_CLOCKS) \
    $(wildcard include/config/GENERIC_CMOS_UPDATE) \
  /src/include/linux/clocksource_ids.h \
  /src/include/linux/debugobjects.h \
    $(wildcard include/config/DEBUG_OBJECTS_FREE) \
  /src/include/linux/workqueue.h \
    $(wildcard include/config/DEBUG_OBJECTS_WORK) \
    $(wildcard include/config/FREEZER) \
    $(wildcard include/config/SYSFS) \
    $(wildcard include/config/WQ_WATCHDOG) \
  /src/include/linux/workqueue_types.h \
  /src/include/linux/percpu_counter.h \
  /src/arch/x86/include/asm/mmu.h \
    $(wildcard include/config/MODIFY_LDT_SYSCALL) \
    $(wildcard include/config/ADDRESS_MASKING) \
    $(wildcard include/config/BROADCAST_TLB_FLUSH) \
  /src/include/linux/page-flags.h \
    $(wildcard include/config/PAGE_IDLE_FLAG) \
    $(wildcard include/config/ARCH_USES_PG_ARCH_2) \
    $(wildcard include/config/ARCH_USES_PG_ARCH_3) \
    $(wildcard include/config/MIGRATION) \
    $(wildcard include/config/HUGETLB_PAGE_OPTIMIZE_VMEMMAP) \
  /src/include/linux/local_lock.h \
  /src/include/linux/local_lock_internal.h \
  /src/include/linux/zswap.h \
    $(wildcard include/config/ZSWAP) \
  /src/include/linux/memory_hotplug.h \
    $(wildcard include/config/ARCH_HAS_ADD_PAGES) \
    $(wildcard include/config/MEMORY_HOTREMOVE) \
  /src/include/linux/notifier.h \
    $(wildcard include/config/TREE_SRCU) \
  /src/include/linux/srcu.h \
    $(wildcard include/config/TINY_SRCU) \
    $(wildcard include/config/NEED_SRCU_NMI_SAFE) \
  /src/include/linux/rcu_segcblist.h \
  /src/include/linux/srcutree.h \
  /src/include/linux/rcu_node_tree.h \
    $(wildcard include/config/RCU_FANOUT) \
    $(wildcard include/config/RCU_FANOUT_LEAF) \
  /src/include/linux/topology.h \
    $(wildcard include/config/USE_PERCPU_NUMA_NODE_ID) \
    $(wildcard include/config/SCHED_SMT) \
    $(wildcard include/config/GENERIC_ARCH_TOPOLOGY) \
  /src/include/linux/arch_topology.h \
  /src/arch/x86/include/asm/topology.h \
    $(wildcard include/config/X86_LOCAL_APIC) \
    $(wildcard include/config/SCHED_MC_PRIO) \
  /src/include/asm-generic/topology.h \
  /src/include/linux/cpu_smt.h \
    $(wildcard include/config/HOTPLUG_SMT) \
  /src/include/linux/percpu-refcount.h \
  /src/include/linux/hash.h \
    $(wildcard include/config/HAVE_ARCH_HASH) \
  /src/include/linux/kasan.h \
    $(wildcard include/config/KASAN_STACK) \
    $(wildcard include/config/KASAN_VMALLOC) \
  /src/include/linux/kasan-enabled.h \
    $(wildcard include/config/ARCH_DEFER_KASAN) \
  /src/include/linux/kasan-tags.h \
  /src/include/linux/sched/autogroup.h \
    $(wildcard include/config/SCHED_AUTOGROUP) \
  /src/include/linux/sched/mm.h \
    $(wildcard include/config/MMU_LAZY_TLB_REFCOUNT) \
    $(wildcard include/config/ARCH_HAS_MEMBARRIER_CALLBACKS) \
    $(wildcard include/config/ARCH_HAS_SYNC_CORE_BEFORE_USERMODE) \
  /src/include/linux/sync_core.h \
    $(wildcard include/config/ARCH_HAS_PREPARE_SYNC_CORE_CMD) \
  /src/arch/x86/include/asm/sync_core.h \
  /src/include/linux/sched/coredump.h \
  /src/include/linux/sched/user.h \
    $(wildcard include/config/EPOLL) \
    $(wildcard include/config/NET) \
    $(wildcard include/config/VFIO_PCI_ZDEV_KVM) \
    $(wildcard include/config/IOMMUFD) \
    $(wildcard include/config/SECRETMEM) \
    $(wildcard include/config/WATCH_QUEUE) \
  /src/include/linux/uidgid.h \
    $(wildcard include/config/MULTIUSER) \
    $(wildcard include/config/USER_NS) \
  /src/include/linux/highuid.h \
  /src/include/linux/ratelimit.h \
  /src/include/linux/sched/numa_balancing.h \
  /src/include/linux/sched/stat.h \
  /src/include/linux/sched/task.h \
    $(wildcard include/config/HAVE_EXIT_THREAD) \
    $(wildcard include/config/HAVE_ARCH_THREAD_STRUCT_WHITELIST) \
  /src/include/linux/uaccess.h \
    $(wildcard include/config/ARCH_HAS_SUBPAGE_FAULTS) \
    $(wildcard include/config/HARDENED_USERCOPY) \
  /src/include/linux/fault-inject-usercopy.h \
    $(wildcard include/config/FAULT_INJECTION_USERCOPY) \
  /src/include/linux/nospec.h \
  /src/include/linux/ucopysize.h \
    $(wildcard include/config/HARDENED_USERCOPY_DEFAULT_ON) \
  /src/arch/x86/include/asm/uaccess.h \
    $(wildcard include/config/CC_HAS_ASM_GOTO_OUTPUT) \
    $(wildcard include/config/CC_HAS_ASM_GOTO_TIED_OUTPUT) \
    $(wildcard include/config/ARCH_HAS_COPY_MC) \
    $(wildcard include/config/X86_INTEL_USERCOPY) \
  /src/include/linux/mmap_lock.h \
  /src/arch/x86/include/asm/smap.h \
  /src/arch/x86/include/asm/extable.h \
  /src/arch/x86/include/asm/tlbflush.h \
  /src/include/linux/mmu_notifier.h \
  /src/include/linux/interval_tree.h \
  /src/arch/x86/include/asm/invpcid.h \
  /src/arch/x86/include/asm/pti.h \
  /src/arch/x86/include/asm/pgtable.h \
    $(wildcard include/config/DEBUG_WX) \
    $(wildcard include/config/HAVE_ARCH_TRANSPARENT_HUGEPAGE_PUD) \
    $(wildcard include/config/ARCH_SUPPORTS_PMD_PFNMAP) \
    $(wildcard include/config/ARCH_SUPPORTS_PUD_PFNMAP) \
    $(wildcard include/config/HAVE_ARCH_SOFT_DIRTY) \
    $(wildcard include/config/ARCH_ENABLE_THP_MIGRATION) \
    $(wildcard include/config/PAGE_TABLE_CHECK) \
    $(wildcard include/config/X86_SGX) \
  /src/arch/x86/include/asm/x86_init.h \
  /src/arch/x86/include/asm/pkru.h \
  /src/arch/x86/include/asm/fpu/api.h \
    $(wildcard include/config/MATH_EMULATION) \
  /src/arch/x86/include/asm/coco.h \
  /src/include/asm-generic/pgtable_uffd.h \
  /src/include/linux/page_table_check.h \
  /src/arch/x86/include/asm/pgtable_64.h \
  /src/arch/x86/include/asm/fixmap.h \
    $(wildcard include/config/PROVIDE_OHCI1394_DMA_INIT) \
    $(wildcard include/config/X86_IO_APIC) \
    $(wildcard include/config/PCI_MMCONFIG) \
    $(wildcard include/config/ACPI_APEI_GHES) \
    $(wildcard include/config/INTEL_TXT) \
  /src/arch/x86/include/asm/apicdef.h \
  /src/arch/x86/include/uapi/asm/vsyscall.h \
  /src/include/asm-generic/fixmap.h \
  /src/arch/x86/include/asm/pgtable-invert.h \
  /src/arch/x86/include/asm/uaccess_64.h \
  /src/arch/x86/include/asm/runtime-const.h \
  /src/include/asm-generic/access_ok.h \
    $(wildcard include/config/ALTERNATE_USER_ADDRESS_SPACE) \
  /src/include/linux/sched/task_stack.h \
    $(wildcard include/config/DEBUG_STACK_USAGE) \
  /src/include/uapi/linux/magic.h \
  /src/include/linux/sched/cputime.h \
  /src/include/linux/sched/signal.h \
    $(wildcard include/config/BSD_PROCESS_ACCT) \
    $(wildcard include/config/TASKSTATS) \
  /src/include/linux/rculist.h \
    $(wildcard include/config/PROVE_RCU_LIST) \
  /src/include/linux/signal.h \
    $(wildcard include/config/DYNAMIC_SIGFRAME) \
  /src/include/linux/sched/jobctl.h \
  /src/include/linux/cred.h \
  /src/include/linux/capability.h \
  /src/include/uapi/linux/capability.h \
  /src/include/linux/key.h \
    $(wildcard include/config/KEY_NOTIFICATIONS) \
  /src/include/linux/sysctl.h \
    $(wildcard include/config/SYSCTL) \
  /src/include/uapi/linux/sysctl.h \
  /src/include/linux/assoc_array.h \
    $(wildcard include/config/ASSOCIATIVE_ARRAY) \
  /src/include/linux/pid.h \
  /src/include/linux/posix-timers.h \
  /src/include/linux/alarmtimer.h \
    $(wildcard include/config/RTC_CLASS) \
  /src/include/linux/hrtimer.h \
    $(wildcard include/config/HIGH_RES_TIMERS) \
    $(wildcard include/config/TIME_LOW_RES) \
    $(wildcard include/config/TIMERFD) \
  /src/include/linux/hrtimer_defs.h \
  /src/include/linux/timerqueue.h \
  /src/include/linux/rcuref.h \
  /src/include/linux/seq_file.h \
  /src/include/linux/string_helpers.h \
  /src/include/linux/ctype.h \
  /src/include/linux/string_choices.h \
  /src/include/linux/fs.h \
    $(wildcard include/config/FANOTIFY_ACCESS_PERMISSIONS) \
    $(wildcard include/config/READ_ONLY_THP_FOR_FS) \
    $(wildcard include/config/FS_POSIX_ACL) \
    $(wildcard include/config/CGROUP_WRITEBACK) \
    $(wildcard include/config/IMA) \
    $(wildcard include/config/FILE_LOCKING) \
    $(wildcard include/config/FSNOTIFY) \
    $(wildcard include/config/UNICODE) \
    $(wildcard include/config/FS_ENCRYPTION) \
    $(wildcard include/config/FS_VERITY) \
    $(wildcard include/config/QUOTA) \
    $(wildcard include/config/FS_DAX) \
  /src/include/linux/vfsdebug.h \
    $(wildcard include/config/DEBUG_VFS) \
  /src/include/linux/wait_bit.h \
  /src/include/linux/kdev_t.h \
  /src/include/uapi/linux/kdev_t.h \
  /src/include/linux/dcache.h \
  /src/include/linux/rculist_bl.h \
  /src/include/linux/list_bl.h \
  /src/include/linux/bit_spinlock.h \
  /src/include/linux/lockref.h \
    $(wildcard include/config/ARCH_USE_CMPXCHG_LOCKREF) \
  /src/include/linux/stringhash.h \
    $(wildcard include/config/DCACHE_WORD_ACCESS) \
  /src/include/linux/path.h \
  /src/include/linux/stat.h \
  /src/arch/x86/include/uapi/asm/stat.h \
  /src/include/uapi/linux/stat.h \
  /src/include/linux/list_lru.h \
  /src/include/linux/shrinker.h \
    $(wildcard include/config/SHRINKER_DEBUG) \
  /src/include/linux/xarray.h \
    $(wildcard include/config/XARRAY_MULTI) \
  /src/include/linux/radix-tree.h \
  /src/include/linux/semaphore.h \
  /src/include/linux/fcntl.h \
    $(wildcard include/config/ARCH_32BIT_OFF_T) \
  /src/include/uapi/linux/fcntl.h \
  arch/x86/include/generated/uapi/asm/fcntl.h \
  /src/include/uapi/asm-generic/fcntl.h \
  /src/include/uapi/linux/openat2.h \
  /src/include/linux/migrate_mode.h \
  /src/include/linux/percpu-rwsem.h \
  /src/include/linux/rcuwait.h \
  /src/include/linux/rcu_sync.h \
  /src/include/linux/delayed_call.h \
  /src/include/linux/uuid.h \
  /src/include/linux/errseq.h \
  /src/include/linux/ioprio.h \
  /src/include/linux/sched/rt.h \
  /src/include/linux/iocontext.h \
    $(wildcard include/config/BLK_ICQ) \
  /src/include/uapi/linux/ioprio.h \
  /src/include/linux/fs_types.h \
  /src/include/linux/mount.h \
  /src/include/linux/mnt_idmapping.h \
  /src/include/linux/rw_hint.h \
  /src/include/linux/file_ref.h \
  /src/include/linux/unicode.h \
  /src/include/uapi/linux/fs.h \
  /src/include/linux/quota.h \
    $(wildcard include/config/QUOTA_NETLINK_INTERFACE) \
  /src/include/uapi/linux/dqblk_xfs.h \
  /src/include/linux/dqblk_v1.h \
  /src/include/linux/dqblk_v2.h \
  /src/include/linux/dqblk_qtree.h \
  /src/include/linux/projid.h \
  /src/include/uapi/linux/quota.h \
  /src/include/linux/rtmutex.h \
    $(wildcard include/config/DEBUG_RT_MUTEXES) \
  /src/include/uapi/linux/unistd.h \
  /src/arch/x86/include/asm/unistd.h \
  /src/arch/x86/include/uapi/asm/unistd.h \
  arch/x86/include/generated/uapi/asm/unistd_64.h \
  arch/x86/include/generated/asm/unistd_64_x32.h \
  arch/x86/include/generated/asm/unistd_32_ia32.h \
  /src/include/linux/module.h \
    $(wildcard include/config/MODULES_TREE_LOOKUP) \
    $(wildcard include/config/STACKTRACE_BUILD_ID) \
    $(wildcard include/config/ARCH_USES_CFI_TRAPS) \
    $(wildcard include/config/MODULE_SIG) \
    $(wildcard include/config/KALLSYMS) \
    $(wildcard include/config/BPF_EVENTS) \
    $(wildcard include/config/DEBUG_INFO_BTF_MODULES) \
    $(wildcard include/config/EVENT_TRACING) \
    $(wildcard include/config/MODULE_UNLOAD) \
    $(wildcard include/config/CONSTRUCTORS) \
    $(wildcard include/config/FUNCTION_ERROR_INJECTION) \
  /src/include/linux/buildid.h \
    $(wildcard include/config/VMCORE_INFO) \
  /src/include/linux/kmod.h \
  /src/include/linux/umh.h \
  /src/include/linux/elf.h \
    $(wildcard include/config/ARCH_HAVE_EXTRA_ELF_NOTES) \
    $(wildcard include/config/ARCH_USE_GNU_PROPERTY) \
    $(wildcard include/config/ARCH_HAVE_ELF_PROT) \
  /src/arch/x86/include/asm/elf.h \
    $(wildcard include/config/X86_X32_ABI) \
  /src/arch/x86/include/asm/ia32.h \
  /src/arch/x86/include/asm/user.h \
  /src/arch/x86/include/asm/user_64.h \
  /src/arch/x86/include/asm/fsgsbase.h \
  /src/arch/x86/include/asm/vdso.h \
  /src/include/uapi/linux/elf.h \
  /src/include/uapi/linux/elf-em.h \
  /src/include/linux/kobject.h \
    $(wildcard include/config/UEVENT_HELPER) \
    $(wildcard include/config/DEBUG_KOBJECT_RELEASE) \
  /src/include/linux/sysfs.h \
  /src/include/linux/kernfs.h \
    $(wildcard include/config/KERNFS) \
  /src/include/linux/idr.h \
  /src/include/linux/kobject_ns.h \
  /src/include/linux/moduleparam.h \
    $(wildcard include/config/ALPHA) \
    $(wildcard include/config/PPC64) \
  /src/include/linux/rbtree_latch.h \
  /src/include/linux/error-injection.h \
  /src/include/asm-generic/error-injection.h \
  /src/include/linux/dynamic_debug.h \
  /src/arch/x86/include/asm/module.h \
    $(wildcard include/config/UNWINDER_ORC) \
  /src/include/asm-generic/module.h \
    $(wildcard include/config/HAVE_MOD_ARCH_SPECIFIC) \
  /src/include/linux/vmalloc.h \
    $(wildcard include/config/HAVE_ARCH_HUGE_VMALLOC) \
  /src/arch/x86/include/asm/vmalloc.h \
    $(wildcard include/config/HAVE_ARCH_HUGE_VMAP) \
  /src/arch/x86/include/asm/pgtable_areas.h \
  /src/include/linux/mempolicy.h \
    $(wildcard include/config/TMPFS) \
  /src/include/linux/node.h \
    $(wildcard include/config/HMEM_REPORTING) \
  /src/include/linux/device.h \
    $(wildcard include/config/GENERIC_MSI_IRQ) \
    $(wildcard include/config/ENERGY_MODEL) \
    $(wildcard include/config/PINCTRL) \
    $(wildcard include/config/ARCH_HAS_DMA_OPS) \
    $(wildcard include/config/DMA_DECLARE_COHERENT) \
    $(wildcard include/config/DMA_CMA) \
    $(wildcard include/config/SWIOTLB) \
    $(wildcard include/config/SWIOTLB_DYNAMIC) \
    $(wildcard include/config/ARCH_HAS_SYNC_DMA_FOR_DEVICE) \
    $(wildcard include/config/ARCH_HAS_SYNC_DMA_FOR_CPU) \
    $(wildcard include/config/ARCH_HAS_SYNC_DMA_FOR_CPU_ALL) \
    $(wildcard include/config/DMA_OPS_BYPASS) \
    $(wildcard include/config/DMA_NEED_SYNC) \
    $(wildcard include/config/IOMMU_DMA) \
    $(wildcard include/config/PM) \
    $(wildcard include/config/PM_SLEEP) \
    $(wildcard include/config/OF) \
    $(wildcard include/config/DEVTMPFS) \
  /src/include/linux/dev_printk.h \
  /src/include/linux/energy_model.h \
  /src/include/linux/sched/cpufreq.h \
    $(wildcard include/config/CPU_FREQ) \
  /src/include/linux/sched/topology.h \
    $(wildcard include/config/SCHED_CLUSTER) \
    $(wildcard include/config/SCHED_MC) \
    $(wildcard include/config/CPU_FREQ_GOV_SCHEDUTIL) \
  /src/include/linux/sched/idle.h \
  /src/include/linux/sched/sd_flags.h \
  /src/include/linux/ioport.h \
  /src/include/linux/klist.h \
  /src/include/linux/pm.h \
    $(wildcard include/config/VT_CONSOLE_SLEEP) \
    $(wildcard include/config/CXL_SUSPEND) \
    $(wildcard include/config/PM_CLK) \
    $(wildcard include/config/PM_GENERIC_DOMAINS) \
  /src/include/linux/device/bus.h \
    $(wildcard include/config/ACPI) \
  /src/include/linux/device/class.h \
  /src/include/linux/device/devres.h \
    $(wildcard include/config/HAS_IOMEM) \
  /src/include/linux/device/driver.h \
  /src/arch/x86/include/asm/device.h \
  /src/include/linux/pm_wakeup.h \
  /src/include/linux/pagemap.h \
  /src/include/linux/mm.h \
    $(wildcard include/config/HAVE_ARCH_MMAP_RND_BITS) \
    $(wildcard include/config/HAVE_ARCH_MMAP_RND_COMPAT_BITS) \
    $(wildcard include/config/ARCH_USES_HIGH_VMA_FLAGS) \
    $(wildcard include/config/ARCH_HAS_PKEYS) \
    $(wildcard include/config/ARCH_PKEY_BITS) \
    $(wildcard include/config/ARM64_GCS) \
    $(wildcard include/config/PARISC) \
    $(wildcard include/config/SPARC64) \
    $(wildcard include/config/ARM64_MTE) \
    $(wildcard include/config/HAVE_ARCH_USERFAULTFD_MINOR) \
    $(wildcard include/config/PPC32) \
    $(wildcard include/config/FIND_NORMAL_PAGE) \
    $(wildcard include/config/SHMEM) \
    $(wildcard include/config/HAVE_GIGANTIC_FOLIOS) \
    $(wildcard include/config/ARCH_HAS_PTE_SPECIAL) \
    $(wildcard include/config/ASYNC_KERNEL_PGTABLE_FREE) \
    $(wildcard include/config/SPLIT_PTE_PTLOCKS) \
    $(wildcard include/config/HIGHPTE) \
    $(wildcard include/config/DEBUG_VM_RB) \
    $(wildcard include/config/PAGE_POISONING) \
    $(wildcard include/config/INIT_ON_ALLOC_DEFAULT_ON) \
    $(wildcard include/config/INIT_ON_FREE_DEFAULT_ON) \
    $(wildcard include/config/DEBUG_PAGEALLOC) \
    $(wildcard include/config/ARCH_WANT_OPTIMIZE_DAX_VMEMMAP) \
    $(wildcard include/config/HUGETLBFS) \
    $(wildcard include/config/MAPPING_DIRTY_HELPERS) \
    $(wildcard include/config/MSEAL_SYSTEM_MAPPINGS) \
    $(wildcard include/config/PAGE_POOL) \
  /src/include/linux/pgalloc_tag.h \
  /src/include/linux/page_ext.h \
  /src/include/linux/page_ref.h \
    $(wildcard include/config/DEBUG_PAGE_REF) \
  /src/include/linux/sizes.h \
  /src/include/linux/pgtable.h \
    $(wildcard include/config/ARCH_HAS_NONLEAF_PMD_YOUNG) \
    $(wildcard include/config/ARCH_HAS_HW_PTE_YOUNG) \
    $(wildcard include/config/GUP_GET_PXX_LOW_HIGH) \
    $(wildcard include/config/ARCH_WANT_PMD_MKWRITE) \
    $(wildcard include/config/X86_ESPFIX64) \
  /src/include/linux/memremap.h \
    $(wildcard include/config/DEVICE_PRIVATE) \
    $(wildcard include/config/PCI_P2PDMA) \
  /src/include/linux/cacheinfo.h \
    $(wildcard include/config/ACPI_PPTT) \
    $(wildcard include/config/ARM) \
    $(wildcard include/config/ARCH_HAS_CPU_CACHE_ALIASING) \
  /src/include/linux/cpuhplock.h \
  /src/include/linux/huge_mm.h \
    $(wildcard include/config/PGTABLE_HAS_HUGE_LEAVES) \
    $(wildcard include/config/PERSISTENT_HUGE_ZERO_FOLIO) \
  /src/include/linux/vmstat.h \
    $(wildcard include/config/VM_EVENT_COUNTERS) \
    $(wildcard include/config/DEBUG_TLBFLUSH) \
    $(wildcard include/config/PER_VMA_LOCK_STATS) \
  /src/include/linux/vm_event_item.h \
    $(wildcard include/config/MEMORY_BALLOON) \
    $(wildcard include/config/BALLOON_COMPACTION) \
    $(wildcard include/config/X86) \
  /src/include/linux/highmem.h \
  /src/include/linux/cacheflush.h \
  /src/arch/x86/include/asm/cacheflush.h \
  /src/include/asm-generic/cacheflush.h \
  /src/include/linux/kmsan.h \
  /src/include/linux/dma-direction.h \
  /src/include/linux/hardirq.h \
  /src/include/linux/context_tracking_state.h \
    $(wildcard include/config/CONTEXT_TRACKING_USER) \
    $(wildcard include/config/CONTEXT_TRACKING) \
  /src/include/linux/ftrace_irq.h \
    $(wildcard include/config/HWLAT_TRACER) \
    $(wildcard include/config/OSNOISE_TRACER) \
  /src/include/linux/vtime.h \
    $(wildcard include/config/VIRT_CPU_ACCOUNTING) \
    $(wildcard include/config/IRQ_TIME_ACCOUNTING) \
  /src/arch/x86/include/asm/hardirq.h \
    $(wildcard include/config/KVM_INTEL) \
    $(wildcard include/config/KVM) \
    $(wildcard include/config/X86_THERMAL_VECTOR) \
    $(wildcard include/config/X86_MCE_THRESHOLD) \
    $(wildcard include/config/X86_MCE_AMD) \
    $(wildcard include/config/X86_HV_CALLBACK_VECTOR) \
    $(wildcard include/config/HYPERV) \
    $(wildcard include/config/X86_POSTED_MSI) \
  /src/include/linux/highmem-internal.h \
  /src/include/linux/hugetlb_inline.h \
  /src/include/uapi/linux/mempolicy.h \
  /src/include/linux/sem.h \
  /src/include/uapi/linux/sem.h \
  /src/include/linux/ipc.h \
  /src/include/linux/rhashtable-types.h \
  /src/include/uapi/linux/ipc.h \
  arch/x86/include/generated/uapi/asm/ipcbuf.h \
  /src/include/uapi/asm-generic/ipcbuf.h \
  /src/arch/x86/include/uapi/asm/sembuf.h \
  /src/include/linux/file.h \
  /src/include/linux/fdtable.h \
  /src/include/linux/binfmts.h \
    $(wildcard include/config/COREDUMP) \
    $(wildcard include/config/BINFMT_MISC) \
  /src/arch/x86/include/asm/exec.h \
  /src/include/uapi/linux/binfmts.h \
  /src/include/linux/mman.h \
  /src/include/uapi/linux/mman.h \
  /src/arch/x86/include/asm/mman.h \
  /src/arch/x86/include/uapi/asm/mman.h \
  /src/include/uapi/asm-generic/mman.h \
  /src/include/uapi/asm-generic/mman-common.h \
  /src/include/uapi/asm-generic/hugetlb_encode.h \
  /src/include/linux/mm_inline.h \
    $(wildcard include/config/LRU_GEN_ENABLED) \
    $(wildcard include/config/PTE_MARKER_UFFD_WP) \
  /src/include/linux/swap.h \
    $(wildcard include/config/THP_SWAP) \
  /src/include/linux/memcontrol.h \
    $(wildcard include/config/MEMCG_NMI_SAFETY_REQUIRES_ATOMIC) \
  /src/include/linux/cgroup.h \
    $(wildcard include/config/DEBUG_CGROUP_REF) \
    $(wildcard include/config/CGROUP_CPUACCT) \
    $(wildcard include/config/SOCK_CGROUP_DATA) \
    $(wildcard include/config/CGROUP_DATA) \
    $(wildcard include/config/CGROUP_BPF) \
  /src/include/uapi/linux/cgroupstats.h \
  /src/include/uapi/linux/taskstats.h \
  /src/include/linux/ns_common.h \
    $(wildcard include/config/IPC_NS) \
    $(wildcard include/config/NET_NS) \
    $(wildcard include/config/PID_NS) \
    $(wildcard include/config/TIME_NS) \
    $(wildcard include/config/UTS_NS) \
  /src/include/linux/nsproxy.h \
  /src/include/linux/user_namespace.h \
    $(wildcard include/config/INOTIFY_USER) \
    $(wildcard include/config/FANOTIFY) \
    $(wildcard include/config/PERSISTENT_KEYRINGS) \
  /src/include/linux/rculist_nulls.h \
  /src/include/linux/kernel_stat.h \
    $(wildcard include/config/GENERIC_IRQ_STAT_SNAPSHOT) \
  /src/include/linux/interrupt.h \
    $(wildcard include/config/IRQ_FORCED_THREADING) \
    $(wildcard include/config/GENERIC_IRQ_PROBE) \
    $(wildcard include/config/IRQ_TIMINGS) \
  /src/include/linux/irqreturn.h \
  /src/arch/x86/include/asm/irq.h \
  /src/arch/x86/include/asm/irq_vectors.h \
    $(wildcard include/config/PCI_MSI) \
  /src/arch/x86/include/asm/sections.h \
  /src/include/asm-generic/sections.h \
    $(wildcard include/config/HAVE_FUNCTION_DESCRIPTORS) \
  /src/include/linux/cgroup-defs.h \
    $(wildcard include/config/CGROUP_NET_CLASSID) \
    $(wildcard include/config/CGROUP_NET_PRIO) \
  /src/include/linux/u64_stats_sync.h \
  arch/x86/include/generated/asm/local64.h \
  /src/include/asm-generic/local64.h \
  /src/arch/x86/include/asm/local.h \
  /src/include/linux/bpf-cgroup-defs.h \
    $(wildcard include/config/BPF_LSM) \
  /src/include/linux/psi_types.h \
  /src/include/linux/kthread.h \
  /src/include/linux/cgroup_namespace.h \
  /src/include/linux/page_counter.h \
    $(wildcard include/config/CGROUP_DMEM) \
  /src/include/linux/vmpressure.h \
  /src/include/linux/eventfd.h \
  /src/include/uapi/linux/eventfd.h \
  /src/include/linux/writeback.h \
  /src/include/linux/flex_proportions.h \
  /src/include/linux/backing-dev-defs.h \
    $(wildcard include/config/DEBUG_FS) \
  /src/include/linux/blk_types.h \
    $(wildcard include/config/FAIL_MAKE_REQUEST) \
    $(wildcard include/config/BLK_CGROUP_IOCOST) \
    $(wildcard include/config/BLK_INLINE_ENCRYPTION) \
    $(wildcard include/config/BLK_DEV_INTEGRITY) \
  /src/include/linux/bvec.h \
  /src/include/linux/pagevec.h \
  /src/include/linux/userfaultfd_k.h \
  /src/include/linux/swapops.h \
  /src/include/linux/memblock.h \
    $(wildcard include/config/ARCH_KEEP_MEMBLOCK) \
    $(wildcard include/config/HAVE_MEMBLOCK_PHYS_MAP) \
    $(wildcard include/config/MEMTEST) \
    $(wildcard include/config/MEMBLOCK_KHO_SCRATCH) \
  /src/arch/x86/include/asm/dma.h \
    $(wildcard include/config/ISA_DMA_API) \
    $(wildcard include/config/GENERIC_ISA_DMA) \
  /src/arch/x86/include/asm/io.h \
    $(wildcard include/config/MTRR) \
    $(wildcard include/config/X86_PAT) \
  arch/x86/include/generated/asm/early_ioremap.h \
  /src/include/asm-generic/early_ioremap.h \
    $(wildcard include/config/GENERIC_EARLY_IOREMAP) \
  /src/arch/x86/include/asm/shared/io.h \
  /src/include/asm-generic/io.h \
    $(wildcard include/config/GENERIC_IOMAP) \
    $(wildcard include/config/TRACE_MMIO_ACCESS) \
    $(wildcard include/config/HAS_IOPORT) \
    $(wildcard include/config/GENERIC_IOREMAP) \
    $(wildcard include/config/HAS_IOPORT_MAP) \
  /src/include/asm-generic/iomap.h \
  /src/include/asm-generic/pci_iomap.h \
    $(wildcard include/config/PCI) \
    $(wildcard include/config/NO_GENERIC_PCI_IOPORT_MAP) \
    $(wildcard include/config/GENERIC_PCI_IOMAP) \
  /src/include/linux/logic_pio.h \
    $(wildcard include/config/INDIRECT_PIO) \
  /src/include/linux/fwnode.h \
  /src/include/linux/cpu.h \
    $(wildcard include/config/GENERIC_CPU_DEVICES) \
    $(wildcard include/config/PM_SLEEP_SMP) \
    $(wildcard include/config/PM_SLEEP_SMP_NONZERO_CPU) \
    $(wildcard include/config/ARCH_HAS_CPU_FINALIZE_INIT) \
    $(wildcard include/config/CPU_MITIGATIONS) \
  /src/include/linux/cpuhotplug.h \
    $(wildcard include/config/HOTPLUG_CORE_SYNC_DEAD) \
  /src/include/linux/security.h \
    $(wildcard include/config/SECURITY_NETWORK) \
    $(wildcard include/config/SECURITY_INFINIBAND) \
    $(wildcard include/config/SECURITY_NETWORK_XFRM) \
    $(wildcard include/config/SECURITY_PATH) \
    $(wildcard include/config/SECURITYFS) \
  /src/include/linux/kernel_read_file.h \
  /src/include/linux/sockptr.h \
  /src/include/linux/bpf.h \
    $(wildcard include/config/DEBUG_KERNEL) \
    $(wildcard include/config/FINEIBT) \
    $(wildcard include/config/BPF_JIT_ALWAYS_ON) \
    $(wildcard include/config/INET) \
  /src/include/uapi/linux/bpf.h \
    $(wildcard include/config/BPF_LIRC_MODE2) \
    $(wildcard include/config/EFFICIENT_UNALIGNED_ACCESS) \
    $(wildcard include/config/IP_ROUTE_CLASSID) \
    $(wildcard include/config/BPF_KPROBE_OVERRIDE) \
    $(wildcard include/config/XFRM) \
    $(wildcard include/config/IPV6) \
  /src/include/uapi/linux/bpf_common.h \
  /src/include/uapi/linux/filter.h \
  /src/include/crypto/sha2.h \
  /src/include/linux/kallsyms.h \
    $(wildcard include/config/KALLSYMS_ALL) \
  /src/include/linux/bpfptr.h \
  /src/include/linux/btf.h \
  /src/include/linux/bsearch.h \
  /src/include/linux/btf_ids.h \
  /src/include/uapi/linux/btf.h \
  /src/include/linux/rcupdate_trace.h \
    $(wildcard include/config/TASKS_TRACE_RCU_READ_MB) \
  /src/include/linux/static_call.h \
  /src/arch/x86/include/asm/static_call.h \
  /src/arch/x86/include/asm/text-patching.h \
    $(wildcard include/config/UML_X86) \
  /src/include/linux/cfi.h \
  /src/arch/x86/include/asm/cfi.h \
    $(wildcard include/config/FINEIBT_BHI) \
    $(wildcard include/config/FUNCTION_PADDING_CFI) \
  /src/arch/x86/include/asm/rqspinlock.h \
    $(wildcard include/config/QUEUED_SPINLOCKS) \
  /src/include/asm-generic/rqspinlock.h \
  /src/include/uapi/linux/lsm.h \
  /src/include/linux/lsm/selinux.h \
    $(wildcard include/config/SECURITY_SELINUX) \
  /src/include/linux/lsm/smack.h \
    $(wildcard include/config/SECURITY_SMACK) \
  /src/include/linux/lsm/apparmor.h \
    $(wildcard include/config/SECURITY_APPARMOR) \
  /src/include/linux/lsm/bpf.h \
  /src/include/linux/hugetlb.h \
    $(wildcard include/config/CGROUP_HUGETLB) \
    $(wildcard include/config/ARCH_ENABLE_HUGEPAGE_MIGRATION) \
  /src/include/linux/seccomp.h \
    $(wildcard include/config/HAVE_ARCH_SECCOMP_FILTER) \
    $(wildcard include/config/SECCOMP_FILTER) \
    $(wildcard include/config/CHECKPOINT_RESTORE) \
    $(wildcard include/config/SECCOMP_CACHE_DEBUG) \
  /src/include/uapi/linux/seccomp.h \
  /src/arch/x86/include/asm/seccomp.h \
  /src/include/asm-generic/seccomp.h \
  /src/include/linux/syscalls.h \
    $(wildcard include/config/ARCH_HAS_SYSCALL_WRAPPER) \
    $(wildcard include/config/FTRACE_SYSCALLS) \
    $(wildcard include/config/ODD_RT_SIGACTION) \
    $(wildcard include/config/ARCH_SPLIT_ARG64) \
    $(wildcard include/config/OLD_SIGSUSPEND) \
    $(wildcard include/config/OLD_SIGSUSPEND3) \
    $(wildcard include/config/ADVISE_SYSCALLS) \
  /src/include/uapi/linux/aio_abi.h \
  /src/include/trace/syscall.h \
    $(wildcard include/config/HAVE_SYSCALL_TRACEPOINTS) \
  /src/include/linux/tracepoint.h \
  /src/include/linux/trace_events.h \
    $(wildcard include/config/DYNAMIC_EVENTS) \
    $(wildcard include/config/HIST_TRIGGERS) \
    $(wildcard include/config/KPROBE_EVENTS) \
    $(wildcard include/config/UPROBE_EVENTS) \
  /src/include/linux/ring_buffer.h \
    $(wildcard include/config/RING_BUFFER_ALLOW_SWAP) \
    $(wildcard include/config/RING_BUFFER) \
  /src/include/linux/poll.h \
  /src/include/uapi/linux/poll.h \
  arch/x86/include/generated/uapi/asm/poll.h \
  /src/include/uapi/asm-generic/poll.h \
  /src/include/uapi/linux/eventpoll.h \
  /src/include/uapi/linux/trace_mmap.h \
  /src/include/linux/trace_seq.h \
  /src/include/linux/seq_buf.h \
  /src/include/linux/perf_event.h \
    $(wildcard include/config/HAVE_HW_BREAKPOINT) \
    $(wildcard include/config/FUNCTION_TRACER) \
    $(wildcard include/config/CGROUP_PERF) \
    $(wildcard include/config/GUEST_PERF_EVENTS) \
    $(wildcard include/config/CPU_SUP_INTEL) \
  /src/include/uapi/linux/perf_event.h \
  /src/include/uapi/linux/bpf_perf_event.h \
  arch/x86/include/generated/uapi/asm/bpf_perf_event.h \
  /src/include/uapi/asm-generic/bpf_perf_event.h \
  /src/include/linux/ptrace.h \
  /src/include/linux/pid_namespace.h \
    $(wildcard include/config/MEMFD_CREATE) \
  /src/include/uapi/linux/ptrace.h \
  /src/arch/x86/include/asm/perf_event.h \
    $(wildcard include/config/PERF_EVENTS_AMD_BRS) \
  /src/arch/x86/include/asm/stacktrace.h \
  /src/arch/x86/include/asm/cpu_entry_area.h \
  /src/arch/x86/include/asm/intel_ds.h \
  /src/arch/x86/include/asm/switch_to.h \
  /src/arch/x86/include/asm/hw_breakpoint.h \
  /src/arch/x86/include/uapi/asm/hw_breakpoint.h \
  /src/include/linux/kdebug.h \
  /src/arch/x86/include/asm/kdebug.h \
  /src/include/linux/ftrace.h \
    $(wildcard include/config/HAVE_FUNCTION_GRAPH_FREGS) \
    $(wildcard include/config/HAVE_DYNAMIC_FTRACE_WITH_ARGS) \
    $(wildcard include/config/HAVE_FTRACE_REGS_HAVING_PT_REGS) \
    $(wildcard include/config/HAVE_REGS_AND_STACK_ACCESS_API) \
    $(wildcard include/config/DYNAMIC_FTRACE_WITH_REGS) \
    $(wildcard include/config/DYNAMIC_FTRACE_WITH_ARGS) \
    $(wildcard include/config/DYNAMIC_FTRACE_WITH_DIRECT_CALLS) \
    $(wildcard include/config/STACK_TRACER) \
    $(wildcard include/config/DYNAMIC_FTRACE_WITH_CALL_OPS) \
    $(wildcard include/config/FUNCTION_GRAPH_RETVAL) \
  /src/include/linux/trace_recursion.h \
    $(wildcard include/config/FTRACE_RECORD_RECURSION) \
    $(wildcard include/config/FTRACE_VALIDATE_RCU_IS_WATCHING) \
  /src/include/linux/trace_clock.h \
  /src/arch/x86/include/asm/trace_clock.h \
  /src/arch/x86/include/asm/ftrace.h \
    $(wildcard include/config/HAVE_FENTRY) \
  /src/include/linux/irq_work.h \
    $(wildcard include/config/IRQ_WORK) \
  /src/include/linux/irq_work_types.h \
  /src/arch/x86/include/asm/irq_work.h \
  /src/include/linux/jump_label_ratelimit.h \
  /src/include/linux/perf_regs.h \
    $(wildcard include/config/HAVE_PERF_REGS) \
  /src/arch/x86/include/uapi/asm/perf_regs.h \
  /src/arch/x86/include/asm/syscall_wrapper.h \
  /src/include/linux/syscall_user_dispatch.h \
  /src/include/linux/futex.h \
  /src/include/uapi/linux/futex.h \
  /src/include/linux/compat.h \
    $(wildcard include/config/COMPAT_OLD_SIGACTION) \
  /src/include/linux/socket.h \
  arch/x86/include/generated/uapi/asm/socket.h \
  /src/include/uapi/asm-generic/socket.h \
  arch/x86/include/generated/uapi/asm/sockios.h \
  /src/include/uapi/asm-generic/sockios.h \
  /src/include/uapi/linux/sockios.h \
  /src/include/linux/uio.h \
  /src/include/uapi/linux/uio.h \
  /src/include/uapi/linux/socket.h \
  /src/include/uapi/linux/if.h \
  /src/include/uapi/linux/libc-compat.h \
  /src/include/uapi/linux/hdlc/ioctl.h \
  /src/arch/x86/include/asm/compat.h \
  /src/arch/x86/include/asm/user32.h \
  /src/include/asm-generic/compat.h \
    $(wildcard include/config/COMPAT_FOR_U64_ALIGNMENT) \
  /src/include/linux/task_io_accounting_ops.h \
  /src/include/linux/audit.h \
    $(wildcard include/config/AUDIT_COMPAT_GENERIC) \
  /src/include/linux/audit_arch.h \
  /src/include/uapi/linux/audit.h \
  /src/include/uapi/linux/netfilter/nf_tables.h \
  /src/include/uapi/linux/fanotify.h \
  /src/include/linux/proc_fs.h \
    $(wildcard include/config/PROC_PID_ARCH_STATUS) \
  /src/include/linux/profile.h \
    $(wildcard include/config/PROFILING) \
  /src/include/linux/rmap.h \
    $(wildcard include/config/SLUB_RCU_DEBUG) \
    $(wildcard include/config/HAVE_GUP_FAST) \
    $(wildcard include/config/PAGE_MAPCOUNT) \
  /src/include/linux/ksm.h \
  /src/include/linux/acct.h \
    $(wildcard include/config/BSD_PROCESS_ACCT_V3) \
    $(wildcard include/config/M68K) \
  /src/include/uapi/linux/acct.h \
  /src/include/linux/tsacct_kern.h \
  /src/include/linux/cn_proc.h \
    $(wildcard include/config/PROC_EVENTS) \
  /src/include/uapi/linux/cn_proc.h \
  /src/include/linux/freezer.h \
    $(wildcard include/config/CGROUP_FREEZER) \
  /src/include/linux/delayacct.h \
  /src/include/linux/taskstats_kern.h \
  /src/include/linux/tty.h \
    $(wildcard include/config/TTY) \
  /src/include/uapi/linux/major.h \
  /src/include/uapi/linux/termios.h \
  arch/x86/include/generated/uapi/asm/termios.h \
  /src/include/uapi/asm-generic/termios.h \
  arch/x86/include/generated/uapi/asm/termbits.h \
  /src/include/uapi/asm-generic/termbits.h \
  /src/include/uapi/asm-generic/termbits-common.h \
  arch/x86/include/generated/uapi/asm/ioctls.h \
  /src/include/uapi/asm-generic/ioctls.h \
  /src/include/linux/tty_driver.h \
    $(wildcard include/config/CONSOLE_POLL) \
  /src/include/linux/cdev.h \
  /src/include/linux/tty_ldisc.h \
  /src/include/linux/tty_port.h \
  /src/include/linux/kfifo.h \
  /src/include/linux/tty_buffer.h \
  /src/include/uapi/linux/tty_flags.h \
  /src/include/uapi/linux/tty.h \
  /src/include/linux/fs_struct.h \
  /src/include/linux/user-return-notifier.h \
    $(wildcard include/config/USER_RETURN_NOTIFIER) \
  /src/include/linux/oom.h \
  /src/include/uapi/linux/oom.h \
  /src/include/linux/khugepaged.h \
  /src/include/linux/signalfd.h \
    $(wildcard include/config/SIGNALFD) \
  /src/include/uapi/linux/signalfd.h \
  /src/include/linux/aio.h \
  /src/include/linux/kcov.h \
  /src/include/uapi/linux/kcov.h \
  /src/include/linux/livepatch.h \
  /src/include/linux/livepatch_sched.h \
  /src/include/linux/kstack_erase.h \
  /src/include/linux/randomize_kstack.h \
    $(wildcard include/config/RANDOMIZE_KSTACK_OFFSET_DEFAULT) \
  /src/include/linux/scs.h \
    $(wildcard include/config/DYNAMIC_SCS) \
  /src/include/linux/io_uring.h \
  /src/include/uapi/linux/io_uring.h \
  /src/include/linux/stackprotector.h \
    $(wildcard include/config/ARM64_PTR_AUTH) \
  /src/arch/x86/include/asm/stackprotector.h \
  /src/arch/x86/include/asm/desc.h \
  /src/include/linux/user_events.h \
  /src/include/uapi/linux/user_events.h \
  /src/include/linux/iommu.h \
    $(wildcard include/config/IOMMU_API) \
    $(wildcard include/config/FSL_PAMU) \
    $(wildcard include/config/IRQ_MSI_IOMMU) \
    $(wildcard include/config/IOMMU_DEBUGFS) \
    $(wildcard include/config/IOMMU_SVA) \
    $(wildcard include/config/IOMMU_IOPF) \
  /src/include/linux/scatterlist.h \
    $(wildcard include/config/NEED_SG_DMA_LENGTH) \
    $(wildcard include/config/NEED_SG_DMA_FLAGS) \
    $(wildcard include/config/DEBUG_SG) \
    $(wildcard include/config/SGL_ALLOC) \
    $(wildcard include/config/ARCH_NO_SG_CHAIN) \
    $(wildcard include/config/SG_POOL) \
  /src/include/linux/of.h \
    $(wildcard include/config/OF_DYNAMIC) \
    $(wildcard include/config/SPARC) \
    $(wildcard include/config/OF_PROMTREE) \
    $(wildcard include/config/OF_KOBJ) \
    $(wildcard include/config/OF_NUMA) \
    $(wildcard include/config/OF_OVERLAY) \
  /src/include/linux/mod_devicetable.h \
  /src/include/uapi/linux/mei.h \
  /src/include/uapi/linux/mei_uuid.h \
  /src/include/linux/property.h \
  /src/include/linux/iova_bitmap.h \
    $(wildcard include/config/IOMMUFD_DRIVER) \
  /src/include/uapi/linux/iommufd.h \
  /src/include/linux/rseq.h \
  /src/include/uapi/linux/pidfd.h \
  /src/include/linux/pidfs.h \
  /src/include/linux/tick.h \
    $(wildcard include/config/GENERIC_CLOCKEVENTS) \
    $(wildcard include/config/SUSPEND) \
    $(wildcard include/config/TICK_ONESHOT) \
    $(wildcard include/config/GENERIC_CLOCKEVENTS_BROADCAST) \
    $(wildcard include/config/NO_HZ_COMMON) \
  /src/include/linux/clockchips.h \
    $(wildcard include/config/ARCH_HAS_TICK_BROADCAST) \
  /src/include/linux/clocksource.h \
    $(wildcard include/config/ARCH_CLOCKSOURCE_DATA) \
    $(wildcard include/config/GENERIC_GETTIMEOFDAY) \
    $(wildcard include/config/CLOCKSOURCE_WATCHDOG) \
    $(wildcard include/config/ARCH_CLOCKSOURCE_INIT) \
    $(wildcard include/config/TIMER_PROBE) \
  /src/arch/x86/include/asm/clocksource.h \
  /src/arch/x86/include/asm/vdso/clocksource.h \
  /src/include/vdso/clocksource.h \
  /src/include/linux/unwind_deferred.h \
  /src/include/linux/task_work.h \
  /src/include/linux/unwind_user.h \
  /src/include/linux/unwind_user_types.h \
  /src/arch/x86/include/asm/unwind_user.h \
    $(wildcard include/config/HAVE_UNWIND_USER_FP) \
  /src/arch/x86/include/asm/uprobes.h \
  /src/arch/x86/include/asm/pgalloc.h \
  /src/include/asm-generic/pgalloc.h \
  /src/arch/x86/include/asm/mmu_context.h \
  /src/include/linux/pkeys.h \
  /src/include/trace/events/tlb.h \
  /src/include/trace/define_trace.h \
  /src/arch/x86/include/asm/debugreg.h \
  /src/arch/x86/include/uapi/asm/debugreg.h \
  /src/arch/x86/include/asm/gsseg.h \
  /src/include/asm-generic/mmu_context.h \
  /src/kernel/../mm/internal.h \
    $(wildcard include/config/NO_PAGE_MAPCOUNT) \
    $(wildcard include/config/DEBUG_MEMORY_INIT) \
    $(wildcard include/config/PT_RECLAIM) \
  /src/include/linux/pagewalk.h \
  /src/include/linux/swap_cgroup.h \
  /src/kernel/../mm/vma.h \
    $(wildcard include/config/DEBUG_VM_MAPLE_TREE) \
  /src/include/trace/events/sched.h \
  /src/include/trace/events/task.h \
  /src/include/trace/trace_events.h \
  /src/include/trace/stages/init.h \
  /src/include/trace/stages/stage1_struct_define.h \
  /src/include/trace/stages/stage2_data_offsets.h \
  /src/include/trace/stages/stage3_trace_output.h \
  /src/include/trace/stages/stage4_event_fields.h \
  /src/include/trace/stages/stage5_get_offsets.h \
  /src/include/trace/stages/stage6_event_callback.h \
  /src/include/trace/stages/stage7_class_define.h \
  /src/include/trace/perf.h \
  /src/include/trace/bpf_probe.h \
  /src/include/kunit/visibility.h \
  /src/kernel/task_construction_impl.h \
  /src/include/linux/init_task.h \
  /src/include/linux/utsname.h \
    $(wildcard include/config/PROC_SYSCTL) \
  /src/include/linux/uts_namespace.h \
  /src/include/uapi/linux/utsname.h \
  /src/include/linux/securebits.h \
  /src/include/uapi/linux/securebits.h \
  /src/include/net/net_namespace.h \
    $(wildcard include/config/NF_CONNTRACK) \
    $(wildcard include/config/NF_FLOW_TABLE) \
    $(wildcard include/config/UNIX) \
    $(wildcard include/config/IEEE802154_6LOWPAN) \
    $(wildcard include/config/IP_SCTP) \
    $(wildcard include/config/NETFILTER) \
    $(wildcard include/config/NF_TABLES) \
    $(wildcard include/config/WEXT_CORE) \
    $(wildcard include/config/IP_VS) \
    $(wildcard include/config/MPLS) \
    $(wildcard include/config/CAN) \
    $(wildcard include/config/XDP_SOCKETS) \
    $(wildcard include/config/MCTP) \
    $(wildcard include/config/CRYPTO_USER) \
    $(wildcard include/config/SMC) \
    $(wildcard include/config/DEBUG_NET_SMALL_RTNL) \
    $(wildcard include/config/NET_NS_REFCNT_TRACKER) \
  /src/include/net/flow.h \
  /src/include/linux/in6.h \
  /src/include/uapi/linux/in6.h \
  /src/include/net/inet_dscp.h \
  /src/include/net/netns/core.h \
    $(wildcard include/config/RPS) \
  /src/include/net/netns/mib.h \
    $(wildcard include/config/XFRM_STATISTICS) \
    $(wildcard include/config/TLS) \
    $(wildcard include/config/MPTCP) \
  /src/include/net/snmp.h \
  /src/include/uapi/linux/snmp.h \
  /src/include/net/netns/unix.h \
  /src/include/net/netns/packet.h \
  /src/include/net/netns/ipv4.h \
    $(wildcard include/config/IP_ROUTE_MULTIPATH) \
    $(wildcard include/config/NET_UDP_TUNNEL) \
    $(wildcard include/config/IP_MULTIPLE_TABLES) \
    $(wildcard include/config/NET_L3_MASTER_DEV) \
    $(wildcard include/config/IP_MROUTE) \
    $(wildcard include/config/IP_MROUTE_MULTIPLE_TABLES) \
  /src/include/net/inet_frag.h \
  /src/include/net/dropreason-core.h \
  /src/include/linux/siphash.h \
    $(wildcard include/config/HAVE_EFFICIENT_UNALIGNED_ACCESS) \
  /src/include/net/netns/ipv6.h \
    $(wildcard include/config/IPV6_MULTIPLE_TABLES) \
    $(wildcard include/config/IPV6_SUBTREES) \
    $(wildcard include/config/IPV6_MROUTE) \
    $(wildcard include/config/IPV6_MROUTE_MULTIPLE_TABLES) \
    $(wildcard include/config/NF_DEFRAG_IPV6) \
  /src/include/net/dst_ops.h \
  /src/include/uapi/linux/icmpv6.h \
  /src/include/net/netns/nexthop.h \
  /src/include/net/netns/ieee802154_6lowpan.h \
  /src/include/net/netns/sctp.h \
  /src/include/net/netns/netfilter.h \
    $(wildcard include/config/LWTUNNEL) \
    $(wildcard include/config/NETFILTER_FAMILY_ARP) \
    $(wildcard include/config/NETFILTER_FAMILY_BRIDGE) \
    $(wildcard include/config/NF_DEFRAG_IPV4) \
  /src/include/linux/netfilter_defs.h \
  /src/include/uapi/linux/netfilter.h \
  /src/include/linux/in.h \
  /src/include/uapi/linux/in.h \
  /src/include/net/netns/nftables.h \
  /src/include/net/netns/xfrm.h \
  /src/include/uapi/linux/xfrm.h \
  /src/include/net/netns/mpls.h \
  /src/include/net/netns/can.h \
  /src/include/net/netns/xdp.h \
  /src/include/net/netns/smc.h \
  /src/include/net/netns/bpf.h \
  /src/include/net/netns/mctp.h \
  /src/include/linux/hashtable.h \
  /src/include/net/net_trackers.h \
    $(wildcard include/config/NET_DEV_REFCNT_TRACKER) \
  /src/include/linux/ref_tracker.h \
    $(wildcard include/config/REF_TRACKER) \
  /src/include/linux/stackdepot.h \
    $(wildcard include/config/STACKDEPOT) \
    $(wildcard include/config/STACKDEPOT_MAX_FRAMES) \
    $(wildcard include/config/STACKDEPOT_ALWAYS_INIT) \
  /src/include/linux/skbuff.h \
    $(wildcard include/config/BRIDGE_NETFILTER) \
    $(wildcard include/config/NET_TC_SKB_EXT) \
    $(wildcard include/config/MAX_SKB_FRAGS) \
    $(wildcard include/config/NET_SOCK_MSG) \
    $(wildcard include/config/SKB_EXTENSIONS) \
    $(wildcard include/config/NET_XGRESS) \
    $(wildcard include/config/WIRELESS) \
    $(wildcard include/config/IPV6_NDISC_NODETYPE) \
    $(wildcard include/config/NETFILTER_XT_TARGET_TRACE) \
    $(wildcard include/config/NET_SWITCHDEV) \
    $(wildcard include/config/NET_REDIRECT) \
    $(wildcard include/config/SKB_DECRYPTED) \
    $(wildcard include/config/NET_SCHED) \
    $(wildcard include/config/NET_RX_BUSY_POLL) \
    $(wildcard include/config/XPS) \
    $(wildcard include/config/NETWORK_SECMARK) \
    $(wildcard include/config/DEBUG_NET) \
    $(wildcard include/config/FAIL_SKB_REALLOC) \
    $(wildcard include/config/NETWORK_PHY_TIMESTAMPING) \
    $(wildcard include/config/MCTP_FLOWS) \
    $(wildcard include/config/INET_PSP) \
  /src/include/net/checksum.h \
  /src/arch/x86/include/asm/checksum.h \
    $(wildcard include/config/GENERIC_CSUM) \
  /src/arch/x86/include/asm/checksum_64.h \
  /src/include/linux/dma-mapping.h \
    $(wildcard include/config/DMA_API_DEBUG) \
    $(wildcard include/config/HAS_DMA) \
    $(wildcard include/config/NEED_DMA_MAP_STATE) \
  /src/include/linux/netdev_features.h \
  /src/include/net/flow_dissector.h \
  /src/include/uapi/linux/if_ether.h \
  /src/include/uapi/linux/pkt_cls.h \
    $(wildcard include/config/NET_CLS_ACT) \
  /src/include/uapi/linux/pkt_sched.h \
  /src/include/uapi/linux/if_packet.h \
  /src/include/linux/page_frag_cache.h \
  /src/include/net/net_debug.h \
  /src/include/net/netmem.h \
  /src/include/linux/seq_file_net.h \

kernel/fork.o: $(deps_kernel/fork.o)

$(deps_kernel/fork.o):

kernel/fork.o: $(wildcard ./tools/objtool/objtool)
