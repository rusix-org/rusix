# SPDX-License-Identifier: GPL-2.0-only
# Build the local base using the pinned ci/Dockerfile and package lock first.
# Record its inspected image identity for each build; IDs can differ across
# builders even when the pinned inputs and package inventory match.
ARG TOOLCHAIN_IMAGE=rusix-toolchain:trixie-20261025
FROM ${TOOLCHAIN_IMAGE}
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install --yes --no-install-recommends e2fsprogs \
    && dpkg-query -W -f='${Package}\t${Version}\t${Architecture}\n' \
       | sort > /opt/rusix/ext4-packages.lock \
    && rm -rf /var/lib/apt/lists/*
COPY ext4-packages.lock /opt/rusix/expected-ext4-packages.lock
RUN cmp /opt/rusix/ext4-packages.lock /opt/rusix/expected-ext4-packages.lock
# Do not execute the guest fixture while constructing the container.
