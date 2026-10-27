# SPDX-License-Identifier: GPL-2.0-only
# Official Debian amd64 image, published 2026-10-20. No floating base or APT suite.
FROM debian:trixie-slim@sha256:4876fdea29cac1a33a3195f1eb1952feb1fca7dd6dd00be3e2f1879cf20d34d2

# The dated signed archive fixes all transitive package versions, including QEMU
# and the static C runtime used by the BRD probe. HTTP transport is authenticated
# by Debian's signed Release metadata and package hashes; no trusted=yes bypass.
RUN rm /etc/apt/sources.list.d/debian.sources \
    && printf '%s\n' \
      'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/20261025T000000Z/ trixie main' \
      'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/20261025T000000Z/ trixie-security main' \
      > /etc/apt/sources.list \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install --yes --no-install-recommends \
      bc bindgen bison ca-certificates cargo clang-19 cpio flex gcc git \
      libc6-dev libclang-19-dev libelf-dev libssl-dev lld-19 llvm-19 make \
      pahole perl pkg-config python3 qemu-system-x86 rust-src rustc rustfmt \
      util-linux xz-utils \
    && mkdir -p /opt/rusix \
    && dpkg-query -W -f='${Package}\t${Version}\t${Architecture}\n' \
      | sort > /opt/rusix/packages.lock \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/usr/lib/llvm-19/bin:${PATH}" \
    LIBCLANG_PATH="/usr/lib/llvm-19/lib" \
    LC_ALL="C" \
    PYTHONDONTWRITEBYTECODE="1" \
    GIT_OPTIONAL_LOCKS="0"

RUN rustc --version | grep '^rustc 1\.85\.1 ' \
    && clang --version | grep 'clang version 19\.1\.7' \
    && bindgen --version | grep '^bindgen 0\.71\.1$' \
    && test -f /usr/lib/rustlib/src/rust/library/core/src/lib.rs \
    && { rustc --version --verbose; clang --version; ld.lld --version; \
         bindgen --version; gcc --version; qemu-system-x86_64 --version; } \
       > /opt/rusix/toolchain.log

COPY packages.lock /opt/rusix/expected-packages.lock
RUN cmp /opt/rusix/expected-packages.lock /opt/rusix/packages.lock

WORKDIR /src
CMD ["bash"]
