#!/usr/bin/env python3
"""Persistent proof-DAG (BIG_PROBLEMS_DESIGN.md §1) — the single source of truth for a big target.

A node = one lemma/obligation (a `proofs/<id>/` folder). Edges = "uses" (a node consumes its deps).
The graph that today lives only in PLAN prose becomes machine-readable here, so a frontier scheduler
(orchestrator.py, step 2) can walk it turn-based, and so the work survives sessions/crashes.

This module is dependency-light on purpose: only stdlib + lean_pipeline helpers (no network, no model
residency) so the DAG can be inspected/seeded without spinning anything up.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

AGENTS = Path(__file__).resolve().parent
sys.path.insert(0, str(AGENTS))
from lean_pipeline import has_sorry  # noqa: E402  (stdlib-only helper)

STATUSES = {"open", "context", "planning", "proving", "researching", "proved", "refuted", "blocked"}
STD_AXIOMS = ["propext", "Classical.choice", "Quot.sound"]


@dataclass
class Node:
    id: str
    statement: str = ""                 # self-contained lean (imports + open + sig := by sorry)
    status: str = "open"
    deps: list[str] = field(default_factory=list)
    parent_proof: str | None = None
    depth: int = 0
    main_decl: str = ""                 # the node's primary theorem/lemma name
    provides: list[str] = field(default_factory=list)  # all decl names this node defines
    premises: list[str] = field(default_factory=list)
    brief: str = ""
    report: str = ""                    # path to IterResearch proof-state report (research nodes)
    proof_path: str = ""                # gate-clean artifact when proved
    folder: str = ""                    # proofs/<id>
    attempts: list[dict] = field(default_factory=list)
    axioms: list[str] = field(default_factory=list)  # #print axioms when proved


# ---------- signature / decl extraction (mechanical, no model) ----------
_DECL_RE = re.compile(r"^\s*(?:noncomputable\s+|private\s+|protected\s+)*(?:theorem|lemma)\s+([A-Za-z0-9_'.]+)", re.M)
_SIG_RE = re.compile(r"\b(?:theorem|lemma)\b.*?(?=:=)", re.DOTALL)


def _main_signature(src: str) -> str:
    m = _SIG_RE.search(src)
    return m.group(0).strip() if m else ""


def _decl_names(src: str) -> list[str]:
    seen: list[str] = []
    for m in _DECL_RE.finditer(src):
        if m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


def _body_identifiers(src: str) -> set[str]:
    """Identifiers used after the first `:=` (the proof bodies) — where deps get referenced."""
    body = src.split(":=", 1)[1] if ":=" in src else src
    return set(re.findall(r"[A-Za-z_][A-Za-z0-9_'.]{2,}", body))


class DAG:
    def __init__(self, goal: str = "", nodes: dict[str, Node] | None = None):
        self.goal = goal
        self.nodes: dict[str, Node] = nodes or {}

    # ----- IO (crash-safe: write tmp + atomic replace) -----
    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"goal": self.goal, "nodes": {k: asdict(v) for k, v in self.nodes.items()}}
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp, path)

    @classmethod
    def load(cls, path: Path) -> "DAG":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        nodes = {k: Node(**v) for k, v in data.get("nodes", {}).items()}
        return cls(goal=data.get("goal", ""), nodes=nodes)

    # ----- seeding from the existing proofs/ tree -----
    @classmethod
    def seed_from_proofs(cls, project_root: Path, goal: str = "") -> "DAG":
        proofs = Path(project_root) / "proofs"
        raw: dict[str, dict] = {}
        for d in sorted(proofs.iterdir()):
            attempt = d / "attempt.lean"
            if not (d.is_dir() and attempt.exists()):
                continue
            src = attempt.read_text(errors="ignore")
            decls = _decl_names(src)
            raw[d.name] = {
                "src": src,
                "decls": decls,
                "main": decls[-1] if decls else d.name,  # primary target = last top-level decl
                "sig": _main_signature(src),
                "open": has_sorry(src),
                "body_ids": _body_identifiers(src),
            }
        # decl-name -> node id (for dep recovery); skip ultra-common short names already filtered (>2 chars)
        decl_owner: dict[str, str] = {}
        for nid, r in raw.items():
            for name in r["decls"]:
                decl_owner.setdefault(name, nid)
        nodes: dict[str, Node] = {}
        for nid, r in raw.items():
            deps = sorted({decl_owner[name] for name in r["body_ids"]
                           if name in decl_owner and decl_owner[name] != nid})
            nodes[nid] = Node(
                id=nid, statement=r["src"], status=("open" if r["open"] else "proved"),
                deps=deps, main_decl=r["main"], provides=r["decls"],
                folder=f"proofs/{nid}",
                proof_path=("" if r["open"] else f"proofs/{nid}/attempt.lean"),
            )
        dag = cls(goal=goal, nodes=nodes)
        dag.goal = dag.resolve_goal(goal)
        dag._compute_depths()
        return dag

    def resolve_goal(self, goal: str) -> str:
        """Map a goal given as a theorem name to its node id (folders are named differently)."""
        if not goal or goal in self.nodes:
            return goal
        for nid, n in self.nodes.items():
            if n.main_decl == goal or goal in n.provides:
                return nid
        return goal  # unresolved; summary will flag it

    # ----- graph ops -----
    def _compute_depths(self) -> None:
        memo: dict[str, int] = {}
        def depth(nid: str, stack: frozenset[str]) -> int:
            if nid in memo:
                return memo[nid]
            if nid in stack:               # cycle guard (shouldn't happen): break it
                return 0
            deps = [d for d in self.nodes[nid].deps if d in self.nodes]
            d = 0 if not deps else 1 + max(depth(x, stack | {nid}) for x in deps)
            memo[nid] = d
            return d
        for nid, node in self.nodes.items():
            node.depth = depth(nid, frozenset())

    def proved(self, nid: str) -> bool:
        return nid in self.nodes and self.nodes[nid].status == "proved"

    def ready(self, nid: str) -> bool:
        """An open node is ready iff every dep (that exists in the DAG) is proved."""
        n = self.nodes[nid]
        return n.status in {"open", "context", "planning", "proving"} and \
            all(self.proved(d) for d in n.deps if d in self.nodes)

    def frontier(self) -> list[str]:
        return [nid for nid in self.nodes if self.ready(nid)]

    def critical_path(self, root: str | None = None) -> list[str]:
        """Longest chain of NOT-proved nodes ending at root (or the deepest node)."""
        root = root or self.goal or max(self.nodes, key=lambda n: self.nodes[n].depth, default="")
        if root not in self.nodes:
            return []
        path: list[str] = []
        cur = root
        seen: set[str] = set()
        while cur and cur not in seen:
            seen.add(cur)
            if not self.proved(cur):
                path.append(cur)
            unproved = [d for d in self.nodes[cur].deps if d in self.nodes and not self.proved(d)]
            if not unproved:
                break
            cur = max(unproved, key=lambda n: self.nodes[n].depth)
        return path

    def axiom_rollup(self, root: str | None = None) -> tuple[bool, list[str]]:
        """Root is closed iff its whole dep-closure is proved and every node's axioms ⊆ standard."""
        root = root or self.goal
        if root not in self.nodes:
            return False, ["unknown root"]
        clo: set[str] = set()
        stack = [root]
        while stack:
            nid = stack.pop()
            if nid in clo or nid not in self.nodes:
                continue
            clo.add(nid)
            stack.extend(self.nodes[nid].deps)
        bad: list[str] = []
        for nid in clo:
            n = self.nodes[nid]
            if n.status != "proved":
                bad.append(f"{nid}:{n.status}")
            for ax in n.axioms:
                if ax not in STD_AXIOMS:
                    bad.append(f"{nid}:axiom:{ax}")
        return (not bad), bad

    def summary(self) -> str:
        by: dict[str, int] = {}
        for n in self.nodes.values():
            by[n.status] = by.get(n.status, 0) + 1
        edges = sum(len(n.deps) for n in self.nodes.values())
        leaves = [nid for nid, n in self.nodes.items() if not n.deps]
        roots = [nid for nid in self.nodes
                 if not any(nid in m.deps for m in self.nodes.values())]
        lines = [f"goal: {self.goal or '(unset)'}",
                 f"nodes: {len(self.nodes)}  edges: {edges}  "
                 f"max-depth: {max((n.depth for n in self.nodes.values()), default=0)}",
                 f"status: {by}",
                 f"frontier (ready): {len(self.frontier())}",
                 f"roots (nothing depends on them): {len(roots)}  leaves (no deps): {len(leaves)}"]
        if self.goal:
            ok, bad = self.axiom_rollup()
            lines.append(f"goal closed: {ok}" + ("" if ok else f"  (blockers: {len(bad)})"))
            cp = self.critical_path()
            lines.append(f"critical path ({len(cp)}): " + " -> ".join(cp[:8]) + ("…" if len(cp) > 8 else ""))
        return "\n".join(lines)


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("seed")
    s.add_argument("--root", default=str(Path.home() / "projects" / "lean-runtime-analysis"))
    s.add_argument("--goal", default="")
    s.add_argument("--out", default=None, help="dag.json path (default <root>/.mathprover/dag/dag.json)")
    sh = sub.add_parser("show")
    sh.add_argument("--dag", required=True)
    a = ap.parse_args()
    if a.cmd == "seed":
        root = Path(a.root)
        out = Path(a.out) if a.out else root / ".mathprover" / "dag" / "dag.json"
        dag = DAG.seed_from_proofs(root, goal=a.goal)
        dag.save(out)
        print(f"seeded {len(dag.nodes)} nodes -> {out}\n")
        print(dag.summary())
    elif a.cmd == "show":
        print(DAG.load(Path(a.dag)).summary())


if __name__ == "__main__":
    main()
