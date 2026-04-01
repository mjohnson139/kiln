from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from kiln.slack import send_slack_message


class SlackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_webhook = os.environ.get("KILN_SLACK_WEBHOOK_URL")
        os.environ.pop("KILN_SLACK_WEBHOOK_URL", None)
        self.addCleanup(self._restore_webhook)

    def _restore_webhook(self) -> None:
        if self.old_webhook is None:
            os.environ.pop("KILN_SLACK_WEBHOOK_URL", None)
        else:
            os.environ["KILN_SLACK_WEBHOOK_URL"] = self.old_webhook

    @patch("kiln.slack.subprocess.run")
    def test_claude_fallback_uses_timeout(self, run_mock) -> None:
        send_slack_message("status")
        _, kwargs = run_mock.call_args
        self.assertEqual(kwargs["timeout"], 30)


if __name__ == "__main__":
    unittest.main()
