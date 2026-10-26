// SPDX-License-Identifier: GPL-2.0-only
/* Guest-only mm constructor consumers; never execute on the host. */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/prctl.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

/* Stable pinned Linux UAPI, also when the fixture libc headers are older. */
#ifndef PR_SET_MDWE
#define PR_SET_MDWE 65
#define PR_GET_MDWE 66
#endif
#ifndef PR_MDWE_REFUSE_EXEC_GAIN
#define PR_MDWE_REFUSE_EXEC_GAIN (1UL << 0)
#define PR_MDWE_NO_INHERIT (1UL << 1)
#endif
extern char **environ;
static volatile unsigned int fresh_image = 0x1234;
static const char *self_path = "/proc/self/exe";

static long long milliseconds(void)
{
	struct timespec now;
	if (clock_gettime(CLOCK_MONOTONIC, &now))
		return -1;
	return (long long)now.tv_sec * 1000 + now.tv_nsec / 1000000;
}

static int read_text(const char *path, char *buf, size_t size)
{
	int fd = open(path, O_RDONLY | O_CLOEXEC);
	ssize_t n;
	if (fd < 0)
		return -1;
	n = read(fd, buf, size - 1);
	close(fd);
	if (n < 0 || (size_t)n == size - 1)
		return -1;
	buf[n] = 0;
	return 0;
}

static int guest_guard(void)
{
	char command[8192], init[64], *word, *save;
	int found = 0;
	if (read_text("/proc/cmdline", command, sizeof(command)) ||
	    read_text("/proc/1/comm", init, sizeof(init)) ||
	    strcmp(init, "rusix-mm-init\n"))
		return -1;
	for (word = strtok_r(command, " \t\n", &save); word;
	     word = strtok_r(NULL, " \t\n", &save))
		if (!strcmp(word, "rusix.mm_construction_probe=1"))
			found++;
	return found == 1 ? 0 : -1;
}

/* Polling only bounds supervision; elapsed time never proves a kernel behavior. */
static int wait_child(pid_t child, int code, int timeout_ms)
{
	long long start = milliseconds(), now;
	int status;
	pid_t got;
	if (start < 0)
		return -1;
	for (;;) {
		got = waitpid(child, &status, WNOHANG);
		if (got == child)
			return WIFEXITED(status) && WEXITSTATUS(status) == code ? 0 : -1;
		if (got < 0 && errno != EINTR)
			return -1;
		now = milliseconds();
		if (now < 0 || now - start >= timeout_ms)
			return -1;
		poll(NULL, 0, 5);
	}
}

/* Leave the worker zombie unreaped until group cleanup: its PID/PGID cannot
 * be recycled between observation and kill(-group). */
static int observe_worker(pid_t worker)
{
	long long start = milliseconds(), now;
	siginfo_t info;
	if (start < 0)
		return -1;
	for (;;) {
		memset(&info, 0, sizeof(info));
		if (waitid(P_PID, worker, &info, WEXITED | WNOHANG | WNOWAIT)) {
			if (errno != EINTR)
				return -1;
		} else if (info.si_pid == worker) {
			return info.si_code == CLD_EXITED && info.si_status == 0 ? 0 : -1;
		}
		now = milliseconds();
		if (now < 0 || now - start >= 10000)
			return -1;
		poll(NULL, 0, 5);
	}
}

