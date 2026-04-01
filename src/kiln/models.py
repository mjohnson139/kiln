from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class NodeDef:
    node_id: str
    command: str
    cwd: str | None = None
    name: str | None = None
    deps: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class WorkflowDef:
    name: str
    path: str
    nodes: dict[str, NodeDef]


@dataclass(frozen=True)
class RunResult:
    run_id: str
    workflow_name: str
    status: str
