# -*- coding: utf-8 -*-
"""Batch review lookup used by teacher course and model lists."""

import os
import sys
import time
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(REPO_ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from db_connection import get_connection  # noqa: E402
from db_domains import reviews  # noqa: E402


class ReviewBatchLookupTest(unittest.TestCase):
    def test_latest_review_is_returned_for_each_content_id_in_one_lookup(self):
        stamp = time.time_ns() % 1000000000
        ids = (stamp, stamp + 1)
        conn = get_connection()
        conn.execute(
            "INSERT INTO content_reviews "
            "(content_type, content_id, submitter_id, status, review_comment) "
            "VALUES ('course', ?, 'teacher_demo', 'rejected', '旧结论')",
            (ids[0],),
        )
        conn.execute(
            "INSERT INTO content_reviews "
            "(content_type, content_id, submitter_id, status, review_comment) "
            "VALUES ('course', ?, 'teacher_demo', 'approved', '新结论')",
            (ids[0],),
        )
        conn.execute(
            "INSERT INTO content_reviews "
            "(content_type, content_id, submitter_id, status, review_comment) "
            "VALUES ('course', ?, 'teacher_demo', 'rejected', '另一条')",
            (ids[1],),
        )
        conn.commit()
        conn.close()
        self.addCleanup(self._cleanup, ids)

        found = reviews.get_latest_reviews_by_content('course', ids)
        self.assertEqual(found[ids[0]]['review_comment'], '新结论')
        self.assertEqual(found[ids[1]]['review_comment'], '另一条')

    @staticmethod
    def _cleanup(ids):
        for content_id in ids:
            reviews.delete_reviews_for('course', content_id)


if __name__ == '__main__':
    unittest.main()
