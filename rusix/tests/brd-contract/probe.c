// SPDX-License-Identifier: GPL-2.0-only
/* VM-only BRD userspace contract probe. Never execute on the host. */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <linux/fs.h>
#include <pthread.h>
#include <sched.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mount.h>
#include <sys/reboot.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <unistd.h>

#define PAGE_BYTES 4096U
#define SECTOR_BYTES 512U
#define CAPACITY (64ULL * 1024 * 1024)
#define DISCARD_BASE (1ULL * 1024 * 1024)
#define CONCURRENT_BASE (16ULL * 1024 * 1024)
#define ROUNDS 64U

static const char *current_case = "setup";
static bool vm_authorized;
static int disk_fd;

static _Noreturn void finish(void)
{
	fflush(NULL);
	if (vm_authorized) {
		reboot(RB_AUTOBOOT);
		/* Returning from PID 1 could obscure a failed reboot. */
		printf("RUSIX_BRD_FAIL reboot errno=%d\n", errno);
		fflush(NULL);
		for (;;)
			pause();
	}
	_Exit(EXIT_FAILURE);
}

static _Noreturn void fail(const char *format, ...)
{
	va_list args;

	printf("RUSIX_BRD_FAIL %s ", current_case);
	va_start(args, format);
	vprintf(format, args);
	va_end(args);
	putchar('\n');
	finish();
}

static void pass(void)
{
	printf("RUSIX_BRD_PASS %s\n", current_case);
}

static void *aligned_buffer(size_t size)
{
	void *buffer;
	int error = posix_memalign(&buffer, PAGE_BYTES, size);

	if (error)
		fail("posix_memalign error=%d", error);
	return buffer;
}

static void read_exact(void *buffer, size_t size, uint64_t offset)
{
	ssize_t result;

	do {
		result = pread(disk_fd, buffer, size, (off_t)offset);
	} while (result < 0 && errno == EINTR);
	if (result != (ssize_t)size)
		fail("pread offset=%" PRIu64 " size=%zu result=%zd errno=%d",
		     offset, size, result, errno);
}

static void write_exact(const void *buffer, size_t size, uint64_t offset)
{
	ssize_t result;

	do {
		result = pwrite(disk_fd, buffer, size, (off_t)offset);
	} while (result < 0 && errno == EINTR);
	if (result != (ssize_t)size)
		fail("pwrite offset=%" PRIu64 " size=%zu result=%zd errno=%d",
		     offset, size, result, errno);
}

static void discard(uint64_t offset, uint64_t size)
{
	uint64_t range[] = { offset, size };

	if (ioctl(disk_fd, BLKDISCARD, range))
		fail("BLKDISCARD offset=%" PRIu64 " size=%" PRIu64 " errno=%d",
		     offset, size, errno);
}

static uint64_t allocated_pages(void)
{
	FILE *file = fopen("/debug/ramdisk_pages/ram0", "r");
	uint64_t count;
	char trailing;
	int result;

	if (!file)
		fail("open page count errno=%d", errno);
	result = fscanf(file, "%" SCNu64 " %c", &count, &trailing);
	if (fclose(file))
		fail("close page count errno=%d", errno);
	if (result != 1)
		fail("invalid page count");
	return count;
}

static void expect_pages(uint64_t expected)
{
	uint64_t actual = allocated_pages();

	if (actual != expected)
		fail("page count expected=%" PRIu64 " actual=%" PRIu64,
		     expected, actual);
}

static void expect_byte(const unsigned char *data, size_t index,
			unsigned char expected)
{
	if (data[index] != expected)
		fail("byte=%zu expected=%u actual=%u", index, expected, data[index]);
}

static void check_zero_range(unsigned char *buffer, size_t size, uint64_t offset)
{
	memset(buffer, 0xa5, size);
	read_exact(buffer, size, offset);
	for (size_t i = 0; i < size; i++)
		expect_byte(buffer, i, 0);
}

