---
name: kiln
description: Use the local kiln CLI to run and inspect orchestrated workflows.
---

# Kiln Skill

Use `kiln` as the source of truth for workflow execution.

## Rules

- Run `PYTHONPATH=src python3 -m kiln.cli list` before assuming workflow names.
- Use `PYTHONPATH=src python3 -m kiln.cli status --json` for machine-readable status checks.
- Use `PYTHONPATH=src python3 -m kiln.cli logs <run-id>` when investigating failures.
- Use `PYTHONPATH=src python3 -m kiln.cli retry <run-id> --from-failed` to resume after a failed node.
- Never edit the SQLite database or log files directly.

## Commands

```bash
PYTHONPATH=src python3 -m kiln.cli run workflows/sample.dot
PYTHONPATH=src python3 -m kiln.cli status --json
PYTHONPATH=src python3 -m kiln.cli report --slack
```
