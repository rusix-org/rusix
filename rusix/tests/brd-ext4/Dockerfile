# SPDX-License-Identifier: GPL-2.0-only
# Exact locally built toolchain image. It carries dated, signed snapshot sources.
# Before building, verify the local base image ID is
# sha256:0e0cfd724bde5c2a81cee61210c2a14a66ea72f679e1308125825e0463c67937.
# The tag is a local reference; record the inspected base ID with build evidence.
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
