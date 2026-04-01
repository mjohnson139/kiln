from __future__ import annotations

import contextlib
import fcntl
from datetime import UTC, datetime
from pathlib import Path

from kiln import db
from kiln.runtime import run_workflow


def _field_matches(spec: str, value: int) -> bool:
    if spec == "*":
        return True
    if spec.startswith("*/"):
        interval = int(spec[2:])
        return value % interval == 0
    return value == int(spec)


def should_run_now(cron_expr: str, now: datetime) -> bool:
    minute, hour, dom, month, dow = cron_expr.split()
    return all(
        (
            _field_matches(minute, now.minute),
            _field_matches(hour, now.hour),
            _field_matches(dom, now.day),
            _field_matches(month, now.month),
            _field_matches(dow, int(now.strftime("%w"))),
        )
    )


@contextlib.contextmanager
def tick_lock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("w", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def run_due_schedules(now: datetime | None = None) -> list[str]:
    now = now or datetime.now(UTC)
    minute_key = now.replace(second=0, microsecond=0).isoformat()
    conn = db.connect()
    triggered: list[str] = []
    for schedule in db.list_schedules(conn):
        workflow_name = str(schedule["workflow_name"])
        last_enqueued = None if schedule["last_enqueued_at"] is None else str(schedule["last_enqueued_at"])
        if last_enqueued == minute_key:
            continue
        if not should_run_now(str(schedule["cron_expr"]), now):
            continue
        workflow_path = db.workflow_path_for_name(conn, workflow_name)
        if workflow_path is None:
            continue
        result = run_workflow(Path(workflow_path), trigger="schedule", context={})
        db.update_schedule_last_enqueued(conn, workflow_name, minute_key)
        triggered.append(result.run_id)
    return triggered
