import json
from pathlib import Path

_FILE = Path(__file__).parent / "workspace_nodes.json"


def load() -> list:
    if _FILE.exists():
        return json.loads(_FILE.read_text(encoding="utf-8"))
    return []


def _save(nodes: list):
    _FILE.write_text(json.dumps(nodes, indent=2), encoding="utf-8")


def add(label: str) -> list:
    nodes = load()
    next_id = max((n["id"] for n in nodes), default=-1) + 1
    nodes.append({"id": next_id, "label": label})
    _save(nodes)
    return nodes


def remove(node_id: int) -> list:
    nodes = [n for n in load() if n["id"] != node_id]
    _save(nodes)
    return nodes


def clear() -> list:
    _save([])
    return []
