savedcmd_rust/bindings/builtin_init_generated.rs := bindgen /src/rust/bindings/builtin_init_helper.h --rust-target 1.68 --use-core --with-derive-default --ctypes-prefix ffi --no-layout-tests --no-debug '.*' --allowlist-type '^obs_kernel_param$$' --allowlist-function '^$$' --allowlist-var '^$$' -o rust/bindings/builtin_init_generated.rs -- -Wp,-MMD,rust/bindings/.builtin_init_generated.rs.d -nostdinc -I/src/arch/x86/include -I./arch/x86/include/generated -I/src/include -I./include -I/src/arch/x86/include/uapi -I./arch/x86/include/generated/uapi -I/src/include/uapi -I./include/generated/uapi -include /src/include/linux/compiler-version.h -include /src/include/linux/kconfig.h -include /src/include/linux/compiler_types.h -D__KERNEL__ --target=x86_64-linux-gnu -fintegrated-as -Werror=unknown-warning-option -Werror=ignored-optimization-argument -Werror=option-ignored -Werror=unused-command-line-argument -fmacro-prefix-map=/src/= -std=gnu11 -fshort-wchar -funsigned-char -fno-common -fno-PIE -fno-strict-aliasing -mno-sse -mno-mmx -mno-sse2 -mno-3dnow -mno-avx -mno-sse4a -fcf-protection=none -m64 -falign-loops=1 -mno-80387 -mno-fp-ret-in-387 -mstack-alignment=8 -mskip-rax-setup -march=x86-64 -mtune=generic -mno-red-zone -mcmodel=kernel -Wno-sign-compare -fno-asynchronous-unwind-tables -fno-delete-null-pointer-checks -O2 -fno-stack-protector -fomit-frame-pointer -ftrivial-auto-var-init=zero -fno-stack-clash-protection -falign-functions=16 -fstrict-flex-arrays=3 -fno-strict-overflow -fno-stack-check -fno-builtin-wcslen -Wall -Wextra -Wundef -Werror=implicit-function-declaration -Werror=implicit-int -Werror=return-type -Werror=strict-prototypes -Wno-format-security -Wno-trigraphs -Wno-frame-address -Wno-address-of-packed-member -Wmissing-declarations -Wmissing-prototypes -Wframe-larger-than=2048 -Wno-gnu -Wno-format-overflow-non-kprintf -Wno-format-truncation-non-kprintf -Wno-pointer-sign -Wcast-function-type -Wimplicit-fallthrough -Werror=date-time -Werror=incompatible-pointer-types -Wenum-conversion -Wunused -Wno-unused-but-set-variable -Wno-unused-const-variable -Wno-format-overflow -Wno-override-init -Wno-pointer-to-enum-cast -Wno-tautological-constant-out-of-range-compare -Wno-unaligned-access -Wno-enum-compare-conditional -Wno-missing-field-initializers -Wno-type-limits -Wno-shift-negative-value -Wno-enum-enum-conversion -Wno-sign-compare -Wno-unused-parameter -I/src/rust -Irust    -DKBUILD_MODFILE='"rust/builtin_init_generated"' -DKBUILD_BASENAME='"builtin_init_generated"' -DKBUILD_MODNAME='"builtin_init_generated"' -D__KBUILD_MODNAME=kmod_builtin_init_generated -fno-builtin -D__BINDGEN__ -UMODULE

source_rust/bindings/builtin_init_generated.rs := /src/rust/bindings/builtin_init_helper.h

deps_rust/bindings/builtin_init_generated.rs := \
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
  /src/include/linux/init.h \
    $(wildcard include/config/MEMORY_HOTPLUG) \
    $(wildcard include/config/HAVE_ARCH_PREL32_RELOCATIONS) \
  /src/include/linux/build_bug.h \
  /src/include/linux/compiler.h \
    $(wildcard include/config/TRACE_BRANCH_PROFILING) \
    $(wildcard include/config/PROFILE_ALL_BRANCHES) \
    $(wildcard include/config/OBJTOOL) \
    $(wildcard include/config/64BIT) \
  arch/x86/include/generated/asm/rwonce.h \
  /src/include/asm-generic/rwonce.h \
  /src/include/linux/kasan-checks.h \
    $(wildcard include/config/KASAN_GENERIC) \
    $(wildcard include/config/KASAN_SW_TAGS) \
  /src/include/linux/types.h \
    $(wildcard include/config/HAVE_UID16) \
    $(wildcard include/config/UID16) \
    $(wildcard include/config/ARCH_DMA_ADDR_T_64BIT) \
    $(wildcard include/config/PHYS_ADDR_T_64BIT) \
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
  /src/include/linux/kcsan-checks.h \
    $(wildcard include/config/KCSAN_WEAK_MEMORY) \
    $(wildcard include/config/KCSAN_IGNORE_ATOMICS) \
  /src/include/linux/stringify.h \

rust/bindings/builtin_init_generated.rs: $(deps_rust/bindings/builtin_init_generated.rs)

$(deps_rust/bindings/builtin_init_generated.rs):
