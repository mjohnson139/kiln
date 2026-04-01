# Kiln

Minimal local DAG orchestrator.

`kiln` runs shell-command workflows defined in DOT files, records state in SQLite, stores per-node logs on disk, and exposes status through a small CLI.

## Quick Start

```bash
cd /home/matt/dev/kiln
PYTHONPATH=src python3 -m kiln.cli list
PYTHONPATH=src python3 -m kiln.cli run workflows/sample.dot
PYTHONPATH=src python3 -m kiln.cli status --json
```

## Commands

- `PYTHONPATH=src python3 -m kiln.cli run <workflow>`
- `PYTHONPATH=src python3 -m kiln.cli tick`
- `PYTHONPATH=src python3 -m kiln.cli status --json`
- `PYTHONPATH=src python3 -m kiln.cli logs <run-id> [node-id]`
- `PYTHONPATH=src python3 -m kiln.cli retry <run-id> --from-failed`
- `PYTHONPATH=src python3 -m kiln.cli schedule add <workflow> "*/15 * * * *"`
- `PYTHONPATH=src python3 -m kiln.cli report --slack`

## Slack Delivery

`kiln report --slack` uses this order:

1. `KILN_SLACK_WEBHOOK_URL` if present
2. `claude --print` fallback that sends the report to Slack channel `C0AN6F2MUAH`

## Cron Install

```bash
cd /home/matt/dev/kiln
bash scripts/install_cron.sh
```

That installs:

- `kiln tick` every minute
- `kiln report --slack` every 15 minutes

## Tmux

Attach to the running project session with:

```bash
tmux attach -t kiln
```
