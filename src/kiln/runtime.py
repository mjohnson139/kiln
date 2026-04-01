from __future__ import annotations

import json
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path

from kiln import db
from kiln.dot import load_workflow
from kiln.models import RunResult, WorkflowDef
from kiln.paths import log_root


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _run_id() -> str:
    return f"run-{uuid.uuid4().hex[:12]}"


def _ready_nodes(workflow: WorkflowDef, completed: set[str], failed: bool, seen: set[str]) -> list[str]:
    if failed:
        return []
    ready: list[str] = []
    for node_id, node in workflow.nodes.items():
        if node_id in seen:
            continue
        if all(dep in completed for dep in node.deps):
            ready.append(node_id)
    return sorted(ready)


def _execute(
    workflow_path: Path,
    trigger: str,
    context: dict[str, str],
    skipped_successes: set[str] | None = None,
) -> RunResult:
    conn = db.connect()
    workflow = load_workflow(workflow_path)
    db.register_workflow(conn, workflow.name, workflow_path, _now())

    run_id = _run_id()
    db.create_run(conn, run_id, workflow.name, workflow_path, trigger, _now(), context)

    run_log_dir = log_root() / run_id
    run_log_dir.mkdir(parents=True, exist_ok=True)

    skipped_successes = skipped_successes or set()
    for node_id, node in workflow.nodes.items():
        node_log_path = run_log_dir / f"{node_id}.log"
        initial_status = "skipped" if node_id in skipped_successes else "pending"
        db.create_node_run(conn, run_id, node_id, node.command, node.cwd, node_log_path, status=initial_status)

    completed = set(skipped_successes)
    seen = set(skipped_successes)
    failed = False

    while True:
        ready = _ready_nodes(workflow, completed, failed, seen)
        if not ready:
            break
        for node_id in ready:
            node = workflow.nodes[node_id]
            seen.add(node_id)
            node_log_path = run_log_dir / f"{node_id}.log"
            db.start_node_run(conn, run_id, node_id, _now())
            resolved_cwd = workflow_path.parent if node.cwd is None else (workflow_path.parent / node.cwd).resolve()
            with node_log_path.open("w", encoding="utf-8") as handle:
                process = subprocess.run(
                    node.command,
                    shell=True,
                    cwd=resolved_cwd,
                    text=True,
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                )
            status = "success" if process.returncode == 0 else "failed"
            db.finish_node_run(conn, run_id, node_id, status, _now(), process.returncode)
            if status == "success":
                completed.add(node_id)
            else:
                failed = True
                break

    overall_status = "success" if len(completed) == len(workflow.nodes) else "failed"
    db.finish_run(conn, run_id, overall_status, _now())
    return RunResult(run_id=run_id, workflow_name=workflow.name, status=overall_status)


def run_workflow(workflow_path: Path, trigger: str = "manual", context: dict[str, str] | None = None) -> RunResult:
    return _execute(workflow_path=workflow_path.resolve(), trigger=trigger, context=context or {})


def retry_run(run_id: str, from_failed: bool = False) -> RunResult:
    conn = db.connect()
    run = db.fetch_run(conn, run_id)
    workflow_path = Path(str(run["workflow_path"]))
    context = json.loads(str(run["context_json"]))
    if not from_failed:
        return _execute(workflow_path=workflow_path, trigger="retry", context=context)

    prior_nodes = db.fetch_node_runs(conn, run_id)
    preserved_successes = {str(row["node_id"]) for row in prior_nodes if str(row["status"]) == "success"}
    return _execute(
        workflow_path=workflow_path,
        trigger="retry-from-failed",
        context=context,
        skipped_successes=preserved_successes,
    )


def read_logs(run_id: str, node_id: str | None = None) -> str:
    conn = db.connect()
    node_runs = db.fetch_node_runs(conn, run_id)
    selected = [row for row in node_runs if node_id is None or str(row["node_id"]) == node_id]
    if not selected:
        raise KeyError(f"no logs found for run={run_id} node={node_id}")
    chunks: list[str] = []
    for row in selected:
        path = Path(str(row["log_path"]))
        heading = f"== {row['node_id']} =="
        content = path.read_text(encoding="utf-8") if path.exists() else ""
        chunks.append(f"{heading}\n{content}".rstrip())
    return "\n\n".join(chunks)
