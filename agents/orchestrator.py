#!/usr/bin/env python3
"""Frontier scheduler over the persistent proof-DAG (BIG_PROBLEMS_DESIGN.md §2).

Walks `dag.json` turn-based, batching by model to amortize residency swaps across the WHOLE frontier
(all gemma CONTEXT, then all qwen PLAN, then all oprover PROVE, then model-free ASSEMBLE+GATE), then
persists every state change so big targets survive sessions/crashes.

Two entry points:
  --verify-only   gate every `proved` node (compile + placeholders + `#print axioms`), record the
                  axiom set, downgrade any that fail, print the axiom roll-up. NEEDS NO MODELS — pure
                  lake. Validates the DAG plumbing before any proving.
  (default)       the full batched scheduler loop (needs the local models).

Soundness is unchanged from the single-node agent: a node is `proved` ONLY via final_verify; the
root is closed ONLY if the whole dep-closure is proved with axioms ⊆ standard (dag.axiom_rollup).
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

AGENTS = Path(__file__).resolve().parent
sys.path.insert(0, str(AGENTS))
import agent as AG  # noqa: E402  (phase fns: plan_phase, prove_phase, assemble_and_gate, _axiom_backed, _gather_context)
import dag as D  # noqa: E402
import deep_research as DR  # noqa: E402
import models as M  # noqa: E402
import pipeline as P  # noqa: E402
import residency  # noqa: E402
import tools as T  # noqa: E402
from lean_pipeline import axiom_check, final_verify_attempt  # noqa: E402

_AX_RE = re.compile(r"depends on axioms:\s*\[([^\]]*)\]")
MAX_DEPTH = (
    4  # max recursive-decomposition depth before a hard leaf is blocked (→ research, step 4)
)


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", s)[:40]


def _dag_path(root: Path) -> Path:
    return root / ".mathprover" / "dag" / "dag.json"


def _attempt_file(root: Path, node: D.Node) -> Path:
    return root / (node.folder or f"proofs/{node.id}") / "attempt.lean"


def _parse_axioms(output: str) -> list[str]:
    m = _AX_RE.search(output)
    if not m:
        return []
    return [a.strip() for a in m.group(1).split(",") if a.strip()]


def _ctx(root: Path, node: D.Node) -> T.Ctx:
    af = _attempt_file(root, node)
    return T.Ctx(
        project_root=root,
        node=node.id,
        proof_dir=af.parent,
        attempt_file=af,
        goal_src=node.statement or (af.read_text(errors="ignore") if af.exists() else ""),
    )


# ---------------- verify-only (no models) ----------------
def verify_only(root: Path, dag: D.DAG) -> None:
    P.init_log(root)
    dpath = _dag_path(root)
    proved = [nid for nid, n in dag.nodes.items() if n.status == "proved"]
    P.LOG.info("verify-only: gating %d proved nodes (no models)", len(proved))
    for nid in proved:
        n = dag.nodes[nid]
        af = _attempt_file(root, n)
        if not af.exists():
            P.LOG.warning("  %s: no attempt.lean -> downgrade open", nid)
            n.status, n.proof_path = "open", ""
            dag.save(dpath)
            continue
        ok, msg = final_verify_attempt(project_root=root, lean_file=af, theorem=n.main_decl or None)
        if ok:
            axout = axiom_check(project_root=root, lean_file=af, theorem=n.main_decl or None)
            n.axioms = _parse_axioms(axout.combined) or D.STD_AXIOMS
            n.proof_path = (n.folder or f"proofs/{nid}") + "/attempt.lean"
            P.LOG.info("  %s: GATE CLEAN  axioms=%s", nid, n.axioms)
        else:
            n.status, n.proof_path = "open", ""
            n.attempts.append(
                {
                    "ts": int(time.time()),
                    "verdict": "gate_fail",
                    "feedback_head": msg.splitlines()[0][:160] if msg else "",
                }
            )
            P.LOG.info(
                "  %s: GATE FAIL -> open :: %s", nid, msg.splitlines()[0][:120] if msg else ""
            )
        dag.save(dpath)
    print("\n=== verify-only result ===")
    print(dag.summary())
    if dag.goal:
        ok, bad = dag.axiom_rollup()
        if not ok:
            print(f"\ngoal NOT closed; blockers ({len(bad)}): " + ", ".join(bad[:12]))


# ---------------- decomposition (grow the DAG) ----------------
def materialize_children(
    root: Path, dag: D.DAG, parent_id: str, sublemmas: list[dict], parent_proof: str
) -> list[str]:
    """Turn a verified split into child nodes; wire parent.deps + parent_proof. Each child gets its
    own proofs/<id>/attempt.lean (self-contained sorry-lemma) so the gate works on it like any node."""
    parent = dag.nodes[parent_id]
    imports = P._imports_of(parent.statement)
    child_ids: list[str] = []
    for sub in sublemmas:
        name = sub.get("name") or "lemma"
        stmt = sub.get("statement", "").strip()
        if not stmt:
            continue
        cid = f"{parent_id}__{_slug(name)}"
        src = stmt if stmt.lstrip().startswith(("import ", "open ")) else (imports + "\n\n" + stmt)
        af = root / "proofs" / cid / "attempt.lean"
        af.parent.mkdir(parents=True, exist_ok=True)
        af.write_text(src, encoding="utf-8")
        decls = D._decl_names(src)
        dag.nodes[cid] = D.Node(
            id=cid,
            statement=src,
            status="open",
            main_decl=(decls[-1] if decls else name),
            provides=decls,
            folder=f"proofs/{cid}",
        )
        child_ids.append(cid)
    parent.deps = sorted(set(parent.deps) | set(child_ids))
    parent.parent_proof = parent_proof
    parent.status = "planning"  # waiting on children; assembled when all proved
    dag._compute_depths()
    return child_ids


def assemble_parent(root: Path, dag: D.DAG, parent_id: str) -> tuple[bool, str]:
    """All deps proved → splice their proofs + parent_proof, gate the parent (model-free)."""
    parent = dag.nodes[parent_id]
    bodies = []
    for d in parent.deps:
        if d not in dag.nodes:
            continue
        pf = root / dag.nodes[d].proof_path
        if pf.exists():
            bodies.append(AG._strip_imports(pf.read_text(errors="ignore")))
    pp = (parent.parent_proof or "").strip()
    if not pp:
        return False, "no parent_proof"
    if not pp.startswith("by"):
        pp = "by " + pp
    cand = (
        P._imports_of(parent.statement)
        + "\n\n"
        + "\n\n".join(bodies)
        + "\n\n"
        + f"{AG._node_statement(parent.statement)} := {pp}\n"
    )
    return AG._gate(_ctx(root, parent), cand)


# ---------------- batched scheduler (needs models) ----------------
def schedule(
    root: Path,
    dag: D.DAG,
    *,
    max_hours: float,
    max_nodes: int,
    allow_research: bool,
    research_threads: int = 3,
    research_rounds: int = 4,
) -> None:
    logpath = P.init_log(root)
    dpath = _dag_path(root)
    deadline = (time.time() + max_hours * 3600.0) if max_hours > 0 else None
    P.init_progress(
        root,
        task=f"dag:{dag.goal or 'goal'}",
        mode="orchestrator",
        budget=(f"{max_hours}h" if deadline else f"{max_nodes} nodes"),
    )
    residency.free()
    closed = 0
    while closed < max_nodes:
        if deadline and time.time() > deadline:
            P.LOG.info("orchestrator: wall-clock deadline")
            break
        if dag.goal and dag.proved(dag.goal):
            P.LOG.info("orchestrator: GOAL PROVED")
            break
        frontier = dag.frontier()
        if not frontier:
            P.LOG.info("orchestrator: frontier empty")
            break
        # split frontier: parents ready to ASSEMBLE (decomposed, deps proved) vs LEAVES to prove
        parents = [nid for nid in frontier if dag.nodes[nid].deps and dag.nodes[nid].parent_proof]
        leaves = [nid for nid in frontier if nid not in parents]
        P.LOG.info("=== sweep: %d assemble-ready, %d leaves ===", len(parents), len(leaves))
        progressed = False

        # ---- ASSEMBLE ready parents (model-free) ----
        for nid in parents:
            ok, msg = assemble_parent(root, dag, nid)
            n = dag.nodes[nid]
            if ok:
                af = _attempt_file(root, n)
                axout = axiom_check(project_root=root, lean_file=af, theorem=n.main_decl or None)
                n.axioms = _parse_axioms(axout.combined) or D.STD_AXIOMS
                n.status, n.proof_path = "proved", f"proofs/{nid}/attempt.lean"
                closed += 1
                progressed = True
                P.LOG.info("  %s: ASSEMBLED+PROVED (axioms=%s)", nid, n.axioms)
            else:
                n.status = "open"  # assembly failed; re-plan as a leaf next sweep
                P.LOG.info(
                    "  %s: assemble FAIL :: %s",
                    nid,
                    (msg or "").splitlines()[0][:120] if msg else "",
                )
            dag.save(dpath)

        if leaves:
            # ---- CONTEXT batch (gemma, PydanticAI context agent) ----
            residency.use(M.CONTEXT_MODEL)
            P.prog(root, "CONTEXT batch (gemma)", phase="CONTEXT", model=M.CONTEXT_MODEL)
            ctxs: dict[str, T.Ctx] = {}
            for nid in leaves:
                c = _ctx(root, dag.nodes[nid])
                if not dag.nodes[nid].brief:
                    AG._gather_context(c)
                    dag.nodes[nid].brief, dag.nodes[nid].premises = c.brief, c.premises
                    dag.save(dpath)
                else:
                    c.brief, c.premises = dag.nodes[nid].brief, dag.nodes[nid].premises
                ctxs[nid] = c

            # ---- PLAN batch (qwen) ----
            residency.use(M.PLANNER_MODEL)
            P.prog(root, "PLAN batch (qwen)", phase="PLAN", model=M.PLANNER_MODEL)
            plans: dict[str, dict] = {}
            for nid in leaves:
                plan = AG.plan_phase(ctxs[nid], feedback="")
                if AG._axiom_backed(ctxs[nid]) and plan.get("mode") != "refute_then_prove":
                    plan["mode"] = "refute_then_prove"
                plans[nid] = plan

            # ---- PROVE batch (oprover) ----
            residency.use(M.PROVER_MODEL)
            P.prog(root, "PROVE batch (oprover)", phase="PROVE", model=M.PROVER_MODEL)
            for nid in leaves:
                n = dag.nodes[nid]
                status, proved_leaves, fb = AG.prove_phase(ctxs[nid], plans[nid], deadline)
                if status == "FALSE":
                    n.status = "refuted"
                    dag.save(dpath)
                    progressed = True
                    continue
                ok, msg = AG.assemble_and_gate(ctxs[nid], plans[nid], proved_leaves)
                n.attempts.append(
                    {
                        "ts": int(time.time()),
                        "model": M.PROVER_MODEL,
                        "verdict": "proved" if ok else "open",
                        "feedback_head": (msg or fb).splitlines()[0][:160] if (msg or fb) else "",
                    }
                )
                if ok:
                    af = _attempt_file(root, n)
                    axout = axiom_check(
                        project_root=root, lean_file=af, theorem=n.main_decl or None
                    )
                    n.axioms = _parse_axioms(axout.combined) or D.STD_AXIOMS
                    n.status, n.proof_path = "proved", f"proofs/{nid}/attempt.lean"
                    closed += 1
                    progressed = True
                    P.LOG.info("  %s: PROVED (axioms=%s)", nid, n.axioms)
                    dag.save(dpath)
                    continue
                # ---- stuck leaf -> DECOMPOSE (grow the DAG) ----
                split = None
                pl = plans[nid]
                if n.depth < MAX_DEPTH:
                    if not pl.get("direct", True) and pl.get("leaves") and pl.get("parent_proof"):
                        cand_split = {
                            "sublemmas": [
                                {
                                    "name": leaf.get("name", f"h{i}"),
                                    "statement": leaf.get("goal_spec", ""),
                                }
                                for i, leaf in enumerate(pl["leaves"])
                            ],
                            "parent_proof": pl["parent_proof"],
                        }
                        if P.verify_split(n.statement, cand_split, root):
                            split = cand_split
                    if split is None:
                        ps = P.propose_split(n.statement, n.premises)
                        if ps.get("sublemmas") and P.verify_split(n.statement, ps, root):
                            split = ps
                if split:
                    kids = materialize_children(
                        root, dag, nid, split["sublemmas"], split["parent_proof"]
                    )
                    progressed = True
                    P.LOG.info("  %s: DECOMPOSED -> %s", nid, kids)
                elif allow_research:
                    # ---- DEEP-RESEARCH (§5, local; no cloud) ----
                    n.status = "researching"
                    dag.save(dpath)
                    res = DR.deep_research(
                        ctxs[nid],
                        root,
                        threads=research_threads,
                        rounds=research_rounds,
                        deadline=deadline,
                    )
                    n.report = DR.write_report(root, nid, res.get("reports", []))
                    residency.use(M.PROVER_MODEL)  # back to prover residency for the sweep
                    if res["status"] == "proved":
                        ok, _ = AG._gate(
                            ctxs[nid], res["proof"]
                        )  # write node attempt.lean + final_verify
                        if ok:
                            af = _attempt_file(root, n)
                            axout = axiom_check(
                                project_root=root, lean_file=af, theorem=n.main_decl or None
                            )
                            n.axioms = _parse_axioms(axout.combined) or D.STD_AXIOMS
                            n.status, n.proof_path = "proved", f"proofs/{nid}/attempt.lean"
                            closed += 1
                            progressed = True
                            P.LOG.info("  %s: PROVED via deep-research (axioms=%s)", nid, n.axioms)
                        else:
                            n.status = "blocked"
                    elif res["status"] == "split":
                        kids = materialize_children(
                            root, dag, nid, res["split"]["sublemmas"], res["split"]["parent_proof"]
                        )
                        progressed = True
                        P.LOG.info("  %s: deep-research DECOMPOSED -> %s", nid, kids)
                    else:
                        n.status = "blocked"
                        P.LOG.info(
                            "  %s: BLOCKED (deep-research exhausted; report %s)", nid, n.report
                        )
                else:
                    n.status = "blocked"
                    P.LOG.info("  %s: BLOCKED (no valid split; research off)", nid)
                dag.save(dpath)

        if not progressed:
            P.LOG.info("orchestrator: no progress this sweep -> stop")
            break
    residency.free()
    print("\n=== orchestrator result ===")
    print(dag.summary())
    print(f"(log: {logpath})")


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path.home() / "projects" / "lean-runtime-analysis"))
    ap.add_argument(
        "--goal", default="", help="root node id or theorem name (seeds if no dag.json)"
    )
    ap.add_argument("--verify-only", action="store_true", help="gate proved nodes; no models")
    ap.add_argument("--max-hours", type=float, default=0.0)
    ap.add_argument(
        "--max-nodes", type=int, default=20, help="stop after this many newly-closed nodes"
    )
    ap.add_argument(
        "--allow-research", action="store_true", help="enable local deep-research on hard nodes"
    )
    ap.add_argument(
        "--research-threads", type=int, default=3, help="Heavy-mode angle-diverse threads"
    )
    ap.add_argument("--research-rounds", type=int, default=4, help="IterResearch rounds per thread")
    a = ap.parse_args()
    root = Path(a.root)
    dpath = _dag_path(root)
    if dpath.exists():
        dag = D.DAG.load(dpath)
        if a.goal:
            dag.goal = dag.resolve_goal(a.goal)
    else:
        dag = D.DAG.seed_from_proofs(root, goal=a.goal)
        dag.save(dpath)
        print(f"seeded {len(dag.nodes)} nodes -> {dpath}")
    if a.verify_only:
        verify_only(root, dag)
    else:
        schedule(
            root,
            dag,
            max_hours=a.max_hours,
            max_nodes=a.max_nodes,
            allow_research=a.allow_research,
            research_threads=a.research_threads,
            research_rounds=a.research_rounds,
        )


if __name__ == "__main__":
    main()
