// SPDX-License-Identifier: GPL-2.0-only
/* Guest-only raw syscall worker. No libc allocation in the armed interval. */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static int read_file(const char *path, char *buf, size_t len)
{
	int fd = open(path, O_RDONLY | O_CLOEXEC);
	ssize_t n;
	if (fd < 0) return -1;
	n = read(fd, buf, len - 1); close(fd);
	if (n < 0 || (size_t)n == len - 1) return -1;
	buf[n] = 0; return 0;
}
static int guard(void)
{
	char buf[8192], name[32], *word, *save;
	int count = 0;
	if (read_file("/proc/1/comm", name, sizeof(name)) ||
	    strcmp(name, "rusix-fault-init\n") ||
	    read_file("/proc/cmdline", buf, sizeof(buf))) return -1;
	for (word = strtok_r(buf, " \n\t", &save); word; word = strtok_r(NULL, " \n\t", &save))
		if (!strcmp(word, "rusix.task_faults=1")) count++;
	return count == 1 ? 0 : -1;
}
static long long now_ms(void)
{
	struct timespec t;
	if (clock_gettime(CLOCK_MONOTONIC, &t)) return -1;
	return (long long)t.tv_sec * 1000 + t.tv_nsec / 1000000;
}
static int reap(pid_t pid)
{
	long long start = now_ms(), now;
	int status;
	if (start < 0) return -1;
	for (;;) {
		pid_t got = waitpid(pid, &status, WNOHANG);
		if (got == pid) return WIFEXITED(status) && WEXITSTATUS(status) == 23 ? 0 : -1;
		if (got < 0 && errno != EINTR) return -1;
		now = now_ms(); if (now < 0 || now - start >= 2000) return -1;
		poll(NULL, 0, 5);
	}
}
int main(int argc, char **argv)
{
	char path[128], armed[16], remaining[32], go, *end;
	int fd, marker, saved_errno, child_status = 0, retry_status;
	long nth, child, retry, rest;
	ssize_t n;
	size_t armed_len;
	if (guard() || argc != 2 || setpgid(0, 0)) return 125;
	nth = strtol(argv[1], &end, 10);
	if (*end || nth < 0 || nth > 16) return 125;
	snprintf(path, sizeof(path), "/proc/self/task/%ld/fail-nth", syscall(SYS_gettid));
	fd = open(path, O_RDWR | O_CLOEXEC);
	if (fd < 0) return 1;
	marker = open("/sys/kernel/tracing/instances/rusix_task_faults/trace_marker", O_WRONLY | O_CLOEXEC);
	if (marker < 0) return 1;
	snprintf(armed, sizeof(armed), "%ld", nth);
	armed_len = strlen(armed);
	for (size_t i = 0; i < sizeof(remaining); i++)
		((volatile char *)remaining)[i] = 0;
	/* All formatting/opening occurs before arming. Controller configures trace
	 * for this TID before sending exactly one G byte. */
	printf("READY %ld\n", syscall(SYS_gettid)); fflush(stdout);
	if (read(STDIN_FILENO, &go, 1) != 1 || go != 'G') return 2;
	if (write(marker, "ARM\n", 4) != 4) return 3;
	if (syscall(SYS_pwrite64, fd, armed, armed_len, 0L) != (ssize_t)armed_len) return 3;
	errno = 0;
	child = syscall(SYS_fork);
	saved_errno = errno;
	if (child == 0) _exit(23);
	n = syscall(SYS_pread64, fd, remaining, sizeof(remaining) - 1, 0L);
	/* Always disarm before parsing, retry, report or cleanup. */
	if (syscall(SYS_pwrite64, fd, "0", 1UL, 0L) != 1) return 4;
	close(fd);
	if (write(marker, "DISARM\n", 7) != 7) return 4;
	close(marker);
	if (n <= 0) return 5;
	remaining[n] = 0; errno = 0;
	rest = strtol(remaining, &end, 10);
	if (errno || (*end && *end != '\n') || rest < 0 || rest > nth) return 6;
	if (child > 0) child_status = reap(child);
	retry = syscall(SYS_fork);
	if (retry == 0) _exit(23);
	retry_status = retry > 0 ? reap(retry) : -1;
	printf("RESULT pid=%ld nth=%ld ret=%ld errno=%d remaining=%ld child_status=%d retry_status=%d\n",
	       syscall(SYS_gettid), nth, child, saved_errno, rest, child_status, retry_status);
	fflush(stdout);
	/* Keep PID/PGID reserved until supervisor finishes capture or kills group. */
	if (read(STDIN_FILENO, &go, 1) != 1 || go != 'A') return 8;
	return child_status || retry_status ? 7 : 0;
}