static void authorize_vm(void)
{
	char command[4096], *token, *save;
	FILE *file;
	int console;

	/* These guards prevent routine accidental host execution, not hostile use. */
	if (getpid() != 1) {
		fputs("RUSIX_BRD_FAIL setup requires VM PID 1\n", stderr);
		_Exit(EXIT_FAILURE);
	}
	console = open("/dev/console", O_RDWR);
	if (console < 0)
		fail("console errno=%d", errno);
	for (int fd = 0; fd <= 2; fd++) {
		if (dup2(console, fd) < 0)
			fail("dup2 errno=%d", errno);
	}
	if (console > 2)
		close(console);
	setvbuf(stdout, NULL, _IONBF, 0);
	if (mount("proc", "/proc", "proc", MS_NOSUID | MS_NODEV | MS_NOEXEC, NULL))
		fail("mount proc errno=%d", errno);
	file = fopen("/proc/cmdline", "r");
	if (!file || !fgets(command, sizeof(command), file))
		fail("read cmdline errno=%d", errno);
	if (!strchr(command, '\n') && !feof(file))
		fail("truncated cmdline");
	if (fclose(file))
		fail("close cmdline errno=%d", errno);
	for (token = strtok_r(command, " \t\r\n", &save); token;
	     token = strtok_r(NULL, " \t\r\n", &save)) {
		if (!strcmp(token, "rusix.brd_contract=1"))
			vm_authorized = true;
	}
	if (!vm_authorized)
		fail("missing VM command-line authorization token");
	if (mount("debugfs", "/debug", "debugfs", MS_NOSUID | MS_NODEV | MS_NOEXEC, NULL))
		fail("mount debugfs errno=%d", errno);
}

static void geometry(void)
{
	uint64_t size;
	int logical, physical;
	struct stat info;
	cpu_set_t available;

	current_case = "geometry";
	if (sysconf(_SC_PAGESIZE) != PAGE_BYTES)
		fail("requires 4096-byte pages");
	if (sched_getaffinity(0, sizeof(available), &available) ||
	    !CPU_ISSET(0, &available) || !CPU_ISSET(1, &available))
		fail("requires available CPUs 0 and 1");
	disk_fd = open("/dev/ram0", O_RDWR | O_DIRECT | O_CLOEXEC);
	if (disk_fd < 0)
		fail("open ram0 errno=%d", errno);
	if (fstat(disk_fd, &info) || !S_ISBLK(info.st_mode) ||
	    major(info.st_rdev) != 1 || minor(info.st_rdev) != 0)
		fail("ram0 must be block device 1:0");
	if (ioctl(disk_fd, BLKGETSIZE64, &size) ||
	    ioctl(disk_fd, BLKSSZGET, &logical) ||
	    ioctl(disk_fd, BLKPBSZGET, &physical))
		fail("block-size ioctl errno=%d", errno);
	if (size != CAPACITY || logical != SECTOR_BYTES || physical != PAGE_BYTES)
		fail("size=%" PRIu64 " logical=%d physical=%d", size, logical, physical);
	expect_pages(0);
	pass();
}

static void sparse_read(void)
{
	unsigned char *buffer = aligned_buffer(3 * PAGE_BYTES);

	current_case = "sparse_read";
	check_zero_range(buffer, 3 * PAGE_BYTES, 0);
	check_zero_range(buffer, PAGE_BYTES, CONCURRENT_BASE);
	check_zero_range(buffer, PAGE_BYTES, CAPACITY - PAGE_BYTES);
	expect_pages(0);
	free(buffer);
	pass();
}

static unsigned char crossing_pattern(size_t offset)
{
	return (unsigned char)(1 + ((offset * 37 + offset / SECTOR_BYTES) % 251));
}

static void crossing_write(void)
{
	unsigned char *allocation = aligned_buffer(3 * PAGE_BYTES);
	unsigned char *source = allocation + SECTOR_BYTES;
	unsigned char *readback = aligned_buffer(3 * PAGE_BYTES);
	const size_t length = 2 * PAGE_BYTES, start = PAGE_BYTES - SECTOR_BYTES;

	current_case = "crossing_write";
	/* Buffer offset 512 and disk offset 3584 force different page splits. */
	for (size_t i = 0; i < length; i++)
		source[i] = crossing_pattern(i);
	write_exact(source, length, start);
	read_exact(readback, 3 * PAGE_BYTES, 0);
	for (size_t i = 0; i < 3 * PAGE_BYTES; i++)
		expect_byte(readback, i, i >= start && i < start + length ?
			    crossing_pattern(i - start) : 0);
	expect_pages(3);
	free(readback);
	free(allocation);
	pass();
}

static void discard_edges(void)
{
	unsigned char *buffer = aligned_buffer(4 * PAGE_BYTES);

	current_case = "discard_edges";
	for (size_t i = 0; i < 4 * PAGE_BYTES; i++)
		buffer[i] = (unsigned char)(0x31 + i / PAGE_BYTES);
	write_exact(buffer, 4 * PAGE_BYTES, DISCARD_BASE);
	expect_pages(7);
	/* [base+512, base+12800): both edge pages are only partly covered. */
	for (int repeat = 0; repeat < 2; repeat++) {
		discard(DISCARD_BASE + SECTOR_BYTES, 3 * PAGE_BYTES);
		read_exact(buffer, 4 * PAGE_BYTES, DISCARD_BASE);
		for (size_t i = 0; i < 4 * PAGE_BYTES; i++) {
			size_t page = i / PAGE_BYTES;

			expect_byte(buffer, i, page == 1 || page == 2 ? 0 : 0x31 + page);
		}
		expect_pages(5);
	}
	free(buffer);
	pass();
}

