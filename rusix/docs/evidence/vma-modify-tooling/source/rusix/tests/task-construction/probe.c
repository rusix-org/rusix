// SPDX-License-Identifier: GPL-2.0-only
/* Guest-only ordinary userspace task-construction contracts. */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/filter.h>
#include <linux/seccomp.h>
#include <poll.h>
#include <sched.h>
#include <signal.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

extern char **environ;
static volatile unsigned int private_data = 0x1234;
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
	    strcmp(init, "rusix-task-init\n"))
		return -1;
	for (word = strtok_r(command, " \t\n", &save); word;
	     word = strtok_r(NULL, " \t\n", &save))
		if (!strcmp(word, "rusix.task_construction_probe=1"))
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
		if (now < 0 || now - start >= 5000)
			return -1;
		poll(NULL, 0, 5);
	}
}

static int fork_private(void)
{
	volatile unsigned int stack_value = 0x5678;
	pid_t child = fork();
	if (child < 0)
		return 1;
	if (!child) {
		if (stack_value != 0x5678 || private_data != 0x1234)
			_exit(1);
		stack_value = 0xabcd;
		private_data = 0xef01;
		_exit(stack_value == 0xabcd && private_data == 0xef01 ? 37 : 2);
	}
	if (wait_child(child, 37, 2000))
		return 2;
	return stack_value == 0x5678 && private_data == 0x1234 ? 0 : 3;
}

static int exec_fresh(void)
{
	char *const args[] = { (char *)self_path, "--exec-child", "42", NULL };
	pid_t child;
	private_data = 0x8888;
	child = fork();
	if (child < 0)
		return 1;
	if (!child) {
		execve(self_path, args, environ);
		_exit(111);
	}
	return wait_child(child, 42, 2000) ? 2 : 0;
}

static int vfork_exec(void)
{
	char *const args[] = { (char *)self_path, "--exec-child", "43", NULL };
	struct pollfd ready;
	int fds[2], result;
	char byte;
	pid_t child;
	if (pipe2(fds, O_CLOEXEC))
		return 1;
	private_data = 0x8888;
	/* No allocation, logging, shared-data writes or helper calls in this child. */
	child = vfork();
	if (!child) {
		execve(self_path, args, environ);
		_exit(111);
	}
	close(fds[1]);
	if (child < 0) {
		close(fds[0]);
		return 2;
	}
	/* exec closes CLOEXEC descriptors before releasing the vfork parent.
	 * The fresh-image exit code distinguishes successful exec from _exit(111). */
	ready = (struct pollfd){ .fd = fds[0], .events = POLLIN | POLLHUP };
	result = poll(&ready, 1, 0);
	if (result != 1 || !(ready.revents & POLLHUP)) {
		close(fds[0]);
		return 3;
	}
	result = read(fds[0], &byte, 1);
	close(fds[0]);
	if (result != 0)
		return 4;
	return wait_child(child, 43, 2000) ? 5 : 0;
}

static int affinity(void)
{
	cpu_set_t original, chosen, observed;
	pid_t child;
	int cpu, result = 0;
	if (sched_getaffinity(0, sizeof(original), &original))
		return 1;
	CPU_ZERO(&chosen);
	for (cpu = 0; cpu < CPU_SETSIZE; cpu++)
		if (CPU_ISSET(cpu, &original))
			break;
	if (cpu == CPU_SETSIZE)
		return 2;
	CPU_SET(cpu, &chosen);
	if (sched_setaffinity(0, sizeof(chosen), &chosen))
		return 3;
	child = fork();
	if (!child) {
		int ok = !sched_getaffinity(0, sizeof(observed), &observed) &&
			 CPU_EQUAL(&chosen, &observed);
		_exit(ok ? 39 : 1);
	}
	if (child < 0 || wait_child(child, 39, 2000))
		result = 4;
	if (sched_setaffinity(0, sizeof(original), &original) ||
	    sched_getaffinity(0, sizeof(observed), &observed) ||
	    !CPU_EQUAL(&original, &observed))
		result = 5;
	return result;
}

static int filtered_getppid(void)
{
	long result;
	errno = 0;
	result = syscall(SYS_getppid);
	return result == -1 && errno == EACCES &&
		prctl(PR_GET_SECCOMP, 0, 0, 0, 0) == SECCOMP_MODE_FILTER;
}

static int seccomp_inheritance(void)
{
	struct sock_filter insns[] = {
		BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, nr)),
		BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, SYS_getppid, 0, 1),
		BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EACCES),
		BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
	};
	struct sock_fprog filter = { .len = sizeof(insns) / sizeof(insns[0]), .filter = insns };
	pid_t child;
	/* Only this isolated case worker acquires the irreversible filter. */
	if (prctl(PR_GET_SECCOMP, 0, 0, 0, 0) != SECCOMP_MODE_DISABLED ||
	    prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) ||
	    prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &filter))
		return 1;
	if (!filtered_getppid())
		return 2;
	child = fork();
	if (child < 0)
		return 3;
	if (!child)
		_exit(filtered_getppid() ? 41 : 1);
	return wait_child(child, 41, 2000) ? 4 : 0;
}

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
		{ "fork_private_and_wait", fork_private },
		{ "exec_fresh_image", exec_fresh },
		{ "vfork_exec_handoff", vfork_exec },
		{ "affinity_inherited", affinity },
		{ "seccomp_filter_inherited", seccomp_inheritance },
	};
	size_t i;
	if (guest_guard())
		return 125;
	if (argc == 3 && !strcmp(argv[1], "--exec-child")) {
		if (private_data != 0x1234)
			return 112;
		if (!strcmp(argv[2], "42"))
			return 42;
		if (!strcmp(argv[2], "43"))
			return 43;
		return 113;
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
		/* Child also sets its group before creating any descendants. */
		if (setpgid(worker, worker) && errno != EACCES && errno != ESRCH) {
			kill(worker, SIGKILL);
			wait_child(worker, 0, 1000);
			return 1;
		}
		status = observe_worker(worker);
		cleanup = cleanup_group(worker);
		if (status || cleanup) {
			fprintf(stderr, "RUSIX_TASK_CONSTRUCTION_FAIL %s\n", cases[i].name);
			return 1;
		}
		printf("RUSIX_TASK_CONSTRUCTION_CASE %s PASS\n", cases[i].name);
		fflush(stdout);
	}
	puts("RUSIX_TASK_CONSTRUCTION_PASS");
	return 0;
}
