from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from kiln.runtime import run_workflow
from kiln.reporting import build_status_report, collect_status_snapshot


class ReportingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.old_home = os.environ.get("KILN_HOME")
        os.environ["KILN_HOME"] = str(Path(self.tempdir.name) / "kiln-home")
        self.addCleanup(self._restore_home)

    def _restore_home(self) -> None:
        if self.old_home is None:
            os.environ.pop("KILN_HOME", None)
        else:
            os.environ["KILN_HOME"] = self.old_home

    def test_build_status_report_mentions_successes_and_failures(self) -> None:
        success_workflow = Path(self.tempdir.name) / "ok.dot"
        success_workflow.write_text('digraph ok { one [command="python3 -c \\"print(1)\\""]; }', encoding="utf-8")
        failure_workflow = Path(self.tempdir.name) / "bad.dot"
        failure_workflow.write_text('digraph bad { one [command="python3 -c \\"import sys; sys.exit(1)\\""]; }', encoding="utf-8")
        run_workflow(success_workflow)
        run_workflow(failure_workflow)

        report = build_status_report(collect_status_snapshot())
        self.assertIn("Failures in window", report)
        self.assertIn("Successes in window", report)


if __name__ == "__main__":
    unittest.main()
