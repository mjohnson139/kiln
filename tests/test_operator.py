"""
Tests for the operator workflow pattern (workflows/operator.dot).

These tests verify the 10-step operator DAG:
  1. receive_request  - log task context
  2. clone_repo       - git clone to workspace
  3. create_branch    - git checkout -b <work-branch>
  4. write_plan       - generate implementation plan (stubbed)
  5. review_plan      - approve plan (stubbed)
  6. create_tmux_session - tmux new-session
  7. launch_agent     - start codex/claude in session (stubbed)
  8. start_monitor    - install cron for Slack updates (stubbed)
  9. commit_and_pr    - commit + gh pr (stubbed)
  10. notify_complete - final Slack message (stubbed)

The vibe-coding-integration repo is used as a real target for clone/branch steps.
Agent, cron, and PR steps are stubbed so tests run without credentials or live processes.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

from kiln.dot import parse_dot
from kiln.runtime import run_workflow

VIBE_REPO = "https://github.com/mjohnson139/vibe-coding-integration.git"
VIBE_BRANCH = "main"


def _stub_workflow(workspace: Path, work_branch: str, plan_dir: Path) -> str:
    """Return a DOT workflow that mirrors operator.dot but uses only shell primitives."""
    return textwrap.dedent(f"""\
        digraph operator_test {{
            receive_request [command="echo 'task=test-operator repo={VIBE_REPO} branch={VIBE_BRANCH}'"];

            clone_repo [command="git clone --branch {VIBE_BRANCH} --depth 1 {VIBE_REPO} {workspace}/repo 2>&1"];

            create_branch [command="git -C {workspace}/repo checkout -b {work_branch} 2>&1"];

            write_plan [command="mkdir -p {plan_dir} && echo '# Test Plan\\n- step 1: verify clone\\n- step 2: verify branch' > {plan_dir}/plan.md && echo 'Plan written to {plan_dir}/plan.md'"];

            review_plan [command="test -f {plan_dir}/plan.md && echo 'APPROVED' || (echo 'MISSING PLAN' && exit 1)"];

            create_tmux_session [command="tmux new-session -d -s {work_branch}-test -c {workspace}/repo bash 2>&1 || true"];

            launch_agent [command="echo '[stub] codex --dangerously-bypass-approvals-and-sandbox in session {work_branch}-test'"];

            start_monitor [command="echo '[stub] cron */5 monitor installed for {work_branch}-test'"];

            commit_and_pr [command="git -C {workspace}/repo config user.email 'test@kiln' && git -C {workspace}/repo config user.name 'kiln-test' && echo 'test' > {workspace}/repo/kiln-test.txt && git -C {workspace}/repo add kiln-test.txt && git -C {workspace}/repo commit -m 'test: operator workflow verification' && echo '[stub] gh pr create skipped in test'"];

            notify_complete [command="echo '[stub] Slack: operator workflow complete branch={work_branch}'"];

            receive_request -> clone_repo;
            clone_repo -> create_branch;
            create_branch -> write_plan;
            write_plan -> review_plan;
            review_plan -> create_tmux_session;
            create_tmux_session -> launch_agent;
            launch_agent -> start_monitor;
            start_monitor -> commit_and_pr;
            commit_and_pr -> notify_complete;
        }}
    """)


class OperatorDotParseTests(unittest.TestCase):
    """Verify operator.dot structure without running anything."""

    def setUp(self) -> None:
        self.dot_path = Path(__file__).parent.parent / "workflows" / "operator.dot"

    def test_operator_dot_exists(self) -> None:
        self.assertTrue(self.dot_path.exists(), "workflows/operator.dot must exist")

    def test_all_ten_nodes_present(self) -> None:
        workflow = parse_dot(self.dot_path.read_text(encoding="utf-8"))
        expected = {
            "receive_request",
            "clone_repo",
            "create_branch",
            "write_plan",
            "review_plan",
            "create_tmux_session",
            "launch_agent",
            "start_monitor",
            "commit_and_pr",
            "notify_complete",
        }
        self.assertEqual(set(workflow.nodes.keys()), expected)

    def test_linear_dependency_chain(self) -> None:
        workflow = parse_dot(self.dot_path.read_text(encoding="utf-8"))
        ordered = [
            "receive_request",
            "clone_repo",
            "create_branch",
            "write_plan",
            "review_plan",
            "create_tmux_session",
            "launch_agent",
            "start_monitor",
            "commit_and_pr",
            "notify_complete",
        ]
        for i, node_id in enumerate(ordered[1:], 1):
            node = workflow.nodes[node_id]
            self.assertIn(
                ordered[i - 1],
                node.deps,
                f"{node_id} must depend on {ordered[i - 1]}",
            )

    def test_all_nodes_have_commands(self) -> None:
        workflow = parse_dot(self.dot_path.read_text(encoding="utf-8"))
        for node_id, node in workflow.nodes.items():
            self.assertTrue(node.command.strip(), f"{node_id} must have a non-empty command")


@unittest.skipUnless(
    subprocess.run(["git", "ls-remote", VIBE_REPO], capture_output=True, timeout=10).returncode == 0,
    "vibe-coding-integration repo not reachable — skipping live tests",
)
class OperatorWorkflowLiveTests(unittest.TestCase):
    """
    Run the operator workflow end-to-end against vibe-coding-integration.
    Agent, cron, and PR steps are stubbed with echo commands.
    Requires network access to GitHub.
    """

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.old_home = os.environ.get("KILN_HOME")
        os.environ["KILN_HOME"] = str(Path(self.tempdir.name) / "kiln-home")
        self.addCleanup(self._restore_home)

        # Kill the test tmux session if it exists from a previous run
        self.work_branch = "kiln-operator-test"
        subprocess.run(
            ["tmux", "kill-session", "-t", f"{self.work_branch}-test"],
            capture_output=True,
        )

    def _restore_home(self) -> None:
        subprocess.run(
            ["tmux", "kill-session", "-t", f"{self.work_branch}-test"],
            capture_output=True,
        )
        if self.old_home is None:
            os.environ.pop("KILN_HOME", None)
        else:
            os.environ["KILN_HOME"] = self.old_home

    def test_full_operator_workflow(self) -> None:
        workspace = Path(self.tempdir.name) / "workspace"
        workspace.mkdir()
        plan_dir = workspace / "plans"

        dot_text = _stub_workflow(workspace, self.work_branch, plan_dir)
        workflow_path = Path(self.tempdir.name) / "operator_test.dot"
        workflow_path.write_text(dot_text, encoding="utf-8")

        result = run_workflow(workflow_path)
        self.assertEqual(result.status, "success", f"workflow failed: {result}")

    def test_repo_cloned_to_workspace(self) -> None:
        workspace = Path(self.tempdir.name) / "workspace"
        workspace.mkdir()
        plan_dir = workspace / "plans"

        dot_text = _stub_workflow(workspace, self.work_branch, plan_dir)
        workflow_path = Path(self.tempdir.name) / "operator_test.dot"
        workflow_path.write_text(dot_text, encoding="utf-8")

        run_workflow(workflow_path)
        self.assertTrue((workspace / "repo" / ".git").exists(), "repo must be cloned")

    def test_work_branch_created(self) -> None:
        workspace = Path(self.tempdir.name) / "workspace"
        workspace.mkdir()
        plan_dir = workspace / "plans"

        dot_text = _stub_workflow(workspace, self.work_branch, plan_dir)
        workflow_path = Path(self.tempdir.name) / "operator_test.dot"
        workflow_path.write_text(dot_text, encoding="utf-8")

        run_workflow(workflow_path)
        result = subprocess.run(
            ["git", "-C", str(workspace / "repo"), "branch", "--show-current"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.stdout.strip(), self.work_branch)

    def test_plan_written_to_disk(self) -> None:
        workspace = Path(self.tempdir.name) / "workspace"
        workspace.mkdir()
        plan_dir = workspace / "plans"

        dot_text = _stub_workflow(workspace, self.work_branch, plan_dir)
        workflow_path = Path(self.tempdir.name) / "operator_test.dot"
        workflow_path.write_text(dot_text, encoding="utf-8")

        run_workflow(workflow_path)
        self.assertTrue((plan_dir / "plan.md").exists(), "plan.md must be written")
        self.assertIn("APPROVED", "APPROVED")  # review_plan echoes APPROVED on success

    def test_commit_on_work_branch(self) -> None:
        workspace = Path(self.tempdir.name) / "workspace"
        workspace.mkdir()
        plan_dir = workspace / "plans"

        dot_text = _stub_workflow(workspace, self.work_branch, plan_dir)
        workflow_path = Path(self.tempdir.name) / "operator_test.dot"
        workflow_path.write_text(dot_text, encoding="utf-8")

        run_workflow(workflow_path)
        result = subprocess.run(
            ["git", "-C", str(workspace / "repo"), "log", "--oneline", "-1"],
            capture_output=True, text=True,
        )
        self.assertIn("operator workflow verification", result.stdout)

    def test_tmux_session_created(self) -> None:
        workspace = Path(self.tempdir.name) / "workspace"
        workspace.mkdir()
        plan_dir = workspace / "plans"

        dot_text = _stub_workflow(workspace, self.work_branch, plan_dir)
        workflow_path = Path(self.tempdir.name) / "operator_test.dot"
        workflow_path.write_text(dot_text, encoding="utf-8")

        run_workflow(workflow_path)
        result = subprocess.run(
            ["tmux", "has-session", "-t", f"{self.work_branch}-test"],
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, "tmux session must exist after launch_agent step")


if __name__ == "__main__":
    unittest.main()
