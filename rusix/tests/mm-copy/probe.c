// SPDX-License-Identifier: GPL-2.0-only
/* Guest-only MM-copy consumers; never execute on the host. */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <sched.h>
#include <stdatomic.h>
#include <sys/syscall.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/prctl.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>


static volatile unsigned int fresh_image = 0x1234;

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
	    strcmp(init, "rusix-copy-init\n"))
		return -1;
	for (word = strtok_r(command, " \t\n", &save); word;
	     word = strtok_r(NULL, " \t\n", &save))
		if (!strcmp(word, "rusix.mm_copy_probe=1"))
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

/* CLONE_VM without CLONE_THREAD shares TLS storage, but not libc's threading
 * bookkeeping. Therefore the child never calls libc, touches errno, allocates,
 * or returns through C runtime cleanup. glibc clone supplies a new-stack entry;
 * its callback uses only lock-free atomics and raw Linux x86_64 syscalls. */
#if !defined(__x86_64__)
#error This guarded guest fixture requires the declared x86_64 ABI
#endif
_Static_assert(ATOMIC_INT_LOCK_FREE == 2, "shared state must be lock-free");
struct shared_page {
	_Atomic unsigned int state;
	unsigned char data[64];
};
struct clone_args {
	struct shared_page *page;
	int ready_fd;
	int go_fd;
	int exec_image;
};

static inline long raw3(long nr, long a, long b, long c)
{
	long result;
	__asm__ volatile("syscall" : "=a"(result)
		: "a"(nr), "D"(a), "S"(b), "d"(c) : "rcx", "r11", "memory");
	return result;
}

__attribute__((noreturn)) static void raw_exit(int code)
{
	raw3(SYS_exit, code, 0, 0);
	__builtin_unreachable();
}

static int shared_child(void *opaque)
{
	struct clone_args *args = opaque;
	struct shared_page *page = args->page;
	char token = 'R';
	char *const argv[] = { "/proc/self/exe", "--fresh-exec", NULL };
	char *const env[] = { "LC_ALL=C", NULL };

	if (atomic_load_explicit(&page->state, memory_order_acquire) != 0 ||
	    page->data[0] != 0x12 || page->data[63] != 0x34)
		raw_exit(11);
	page->data[0] = 0x56;
	page->data[63] = 0x78;
	atomic_store_explicit(&page->state, 1, memory_order_release);
	if (raw3(SYS_write, args->ready_fd, (long)&token, 1) != 1 ||
	    raw3(SYS_read, args->go_fd, (long)&token, 1) != 1 || token != 'G')
		raw_exit(12);
	if (atomic_load_explicit(&page->state, memory_order_acquire) != 2 ||
	    page->data[1] != 0x9a)
		raw_exit(13);
	page->data[63] = 0xbc;
	fresh_image = 0x9999;
	atomic_store_explicit(&page->state, 3, memory_order_release);
	if (args->exec_image) {
		raw3(SYS_execve, (long)argv[0], (long)argv, (long)env);
		raw_exit(14);
	}
	raw_exit(37);
}

/* Kill only an unreaped child. Returning from this function means its stack and
 * argument storage are no longer in use. A kernel-stuck child forces immediate
 * worker exit without unmapping shared storage; supervisor/VM contain it. */
static void abort_shared_child(pid_t child)
{
	long long start = milliseconds(), now;
	int status;
	pid_t got;

	if (kill(child, SIGKILL) && errno != ESRCH)
		_exit(118);
	for (;;) {
		got = waitpid(child, &status, WNOHANG);
		if (got == child)
			return;
		if (got < 0 && errno != EINTR)
			_exit(118);
		now = milliseconds();
		if (start < 0 || now < 0 || now - start >= 1000)
			_exit(119);
		poll(NULL, 0, 5);
	}
}

/* Unlike wait_child, retain knowledge of whether a wrong-status child was
 * already reaped. Never send a signal to a PID that has become reusable. */
static int join_shared_child(pid_t child, int expected, int *reaped)
{
	long long start = milliseconds(), now;
	int status;
	pid_t got;

	for (;;) {
		got = waitpid(child, &status, WNOHANG);
		if (got == child) {
			*reaped = 1;
			return WIFEXITED(status) && WEXITSTATUS(status) == expected ? 0 : -1;
		}
		if (got < 0 && errno != EINTR)
			return -1;
		now = milliseconds();
		if (start < 0 || now < 0 || now - start >= 3000)
			return -1;
		poll(NULL, 0, 5);
	}
}

