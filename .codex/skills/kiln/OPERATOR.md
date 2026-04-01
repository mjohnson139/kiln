# kiln operator skill

Use this skill when asked to run the operator workflow — i.e., take a task description, a repo URL, and a branch, and execute the full 10-step development loop.

## When to use

- User provides a repo + branch + task and asks you to "run it" or "implement it"
- User says "use the operator workflow"
- You need to orchestrate: clone → branch → plan → agent → monitor → commit → PR

## How to run

```bash
# Required env vars
export REPO=https://github.com/owner/repo.git
export BRANCH=main              # starting branch to clone from
export WORK_BRANCH=feat/my-task # new branch for the work
export TASK="describe the work here"

# Run
kiln run workflows/operator.dot
```

## What each step does

| Step | Node | What happens |
|------|------|-------------|
| 1 | `receive_request` | Logs task context |
| 2 | `clone_repo` | Clones `$REPO` at `$BRANCH` to `/tmp/kiln-workspace/$BRANCH` |
| 3 | `create_branch` | Creates `$WORK_BRANCH` in the workspace |
| 4 | `write_plan` | Runs `claude` with superpowers:writing-plans to write a plan to `docs/superpowers/plans/` |
| 5 | `review_plan` | Runs `claude` to review and approve the plan |
| 6 | `create_tmux_session` | Creates `tmux new-session -s $WORK_BRANCH` |
| 7 | `launch_agent` | Sends codex `--dangerously-bypass-approvals-and-sandbox` into the tmux session |
| 8 | `start_monitor` | Installs `*/5 * * * *` cron to post Slack updates to `#ray-groove-manager` |
| 9 | `commit_and_pr` | Commits all changes (no secrets), opens `gh pr create` back to `$BRANCH` |
| 10 | `notify_complete` | Posts final Slack message with PR link |

## Monitoring

- Status updates go to `#ray-groove-manager` every 5 minutes while the agent works
- Logs: `/tmp/kiln-monitor-$WORK_BRANCH.log`
- Attach to agent session: `tmux attach -t $WORK_BRANCH`

## Tests

```bash
cd ~/dev/kiln
PYTHONPATH=src python3 -m unittest tests.test_operator -v
```

- `OperatorDotParseTests` — fast, no network: verifies DAG structure of operator.dot
- `OperatorWorkflowLiveTests` — requires GitHub access: clones vibe-coding-integration, runs all 10 steps with stubbed agent/cron/PR commands

## Notes

- Agent steps use `/home/matt/.npm-global/bin/codex` (full path, avoids PATH issues in subshells)
- Slack target: `#ray-groove-manager` (C0AN6F2MUAH)
- Sensitive file check in `commit_and_pr` guards against committing keys/tokens
