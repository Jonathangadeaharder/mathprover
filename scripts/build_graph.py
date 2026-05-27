#!/usr/bin/env python3
"""
build_graph.py — Indexer that produces .mathprover/graph.json from source.

Scans:
  - <project>/**/*.lean   for theorems, lemmas, definitions, axioms
  - <project>/**/*.tex    for paper blocks (optional, if a paper dir exists)
  - .mathprover/meta.json for project metadata + foundations + paperBlocks

Decorator format (inside Lean docstrings `/-- ... -/`):

    /--
    @paper <Paper-Label>          (e.g. "Lemma 7.5")
    @paper-id <node-id>           (override; defaults to first identifier)
    @paper-file <relative path>
    @paper-section <section>
    @uses-defs def_A, def_B
    @depends-on node_id_1, node_id_2
    @importance 0.8               (0..1 — defaults from kind)
    @difficulty easy|medium|hard
    @capstone                     (flag)
    -/
    theorem mutation_prob_lower_bound ... := by sorry

Definitions: same docstring tags, plus
    @def-id def_SeparableGame
    @kind structure|def|inductive|abbrev|instance|class|notation

Output: <project>/.mathprover/graph.json matching schema in
mathprover-ui/src/lib/types.ts (ProjectData).

Usage:
    python3 scripts/build_graph.py [--root <path>] [--strict]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ---- regex ------------------------------------------------------------------

# Match a /-- ... -/ docblock immediately preceding a Lean declaration.
DOCBLOCK_RE = re.compile(r"/--(.*?)-/\s*", re.DOTALL)
DECL_RE = re.compile(
    r"^(?P<mods>(?:@\[[^\]]*\]\s*|private\s+|protected\s+|noncomputable\s+)*)?"
    r"(?P<kind>theorem|lemma|def|abbrev|structure|inductive|instance|class|axiom|opaque)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_'\.]*)",
    re.MULTILINE,
)
SORRY_RE = re.compile(r"\bsorry\b")
TAG_RE = re.compile(r"^@([\w-]+)\s*(.*)$")


@dataclass
class Decl:
    kind: str
    name: str
    file: str
    line: int
    docblock: str
    body: str            # source from decl head until the next decl or EOF
    has_sorry: bool


# ---- helpers ----------------------------------------------------------------

def parse_docblock(doc: str) -> dict[str, Any]:
    """Parse `@tag value` lines out of a docstring."""
    tags: dict[str, Any] = {}
    description_lines: list[str] = []
    in_tags = False
    for raw in doc.splitlines():
        line = raw.strip().lstrip("*").strip()
        m = TAG_RE.match(line)
        if m:
            in_tags = True
            tag, value = m.group(1), m.group(2).strip()
            if tag in ("uses-defs", "depends-on"):
                tags[tag] = [s.strip() for s in value.split(",") if s.strip()]
            elif tag == "capstone":
                tags[tag] = True
            else:
                tags[tag] = value
        elif not in_tags and line:
            description_lines.append(line)
    if description_lines and "description" not in tags:
        tags["description"] = " ".join(description_lines)
    return tags


def scan_lean_file(path: Path, project_root: Path) -> list[Decl]:
    """Extract declarations + their preceding docblocks from a .lean file."""
    src = path.read_text(encoding="utf-8")
    rel = str(path.relative_to(project_root))

    # Find every declaration head and its line.
    decls: list[Decl] = []
    decl_matches = list(DECL_RE.finditer(src))
    for idx, m in enumerate(decl_matches):
        kind = m.group("kind")
        name = m.group("name")
        head_start = m.start()
        line_no = src.count("\n", 0, head_start) + 1

        # Find the docblock that ends just before this decl head (allowing
        # only whitespace between).
        doc = ""
        # Search backwards from head_start for the last "-/" before any non-ws
        prefix = src[:head_start]
        # Look at the tail of prefix.
        tail = prefix.rstrip()
        if tail.endswith("-/"):
            # Find the matching /--
            open_idx = tail.rfind("/--")
            if open_idx != -1:
                doc = tail[open_idx + 3 : -2]

        # Body: from head start to next decl or EOF.
        body_end = decl_matches[idx + 1].start() if idx + 1 < len(decl_matches) else len(src)
        body = src[head_start:body_end]

        decls.append(
            Decl(
                kind=kind,
                name=name,
                file=rel,
                line=line_no,
                docblock=doc,
                body=body,
                has_sorry=bool(SORRY_RE.search(body)),
            )
        )
    return decls


def slug_node_id(d: Decl, tags: dict[str, Any]) -> str:
    if "paper-id" in tags:
        return tags["paper-id"]
    # Fall back to L<line>_<name> for sorry-bearing decls so they match the
    # convention used by the existing proof-tree dashboard.
    if d.has_sorry:
        return f"L{d.line}_{d.name}"
    return d.name


def slug_def_id(d: Decl, tags: dict[str, Any]) -> str:
    return tags.get("def-id") or f"def_{d.name}"


def status_for(d: Decl, tags: dict[str, Any]) -> str:
    explicit = tags.get("status", "").upper()
    if explicit in {"PROVEN", "SORRIES", "PROGRESS", "FAILED", "BLOCKED", "READY", "UNEXPLORED"}:
        return explicit
    if d.kind == "axiom":
        return "PROVEN"
    if d.has_sorry:
        return "SORRIES"
    return "PROVEN"


def importance_default(kind: str) -> float:
    return {
        "theorem": 0.8,
        "lemma": 0.6,
        "def": 0.5,
        "structure": 0.55,
        "axiom": 0.95,
    }.get(kind, 0.5)


def build_node(d: Decl) -> dict[str, Any] | None:
    tags = parse_docblock(d.docblock)
    # Strict decorator mode: every emitted node MUST carry @paper-id or @paper.
    # No silent auto-discovery — declarations without decorators are skipped
    # entirely so the graph is fully deterministic and reviewable.
    if "paper-id" not in tags and "paper" not in tags:
        return None
    # A declaration carrying @def-id is a definition, not a theorem node.
    if "def-id" in tags:
        return None
    nid = slug_node_id(d, tags)
    node = {
        "id": nid,
        "paper_id": tags.get("paper", d.name),
        "paper_name": tags.get("name", tags.get("description", d.name)),
        "lean_theorem": d.name,
        "lean_file": d.file,
        "lean_line": d.line,
        "paper_file": tags.get("paper-file", ""),
        "paper_section": tags.get("paper-section", ""),
        "status": status_for(d, tags),
        "depends_on": tags.get("depends-on", []),
        "uses_defs": tags.get("uses-defs", []),
        "importance": float(tags.get("importance", importance_default(d.kind))),
        "difficulty": tags.get("difficulty", "medium"),
        "confidence": float(tags["confidence"]) if "confidence" in tags else (1.0 if not d.has_sorry else 0.5),
        "tokens_spent": 0,
        "attempts": 0,
    }
    if "capstone" in tags:
        node["isCapstone"] = True
    if "paper-stmt" in tags:
        node["paper_stmt"] = tags["paper-stmt"]
    if d.has_sorry:
        node["sorries"] = [
            {"name": d.name, "desc": tags.get("description", ""), "implies": tags.get("implies", "")}
        ]
    return node


def build_definition(d: Decl) -> dict[str, Any] | None:
    tags = parse_docblock(d.docblock)
    # Strict mode: only declarations carrying an explicit @def-id are emitted.
    if "def-id" not in tags:
        return None
    did = slug_def_id(d, tags)
    return {
        "id": did,
        "name": tags.get("name", d.name),
        "kind": tags.get("kind", d.kind if d.kind != "lemma" else "def"),
        "lean_name": d.name,
        "lean_file": d.file,
        "lean_line": d.line,
        "paper_label": tags.get("paper"),
        "paper_section": tags.get("paper-section"),
        "paper_file": tags.get("paper-file"),
        "signature": tags.get("signature"),
        "description": tags.get("description", ""),
        "depends_on": tags.get("depends-on", []),
    }


def infer_proof_folder(project_root: Path, theorem: str, node_id: str) -> str | None:
    proofs = project_root / "proofs"
    if not proofs.is_dir():
        return None
    for folder in proofs.iterdir():
        if not folder.is_dir():
            continue
        if theorem and theorem in folder.name:
            return folder.name
        if node_id in folder.name:
            return folder.name
    return None


def parse_worker_state(status_path: Path) -> str | None:
    if not status_path.exists():
        return None
    m = re.search(r"^state:\s*(\S+)", status_path.read_text(encoding="utf-8"), re.MULTILINE)
    return m.group(1) if m else None


def enrich_nodes(project_root: Path, nodes: list[dict[str, Any]]) -> None:
    for node in nodes:
        folder = node.get("proof_folder") or infer_proof_folder(
            project_root, node.get("lean_theorem", ""), node.get("id", "")
        )
        if folder:
            node["proof_folder"] = folder
            ws = parse_worker_state(project_root / "proofs" / folder / "status.md")
            if ws:
                node["worker_state"] = ws


def merge_run_history(project_root: Path, graph: dict[str, Any]) -> None:
    """Attach attemptsLog from .mathprover/runs/ if index_runs is available."""
    index_script = project_root / "scripts" / "index_runs.py"
    if not index_script.exists():
        return
    import subprocess

    proc = subprocess.run(
        [sys.executable, str(index_script), "--root", str(project_root), "--graph"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        cwd=project_root,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return
    enriched = json.loads(proc.stdout)
    attempts_by_id = {n["id"]: n.get("attemptsLog", []) for n in enriched.get("nodes", [])}
    for node in graph.get("nodes", []):
        logs = attempts_by_id.get(node.get("id", ""), [])
        if logs:
            node["attemptsLog"] = logs
            node["attempts"] = len(logs)
    if enriched.get("activeAgent"):
        graph["activeAgent"] = enriched["activeAgent"]


# ---- main -------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="Project root (containing the .lean files).")
    ap.add_argument("--out", default=None, help="Output path (default <root>/.mathprover/graph.json).")
    ap.add_argument("--meta", default=None, help="Path to meta.json overlay (default <root>/.mathprover/meta.json).")
    ap.add_argument("--strict", action="store_true", help="Exit non-zero on validation errors.")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    out_path = Path(args.out) if args.out else root / ".mathprover" / "graph.json"
    meta_path = Path(args.meta) if args.meta else root / ".mathprover" / "meta.json"

    # Scan all *.lean except cache/build dirs.
    EXCLUDES = {".lake", ".worktrees", ".git", "proofs", "examples"}
    lean_files = [
        p for p in root.rglob("*.lean")
        if not any(part in EXCLUDES for part in p.parts) and not p.name.endswith(".bak.lean")
    ]
    print(f"[build_graph] scanning {len(lean_files)} .lean files under {root}", file=sys.stderr)

    nodes: list[dict[str, Any]] = []
    definitions: list[dict[str, Any]] = []
    errors: list[str] = []

    orphan_sorries: list[str] = []
    orphan_axioms: list[str] = []
    for p in sorted(lean_files):
        for d in scan_lean_file(p, root):
            node = build_node(d)
            if node:
                nodes.append(node)
            elif d.has_sorry:
                orphan_sorries.append(f"{d.file}:{d.line}  {d.name}")
            elif d.kind == "axiom":
                orphan_axioms.append(f"{d.file}:{d.line}  {d.name}")
            df = build_definition(d)
            if df:
                definitions.append(df)

    for s in orphan_sorries:
        errors.append(f"undecorated sorry: {s} — add /-- @paper-id <id> ... -/")
    for a in orphan_axioms:
        errors.append(f"undecorated axiom: {a} — add /-- @paper-id <id> ... -/")

    # Validate uses_defs / depends_on references.
    node_ids = {n["id"] for n in nodes}
    def_ids = {d["id"] for d in definitions}
    for n in nodes:
        for dep in n.get("depends_on", []):
            if dep not in node_ids:
                errors.append(f"node {n['id']}: depends_on '{dep}' not found among nodes")
        for did in n.get("uses_defs", []):
            if did not in def_ids:
                errors.append(f"node {n['id']}: uses_defs '{did}' not found among definitions")
    for df in definitions:
        for dep in df.get("depends_on", []) or []:
            if dep not in def_ids:
                errors.append(f"definition {df['id']}: depends_on '{dep}' not found among definitions")

    # Merge with manual overlay (foundations, paperBlocks, project metadata).
    overlay: dict[str, Any] = {}
    if meta_path.exists():
        overlay = json.loads(meta_path.read_text(encoding="utf-8"))
        print(f"[build_graph] merged overlay {meta_path}", file=sys.stderr)

    project = overlay.get("project") or {
        "name": root.name,
        "path": str(root),
        "paper": "",
        "authors": "",
        "venue": "",
        "capstone": next((n["id"] for n in nodes if n.get("isCapstone")), ""),
        "lastVerified": "",
    }

    graph = {
        "project": project,
        "recents": overlay.get("recents", []),
        "nodes": nodes,
        "definitions": definitions,
        "foundations": overlay.get("foundations", []),
        "paperBlocks": overlay.get("paperBlocks", []),
        "leanBlocks": overlay.get("leanBlocks", []),
        "terms": overlay.get("terms", {}),
        "failures": overlay.get("failures", []),
        "activeAgent": overlay.get("activeAgent"),
    }

    enrich_nodes(root, graph["nodes"])
    if not graph["nodes"]:
        print("[build_graph] no decorated nodes — run scripts/bootstrap_graph.py", file=sys.stderr)
    else:
        merge_run_history(root, graph)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"[build_graph] wrote {out_path}  ({len(nodes)} nodes, {len(definitions)} defs, "
        f"{sum(1 for n in nodes if n['status']=='SORRIES')} open sorries)",
        file=sys.stderr,
    )

    if errors:
        for e in errors:
            print(f"[build_graph] VALIDATION: {e}", file=sys.stderr)
        if args.strict:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
