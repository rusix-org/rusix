// SPDX-License-Identifier: GPL-2.0-only
/* Inline/macro access only: request policy and backing storage live in Rust. */
#include <linux/bio.h>
#include <linux/blkdev.h>
#include <linux/highmem.h>

#ifdef CONFIG_BLOCK

struct bio_vec rust_helper_bio_current_segment(struct bio *bio)
{
	return bio_iter_iovec(bio, bio->bi_iter);
}

void rust_helper_bio_advance_single(struct bio *bio, unsigned int bytes)
{
	bio_advance_iter_single(bio, &bio->bi_iter, bytes);
}

void rust_helper_memcpy_to_page(struct page *page, size_t offset,
			       const char *from, size_t len)
{
	memcpy_to_page(page, offset, from, len);
}

void rust_helper_memcpy_from_page(char *to, struct page *page,
				 size_t offset, size_t len)
{
	memcpy_from_page(to, page, offset, len);
}

void rust_helper_zero_user_segment(struct page *page, unsigned int start,
				   unsigned int end)
{
	zero_user_segment(page, start, end);
}

unsigned int rust_helper_bio_operation(const struct bio *bio)
{
	return bio_op(bio);
}

bool rust_helper_bio_is_nowait(const struct bio *bio)
{
	return bio->bi_opf & REQ_NOWAIT;
}

void rust_helper_bio_io_error(struct bio *bio)
{
	bio_io_error(bio);
}

void rust_helper_bio_wouldblock_error(struct bio *bio)
{
	bio_wouldblock_error(bio);
}

blk_features_t rust_helper_blk_feat_synchronous(void)
{
	return BLK_FEAT_SYNCHRONOUS;
}

blk_features_t rust_helper_blk_feat_nowait(void)
{
	return BLK_FEAT_NOWAIT;
}

#endif /* CONFIG_BLOCK */