static unsigned char *mapping(size_t *size)
{
	long page = sysconf(_SC_PAGESIZE);
	if (page != 4096)
		return MAP_FAILED; /* Declared x86_64 profile, never skip an unsupported ABI. */
	*size = (size_t)page * 3;
	return mmap(NULL, *size, PROT_READ | PROT_WRITE,
		    MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
}

static int private_cow(void)
{
	size_t size, i;
	unsigned char *p = mapping(&size);
	pid_t child;
	int result = 0;
	if (p == MAP_FAILED)
		return 1;
	for (i = 0; i < size; i++)
		p[i] = (unsigned char)(i * 17 + 3);
	child = fork();
	if (!child) {
		for (i = 0; i < size; i++) {
			if (p[i] != (unsigned char)(i * 17 + 3))
				_exit(1);
			p[i] ^= 0xff;
		}
		for (i = 0; i < size; i++)
			if (p[i] != (unsigned char)((i * 17 + 3) ^ 0xff))
				_exit(2);
		_exit(munmap(p, size) ? 3 : 37);
	}
	if (child < 0 || wait_child(child, 37, 2000))
		result = 2;
	for (i = 0; i < size; i++)
		if (p[i] != (unsigned char)(i * 17 + 3))
			result = 3;
	if (munmap(p, size))
		result = 4;
	return result;
}

static int child_mapping_lifetime(void)
{
	size_t size;
	unsigned char *p = mapping(&size);
	int fds[2], result = 0;
	pid_t child;
	if (p == MAP_FAILED)
		return 1;
	p[0] = 0x45;
	p[size - 1] = 0xab;
	if (pipe2(fds, O_CLOEXEC)) {
		munmap(p, size);
		return 2;
	}
	child = fork();
	if (!child) {
		struct pollfd ready = { .fd = fds[0], .events = POLLIN };
		char token;
		close(fds[1]);
		if (poll(&ready, 1, 2000) != 1 || read(fds[0], &token, 1) != 1 || token != 'U')
			_exit(1);
		close(fds[0]);
		if (p[0] != 0x45 || p[size - 1] != 0xab)
			_exit(2);
		p[0] = 0x21;
		p[size - 1] = 0xfe;
		if (p[0] != 0x21 || p[size - 1] != 0xfe)
			_exit(3);
		_exit(munmap(p, size) ? 4 : 38);
	}
	close(fds[0]);
	if (munmap(p, size))
		result = 3;
	if (child < 0 || result || write(fds[1], "U", 1) != 1)
		result = 4;
	close(fds[1]);
	if (child > 0 && wait_child(child, 38, 3000))
		result = 5;
	return result;
}

static int repeated_fork_exec(void)
{
	size_t size;
	unsigned char *p = mapping(&size);
	char *const args[] = { (char *)self_path, "--fresh-exec", NULL };
	int i, result = 0;
	if (p == MAP_FAILED)
		return 1;
	p[0] = 0x42;
	p[size - 1] = 0x91;
	for (i = 0; i < 32; i++) {
		pid_t child = fork();
		if (!child) {
			p[0] = 0x13;
			fresh_image = 0x9999;
			execve(self_path, args, environ);
			_exit(111);
		}
		if (child < 0 || wait_child(child, 42, 2000) ||
		    p[0] != 0x42 || p[size - 1] != 0x91) {
			result = 2;
			break;
		}
	}
	if (munmap(p, size))
		result = 3;
	return result;
}

static int mdwe_state(unsigned long expected)
{
	void *p;
	int rc, saved, result;
	if (prctl(PR_GET_MDWE, 0UL, 0UL, 0UL, 0UL) != (int)expected)
		return 1;
	p = mmap(NULL, 4096, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
	if (p == MAP_FAILED)
		return 2;
	/* No generated code is executed: the mprotect result is the observable ABI. */
	errno = 0;
	rc = mprotect(p, 4096, PROT_READ | PROT_EXEC);
	saved = errno;
	result = expected ? !(rc == -1 && saved == EACCES) : rc != 0;
	if (munmap(p, 4096))
		result = 1;
	return result;
}

static int mdwe(unsigned long flags)
{
	unsigned long expected = flags & PR_MDWE_NO_INHERIT ? 0 : PR_MDWE_REFUSE_EXEC_GAIN;
	char *const args[] = { (char *)self_path, "--mdwe-exec", expected ? "1" : "0", NULL };
	pid_t child;
	if (prctl(PR_GET_MDWE, 0UL, 0UL, 0UL, 0UL) != 0)
		return 1;
	errno = 0;
	if (prctl(PR_SET_MDWE, PR_MDWE_NO_INHERIT, 0UL, 0UL, 0UL) != -1 || errno != EINVAL)
		return 2;
	if (prctl(PR_SET_MDWE, flags, 0UL, 0UL, 0UL) || mdwe_state(flags))
		return 3;
	errno = 0;
	if (prctl(PR_SET_MDWE, 0UL, 0UL, 0UL, 0UL) != -1 || errno != EPERM)
		return 4;
	child = fork();
	if (!child) {
		if (mdwe_state(expected))
			_exit(1);
		fresh_image = 0x9999;
		execve(self_path, args, environ);
		_exit(111);
	}
	if (child < 0 || wait_child(child, 0, 2000) || mdwe_state(flags))
		return 5;
	/* Direct exec from the still-flagged parent tests fresh mm initialization;
	 * NO_INHERIT must clear here even though no preceding fork cleared it. */
	fresh_image = 0x9999;
	execve(self_path, args, environ);
	return 6;
}
static int mdwe_inherited(void) { return mdwe(PR_MDWE_REFUSE_EXEC_GAIN); }
static int mdwe_no_inherit(void) { return mdwe(PR_MDWE_REFUSE_EXEC_GAIN | PR_MDWE_NO_INHERIT); }

/* Subreaper owns orphaned descendants; kill only the per-case process group.
 * A kernel-stuck task can defeat kill/reap: report failure, external VM watchdog
 * remains final containment. Never block the supervisor in an unbounded wait. */
static int cleanup_group(pid_t group)
{
	long long start = milliseconds(), now;
	int status;
	pid_t got;
	if (kill(-group, SIGKILL) && errno != ESRCH)
		return -1;
	if (start < 0)
		return -1;
	for (;;) {
		got = waitpid(-group, &status, WNOHANG);
		if (got < 0 && errno == ECHILD)
			return 0;
		if (got < 0 && errno != EINTR)
			return -1;
		now = milliseconds();
		if (now < 0 || now - start >= 1000)
			return -1;
		if (!got)
			poll(NULL, 0, 5);
	}
}

int main(int argc, char **argv)
{
	static const struct { const char *name; int (*run)(void); } cases[] = {
		{ "anonymous_private_fork_cow", private_cow },
		{ "child_mapping_survives_parent_unmap", child_mapping_lifetime },
		{ "repeated_fork_exec_reap", repeated_fork_exec },
		{ "mdwe_inherited_fork_exec", mdwe_inherited },
		{ "mdwe_no_inherit_fork_exec", mdwe_no_inherit },
	};
	size_t i;
	if (guest_guard())
		return 125;
	if (argc == 2 && !strcmp(argv[1], "--fresh-exec"))
		return fresh_image == 0x1234 ? 42 : 112;
	if (argc == 3 && !strcmp(argv[1], "--mdwe-exec")) {
		if (fresh_image != 0x1234 || (strcmp(argv[2], "0") && strcmp(argv[2], "1")))
			return 113;
		return mdwe_state(!strcmp(argv[2], "1") ? 1 : 0);
	}
	if (argc != 1 || getppid() != 1 || prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0))
		return 125;
	for (i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
		pid_t worker = fork();
		int status, cleanup;
		if (worker < 0)
			return 1;
		if (!worker) {
			if (setpgid(0, 0))
				_exit(120);
			_exit(cases[i].run());
		}
		if (setpgid(worker, worker) && errno != EACCES && errno != ESRCH) {
			kill(worker, SIGKILL);
			wait_child(worker, 0, 1000);
			return 1;
		}
		status = observe_worker(worker);
		cleanup = cleanup_group(worker);
		if (status || cleanup) {
			fprintf(stderr, "RUSIX_MM_CONSTRUCTION_FAIL %s\n", cases[i].name);
			return 1;
		}
		printf("RUSIX_MM_CONSTRUCTION_CASE %s PASS\n", cases[i].name);
		fflush(stdout);
	}
	puts("RUSIX_MM_CONSTRUCTION_PASS");
	return 0;
}
