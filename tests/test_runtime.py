from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from kiln import db
from kiln.runtime import read_logs, retry_run, run_workflow


class RuntimeTests(unittest.TestCase):
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

    def test_run_workflow_records_success(self) -> None:
        workflow_path = Path(self.tempdir.name) / "success.dot"
        workflow_path.write_text(
            'digraph sample { one [command="python3 -c \\"print(1)\\""]; }',
            encoding="utf-8",
        )
        result = run_workflow(workflow_path, trigger="manual", context={})
        self.assertEqual(result.status, "success")
        self.assertIn("1", read_logs(result.run_id))

    def test_retry_from_failed_skips_successful_nodes(self) -> None:
        stamp = Path(self.tempdir.name) / "stamp.txt"
        workflow_path = Path(self.tempdir.name) / "retry.dot"
        workflow_path.write_text(
            (
                "digraph retry {\n"
                f'  one [command="python3 -c \\"from pathlib import Path; p = Path(r\'{stamp}\'); p.write_text(str(int(p.read_text()) + 1) if p.exists() else \'1\')\\""];\n'
                '  two [command="python3 -c \\"import sys; sys.exit(1)\\""];\n'
                "  one -> two;\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        first = run_workflow(workflow_path)
        self.assertEqual(first.status, "failed")
        second = retry_run(first.run_id, from_failed=True)
        self.assertEqual(second.status, "failed")
        self.assertEqual(stamp.read_text(encoding="utf-8"), "1")

    def test_schedule_rows_persist(self) -> None:
        conn = db.connect()
        db.add_schedule(conn, "sample", "*/15 * * * *")
        rows = db.list_schedules(conn)
        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
