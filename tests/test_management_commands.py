from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "setup.settings")

import django

django.setup()

from django.core.management import call_command

from core.management import workflows
from core.management.commands import run_monitor as run_monitor_cmd
from core.management.commands import run_scheduler as run_scheduler_cmd


class ManagementCommandTests(unittest.TestCase):
    def test_run_scheduler_initializes_scheduler(self):
        with patch.object(run_scheduler_cmd, "run_scheduler_workflow") as run_workflow:
            call_command("run_scheduler", rss="/tmp/rss.txt")

        run_workflow.assert_called_once_with(rss_path="/tmp/rss.txt")

    def test_run_monitor_delegates_to_workflow(self):
        with patch.object(run_monitor_cmd, "run_monitor_workflow") as run_workflow:
            call_command("run_monitor", b3_csv="/tmp/b3.csv", rss="/tmp/rss.txt", no_interactive=True)

        run_workflow.assert_called_once_with(b3_csv="/tmp/b3.csv", rss_path="/tmp/rss.txt", interactive=False)

    def test_run_monitor_workflow_does_not_launch_scheduler(self):
        with patch("core.services.acao_service.fetch_sp500_and_store", return_value=0), \
            patch("core.services.acao_service.parse_b3_csv", return_value=0), \
            patch.object(workflows, "load_feeds", return_value=[]), \
            patch.object(workflows, "run_scheduler_workflow") as run_scheduler_workflow:
            workflows.run_monitor_workflow(b3_csv="/tmp/b3.csv", rss_path="/tmp/rss.txt", interactive=False)

        run_scheduler_workflow.assert_not_called()


if __name__ == "__main__":
    unittest.main()