static int shared_clone(int exec_image)
{
	const size_t stack_size = 65536, guard = 4096;
	struct shared_page *page;
	void *stack;
	struct clone_args args;
	int ready[2] = { -1, -1 }, go[2] = { -1, -1 };
	int result = 1, reaped = 0;
	pid_t child = -1;
	struct pollfd event;
	char token;

	if (sysconf(_SC_PAGESIZE) != 4096)
		return 1;
	page = mmap(NULL, guard, PROT_READ | PROT_WRITE,
		    MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
	if (page == MAP_FAILED)
		return 1;
	stack = mmap(NULL, stack_size + 2 * guard, PROT_NONE,
		     MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
	if (stack == MAP_FAILED) {
		munmap(page, guard);
		return 1;
	}
	if (mprotect((char *)stack + guard, stack_size, PROT_READ | PROT_WRITE) ||
	    pipe2(ready, O_CLOEXEC) || pipe2(go, O_CLOEXEC))
		goto out;
	atomic_init(&page->state, 0);
	page->data[0] = 0x12;
	page->data[63] = 0x34;
	args = (struct clone_args) { page, ready[1], go[0], exec_image };
	/* Separate process/thread group and descriptor table; only MM is shared.
	 * No CLONE_VFORK: parent and child must exchange data before either exits. */
	child = clone(shared_child, (char *)stack + guard + stack_size,
		      CLONE_VM | SIGCHLD, &args);
	if (child < 0)
		goto out;
	close(ready[1]);
	ready[1] = -1;
	close(go[0]);
	go[0] = -1;
	event = (struct pollfd) { .fd = ready[0], .events = POLLIN };
	if (poll(&event, 1, 2000) != 1 || read(ready[0], &token, 1) != 1 || token != 'R')
		goto out;
	if (atomic_load_explicit(&page->state, memory_order_acquire) != 1 ||
	    page->data[0] != 0x56 || page->data[63] != 0x78)
		goto out;
	page->data[1] = 0x9a;
	atomic_store_explicit(&page->state, 2, memory_order_release);
	if (write(go[1], "G", 1) != 1 ||
	    join_shared_child(child, exec_image ? 42 : 37, &reaped))
		goto out;
	if (atomic_load_explicit(&page->state, memory_order_acquire) != 3 ||
	    page->data[0] != 0x56 || page->data[1] != 0x9a || page->data[63] != 0xbc ||
	    fresh_image != 0x9999)
		goto out;
	/* Child has exited or detached via exec then exited. Parent's old MM is
	 * still writable, including both the payload and its retained stack VMA. */
	page->data[0] = 0xde;
	page->data[63] = 0xf0;
	((volatile char *)stack)[guard] = 7;
	result = page->data[0] != 0xde || page->data[63] != 0xf0;
out:
	if (child > 0 && !reaped)
		abort_shared_child(child);
	for (int i = 0; i < 2; i++) {
		if (ready[i] >= 0)
			close(ready[i]);
		if (go[i] >= 0)
			close(go[i]);
	}
	if (munmap(stack, stack_size + 2 * guard) || munmap(page, guard))
		result = 1;
	return result;
}
static int shared_exit(void) { return shared_clone(0); }
static int shared_exec(void) { return shared_clone(1); }

int main(int argc, char **argv)
{
	static const struct { const char *name; int (*run)(void); } cases[] = {
		{ "shared_clone_write_and_exit", shared_exit },
		{ "shared_clone_exec_detaches_mm", shared_exec },
		{ "private_fork_cow", private_cow },
	};
	size_t i;

	if (guest_guard())
		return 125;
	if (argc == 2 && !strcmp(argv[1], "--fresh-exec"))
		return fresh_image == 0x1234 ? 42 : 112;
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
			fprintf(stderr, "RUSIX_MM_COPY_FAIL %s\n", cases[i].name);
			return 1;
		}
		printf("RUSIX_MM_COPY_CASE %s PASS\n", cases[i].name);
		fflush(stdout);
	}
	puts("RUSIX_MM_COPY_PASS");
	return 0;
}
