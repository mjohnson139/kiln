from __future__ import annotations

import re
from pathlib import Path

from kiln.models import NodeDef, WorkflowDef

NODE_RE = re.compile(r'^\s*(?P<id>[A-Za-z0-9_]+)\s*\[(?P<attrs>.+)\]\s*;\s*$')
EDGE_RE = re.compile(r'^\s*(?P<src>[A-Za-z0-9_]+)\s*->\s*(?P<dst>[A-Za-z0-9_]+)\s*;\s*$')
ATTR_RE = re.compile(r'([A-Za-z_]+)\s*=\s*"((?:[^"\\]|\\.)*)"')


def _decode_attr(value: str) -> str:
    return bytes(value, "utf-8").decode("unicode_escape")


def _statements(text: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    in_quotes = False
    escaped = False
    for char in text:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            current.append(char)
            escaped = True
            continue
        if char == '"':
            current.append(char)
            in_quotes = not in_quotes
            continue
        if not in_quotes and char in "{};":
            chunk = "".join(current).strip()
            if chunk:
                statements.append(chunk)
            current = []
            if char in "{}":
                statements.append(char)
            continue
        current.append(char)
    chunk = "".join(current).strip()
    if chunk:
        statements.append(chunk)
    return statements


def parse_dot(text: str, path: str = "<memory>") -> WorkflowDef:
    nodes: dict[str, dict[str, str | list[str]]] = {}
    edges: list[tuple[str, str]] = []
    graph_name = Path(path).stem

    for raw_line in _statements(text):
        line = raw_line.strip()
        if not line or line.startswith("//") or line in {"{", "}"}:
            continue
        if line.startswith("digraph "):
            parts = line.split()
            if len(parts) >= 2:
                graph_name = parts[1]
            continue
        node_match = NODE_RE.match(f"{line};")
        if node_match:
            node_id = node_match.group("id")
            attrs = {
                key: _decode_attr(value)
                for key, value in ATTR_RE.findall(node_match.group("attrs"))
            }
            command = attrs.get("command")
            if not command:
                raise ValueError(f"node '{node_id}' is missing command")
            nodes.setdefault(node_id, {})
            nodes[node_id].update(attrs)
            nodes[node_id]["deps"] = nodes[node_id].get("deps", [])
            continue
        edge_match = EDGE_RE.match(f"{line};")
        if edge_match:
            edges.append((edge_match.group("src"), edge_match.group("dst")))
            continue
        raise ValueError(f"unsupported dot line: {raw_line}")

    for src, dst in edges:
        if src not in nodes or dst not in nodes:
            raise ValueError(f"edge references unknown node: {src} -> {dst}")
        deps = nodes[dst].setdefault("deps", [])
        assert isinstance(deps, list)
        deps.append(src)

    node_defs: dict[str, NodeDef] = {}
    for node_id, attrs in nodes.items():
        deps = attrs.get("deps", [])
        assert isinstance(deps, list)
        node_defs[node_id] = NodeDef(
            node_id=node_id,
            command=str(attrs["command"]),
            cwd=str(attrs["cwd"]) if "cwd" in attrs else None,
            name=str(attrs["name"]) if "name" in attrs else None,
            deps=tuple(deps),
        )

    return WorkflowDef(name=graph_name, path=path, nodes=node_defs)


def load_workflow(path: Path) -> WorkflowDef:
    return parse_dot(path.read_text(encoding="utf-8"), path=str(path))
