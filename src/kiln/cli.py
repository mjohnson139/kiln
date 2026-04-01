from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from kiln import db
from kiln.dot import load_workflow
from kiln.paths import lock_root
from kiln.reporting import build_status_report, collect_status_snapshot, status_json
from kiln.runtime import read_logs, retry_run, run_workflow
from kiln.scheduler import run_due_schedules, tick_lock
from kiln.slack import send_slack_message


def _workflow_candidates(workflow_dir: Path) -> list[Path]:
    return sorted(workflow_dir.glob("*.dot"))


def _resolve_workflow(arg: str, workflow_dir: Path) -> Path:
    candidate = Path(arg)
    if candidate.exists():
        return candidate.resolve()
    dotted = workflow_dir / f"{arg}.dot"
    if dotted.exists():
        return dotted.resolve()
    plain = workflow_dir / arg
    if plain.exists():
        return plain.resolve()
    raise FileNotFoundError(f"workflow not found: {arg}")


def _parse_context(items: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in items:
        key, _, value = item.partition("=")
        if not key or not _:
            raise ValueError(f"invalid context item: {item}")
        result[key] = value
    return result


def cmd_list(args: argparse.Namespace) -> int:
    for path in _workflow_candidates(Path(args.workflow_dir)):
        workflow = load_workflow(path)
        print(f"{workflow.name}\t{path}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    workflow_path = _resolve_workflow(args.workflow, Path(args.workflow_dir))
    result = run_workflow(workflow_path, trigger="manual", context=_parse_context(args.context))
    print(json.dumps({"run_id": result.run_id, "status": result.status, "workflow": result.workflow_name}))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    snapshot = collect_status_snapshot(window_minutes=args.window_minutes)
    if args.json:
        print(status_json(snapshot))
    else:
        print(build_status_report(snapshot))
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    print(read_logs(args.run_id, args.node_id))
    return 0


def cmd_retry(args: argparse.Namespace) -> int:
    result = retry_run(args.run_id, from_failed=args.from_failed)
    print(json.dumps({"run_id": result.run_id, "status": result.status, "workflow": result.workflow_name}))
    return 0


def cmd_schedule_add(args: argparse.Namespace) -> int:
    workflow_path = _resolve_workflow(args.workflow, Path(args.workflow_dir))
    workflow = load_workflow(workflow_path)
    conn = db.connect()
    db.register_workflow(conn, workflow.name, workflow_path, "manual")
    db.add_schedule(conn, workflow.name, args.cron_expr)
    print(f"scheduled {workflow.name} on {args.cron_expr}")
    return 0


def cmd_tick(_: argparse.Namespace) -> int:
    with tick_lock(lock_root() / "tick.lock"):
        triggered = run_due_schedules()
    print(json.dumps({"triggered": triggered}))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    snapshot = collect_status_snapshot(window_minutes=args.window_minutes)
    message = build_status_report(snapshot)
    if args.slack:
        send_slack_message(message)
    print(message)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kiln")
    parser.set_defaults(func=None)
    parser.add_argument("--workflow-dir", default=os.environ.get("KILN_WORKFLOW_DIR", "workflows"))
    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser("list")
    list_parser.set_defaults(func=cmd_list)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("workflow")
    run_parser.add_argument("--context", action="append", default=[])
    run_parser.set_defaults(func=cmd_run)

    tick_parser = subparsers.add_parser("tick")
    tick_parser.set_defaults(func=cmd_tick)

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--json", action="store_true")
    status_parser.add_argument("--window-minutes", type=int, default=15)
    status_parser.set_defaults(func=cmd_status)

    logs_parser = subparsers.add_parser("logs")
    logs_parser.add_argument("run_id")
    logs_parser.add_argument("node_id", nargs="?")
    logs_parser.set_defaults(func=cmd_logs)

    retry_parser = subparsers.add_parser("retry")
    retry_parser.add_argument("run_id")
    retry_parser.add_argument("--from-failed", action="store_true")
    retry_parser.set_defaults(func=cmd_retry)

    schedule_parser = subparsers.add_parser("schedule")
    schedule_subparsers = schedule_parser.add_subparsers(dest="schedule_command")
    schedule_add = schedule_subparsers.add_parser("add")
    schedule_add.add_argument("workflow")
    schedule_add.add_argument("cron_expr")
    schedule_add.set_defaults(func=cmd_schedule_add)

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--slack", action="store_true")
    report_parser.add_argument("--window-minutes", type=int, default=15)
    report_parser.set_defaults(func=cmd_report)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.func is None:
        parser.print_help()
        return 1
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
