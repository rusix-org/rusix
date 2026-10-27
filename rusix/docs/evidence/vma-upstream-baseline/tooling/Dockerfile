# Rebuild recipe; installation is executed in a resource-bounded container.
ARG TOOLCHAIN_IMAGE
FROM ${TOOLCHAIN_IMAGE}
COPY install.sh /opt/rusix/install-vma-tools.sh
RUN bash /opt/rusix/install-vma-tools.sh
CMD ["bash"]
