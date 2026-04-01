from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from kiln.paths import db_path, ensure_app_dirs


def connect() -> sqlite3.Connection:
    ensure_app_dirs()
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists workflows (
            name text primary key,
            path text not null,
            sha256 text not null,
            created_at text not null
        );
        create table if not exists schedules (
            workflow_name text primary key,
            cron_expr text not null,
            active integer not null default 1,
            last_enqueued_at text
        );
        create table if not exists runs (
            id text primary key,
            workflow_name text not null,
            workflow_path text not null,
            status text not null,
            trigger text not null,
            started_at text not null,
            finished_at text,
            context_json text not null
        );
        create table if not exists node_runs (
            id integer primary key autoincrement,
            run_id text not null,
            node_id text not null,
            status text not null,
            command text not null,
            cwd text,
            log_path text not null,
            started_at text,
            finished_at text,
            exit_code integer
        );
        """
    )
    conn.commit()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def register_workflow(conn: sqlite3.Connection, name: str, path: Path, created_at: str) -> None:
    conn.execute(
        """
        insert into workflows(name, path, sha256, created_at)
        values (?, ?, ?, ?)
        on conflict(name) do update set path=excluded.path, sha256=excluded.sha256
        """,
        (name, str(path), _sha256(path), created_at),
    )
    conn.commit()


def add_schedule(conn: sqlite3.Connection, workflow_name: str, cron_expr: str) -> None:
    conn.execute(
        """
        insert into schedules(workflow_name, cron_expr, active, last_enqueued_at)
        values (?, ?, 1, null)
        on conflict(workflow_name) do update set cron_expr=excluded.cron_expr, active=1
        """,
        (workflow_name, cron_expr),
    )
    conn.commit()


def list_schedules(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(conn.execute("select * from schedules where active = 1 order by workflow_name"))


def update_schedule_last_enqueued(conn: sqlite3.Connection, workflow_name: str, iso_minute: str) -> None:
    conn.execute(
        "update schedules set last_enqueued_at = ? where workflow_name = ?",
        (iso_minute, workflow_name),
    )
    conn.commit()


def create_run(
    conn: sqlite3.Connection,
    run_id: str,
    workflow_name: str,
    workflow_path: Path,
    trigger: str,
    started_at: str,
    context: dict[str, str],
) -> None:
    conn.execute(
        """
        insert into runs(id, workflow_name, workflow_path, status, trigger, started_at, finished_at, context_json)
        values (?, ?, ?, 'running', ?, ?, null, ?)
        """,
        (run_id, workflow_name, str(workflow_path), trigger, started_at, json.dumps(context, sort_keys=True)),
    )
    conn.commit()


def finish_run(conn: sqlite3.Connection, run_id: str, status: str, finished_at: str) -> None:
    conn.execute(
        "update runs set status = ?, finished_at = ? where id = ?",
        (status, finished_at, run_id),
    )
    conn.commit()


def create_node_run(
    conn: sqlite3.Connection,
    run_id: str,
    node_id: str,
    command: str,
    cwd: str | None,
    log_path: Path,
    status: str = "pending",
) -> None:
    conn.execute(
        """
        insert into node_runs(run_id, node_id, status, command, cwd, log_path, started_at, finished_at, exit_code)
        values (?, ?, ?, ?, ?, ?, null, null, null)
        """,
        (run_id, node_id, status, command, cwd, str(log_path)),
    )
    conn.commit()


def start_node_run(conn: sqlite3.Connection, run_id: str, node_id: str, started_at: str) -> None:
    conn.execute(
        """
        update node_runs
        set status = 'running', started_at = ?
        where run_id = ? and node_id = ?
        """,
        (started_at, run_id, node_id),
    )
    conn.commit()


def finish_node_run(
    conn: sqlite3.Connection,
    run_id: str,
    node_id: str,
    status: str,
    finished_at: str,
    exit_code: int | None,
) -> None:
    conn.execute(
        """
        update node_runs
        set status = ?, finished_at = ?, exit_code = ?
        where run_id = ? and node_id = ?
        """,
        (status, finished_at, exit_code, run_id, node_id),
    )
    conn.commit()


def fetch_run(conn: sqlite3.Connection, run_id: str) -> sqlite3.Row:
    row = conn.execute("select * from runs where id = ?", (run_id,)).fetchone()
    if row is None:
        raise KeyError(f"unknown run id: {run_id}")
    return row


def fetch_node_runs(conn: sqlite3.Connection, run_id: str) -> list[sqlite3.Row]:
    return list(conn.execute("select * from node_runs where run_id = ? order by id", (run_id,)))


def list_runs(conn: sqlite3.Connection, limit: int = 20) -> list[sqlite3.Row]:
    return list(conn.execute("select * from runs order by started_at desc limit ?", (limit,)))


def list_active_runs(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(conn.execute("select * from runs where status = 'running' order by started_at"))


def list_recent_runs_since(conn: sqlite3.Connection, since_iso: str) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            "select * from runs where started_at >= ? order by started_at desc",
            (since_iso,),
        )
    )


def workflow_path_for_name(conn: sqlite3.Connection, workflow_name: str) -> str | None:
    row = conn.execute("select path from workflows where name = ?", (workflow_name,)).fetchone()
    return None if row is None else str(row["path"])
