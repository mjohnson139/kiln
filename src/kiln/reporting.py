from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from kiln import db


def collect_status_snapshot(window_minutes: int = 15) -> dict[str, object]:
    conn = db.connect()
    now = datetime.now(UTC).replace(microsecond=0)
    since = (now - timedelta(minutes=window_minutes)).isoformat()
    active_runs = [dict(row) for row in db.list_active_runs(conn)]
    recent_runs = [dict(row) for row in db.list_recent_runs_since(conn, since)]
    return {
        "generated_at": now.isoformat(),
        "window_minutes": window_minutes,
        "active_runs": active_runs,
        "recent_runs": recent_runs,
    }


def build_status_report(snapshot: dict[str, object]) -> str:
    active_runs = list(snapshot["active_runs"])
    recent_runs = list(snapshot["recent_runs"])
    failures = [row for row in recent_runs if row["status"] == "failed"]
    successes = [row for row in recent_runs if row["status"] == "success"]

    lines = [
        f"[Kiln Status] {snapshot['generated_at']}",
        f"Active runs: {len(active_runs)}",
    ]
    if active_runs:
        lines.append("In progress:")
        for row in active_runs[:5]:
            lines.append(f"- {row['id']} {row['workflow_name']} ({row['started_at']})")
    lines.append(f"Failures in window: {len(failures)}")
    for row in failures[:5]:
        lines.append(f"- {row['id']} {row['workflow_name']}")
    lines.append(f"Successes in window: {len(successes)}")
    for row in successes[:5]:
        lines.append(f"- {row['id']} {row['workflow_name']}")
    return "\n".join(lines)


def status_json(snapshot: dict[str, object] | None = None) -> str:
    return json.dumps(snapshot or collect_status_snapshot(), indent=2, sort_keys=True)