struct writer {
	pthread_barrier_t *barrier;
	unsigned int cpu;
	unsigned char *buffer;
	int error;
};

static int barrier_wait(pthread_barrier_t *barrier)
{
	int result = pthread_barrier_wait(barrier);

	return result == PTHREAD_BARRIER_SERIAL_THREAD ? 0 : result;
}

static unsigned char concurrent_pattern(unsigned int round, unsigned int writer)
{
	return (unsigned char)(1 + round * 2 + writer);
}

static void *concurrent_writer(void *arg)
{
	struct writer *writer = arg;
	cpu_set_t affinity;

	CPU_ZERO(&affinity);
	CPU_SET(writer->cpu, &affinity);
	writer->error = pthread_setaffinity_np(pthread_self(), sizeof(affinity), &affinity);
	for (unsigned int round = 0; round < ROUNDS; round++) {
		ssize_t result;
		int error;

		memset(writer->buffer, concurrent_pattern(round, writer->cpu), SECTOR_BYTES);
		error = barrier_wait(writer->barrier);
		if (error)
			writer->error = error;
		if (!writer->error) {
			do {
				result = pwrite(disk_fd, writer->buffer, SECTOR_BYTES,
					CONCURRENT_BASE + round * PAGE_BYTES +
					writer->cpu * SECTOR_BYTES);
			} while (result < 0 && errno == EINTR);
			if (result != SECTOR_BYTES)
				writer->error = result < 0 ? errno : EIO;
		}
		error = barrier_wait(writer->barrier);
		if (error)
			writer->error = error;
	}
	return NULL;
}

static void concurrent_insert(void)
{
	pthread_barrier_t barrier;
	pthread_t threads[2];
	struct writer writers[2] = { 0 };
	unsigned char *buffer = aligned_buffer(PAGE_BYTES);
	int error;

	current_case = "concurrent_insert";
	error = pthread_barrier_init(&barrier, NULL, 3);
	if (error)
		fail("barrier init error=%d", error);
	for (unsigned int cpu = 0; cpu < 2; cpu++) {
		writers[cpu].barrier = &barrier;
		writers[cpu].cpu = cpu;
		writers[cpu].buffer = aligned_buffer(PAGE_BYTES);
		error = pthread_create(&threads[cpu], NULL, concurrent_writer, &writers[cpu]);
		if (error)
			fail("pthread create error=%d", error);
	}
	for (unsigned int round = 0; round < ROUNDS; round++) {
		error = barrier_wait(&barrier);
		if (error)
			fail("start barrier error=%d", error);
		error = barrier_wait(&barrier);
		if (error)
			fail("end barrier error=%d", error);
		read_exact(buffer, PAGE_BYTES, CONCURRENT_BASE + round * PAGE_BYTES);
		for (size_t i = 0; i < PAGE_BYTES; i++)
			expect_byte(buffer, i, i < 2 * SECTOR_BYTES ?
				    concurrent_pattern(round, i / SECTOR_BYTES) : 0);
	}
	for (unsigned int cpu = 0; cpu < 2; cpu++) {
		error = pthread_join(threads[cpu], NULL);
		if (error || writers[cpu].error)
			fail("writer=%u join=%d write=%d", cpu, error, writers[cpu].error);
		free(writers[cpu].buffer);
	}
	error = pthread_barrier_destroy(&barrier);
	if (error)
		fail("barrier destroy error=%d", error);
	expect_pages(5 + ROUNDS);
	free(buffer);
	pass();
}

static void accounting(void)
{
	unsigned char *buffer = aligned_buffer(4 * PAGE_BYTES);

	current_case = "accounting";
	expect_pages(5 + ROUNDS);
	discard(0, CAPACITY);
	expect_pages(0);
	check_zero_range(buffer, 3 * PAGE_BYTES, 0);
	check_zero_range(buffer, 4 * PAGE_BYTES, DISCARD_BASE);
	for (unsigned int round = 0; round < ROUNDS; round++)
		check_zero_range(buffer, PAGE_BYTES, CONCURRENT_BASE + round * PAGE_BYTES);
	expect_pages(0);
	free(buffer);
	pass();
}

int main(void)
{
	authorize_vm();
	geometry();
	sparse_read();
	crossing_write();
	discard_edges();
	concurrent_insert();
	accounting();
	if (close(disk_fd))
		fail("close ram0 errno=%d", errno);
	puts("RUSIX_BRD_SUCCESS cases=6");
	finish();
}
