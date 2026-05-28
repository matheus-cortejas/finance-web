from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from scheduler import jobs


class SchedulerJobsTests(unittest.TestCase):
    def test_collect_initial_news_uses_retention_window(self):
        with patch.object(jobs, "get_watchlist_assets", return_value=[{"id": 1, "code": "PETR4", "name": "PETROBRAS"}]), \
            patch.object(jobs, "check_feeds_and_report", return_value=[{"title": "ok"}]) as check_report:
            result = jobs.collect_initial_news(["https://example.test/feed"])

        self.assertEqual(result, [{"title": "ok"}])
        check_report.assert_called_once()
        args, kwargs = check_report.call_args
        self.assertEqual(args[0], ["https://example.test/feed"])
        self.assertEqual(args[1], [{"id": 1, "code": "PETR4", "name": "PETROBRAS"}])
        self.assertEqual(kwargs["within_days"], 1)

    def test_cleanup_old_articles_delegates_to_repository(self):
        with patch.object(jobs, "purge_articles_older_than_days", return_value=3) as purge:
            result = jobs.cleanup_old_articles()

        self.assertEqual(result, 3)
        purge.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()