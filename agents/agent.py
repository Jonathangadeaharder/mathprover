#!/usr/bin/env python3
"""Local-Aristotle orchestrator — PHASE-BATCHED, turn-based (plan: PydanticAI native).

One machine, three models that cannot co-reside. We batch work per model into phases so model swaps
(~10-30s each, via residency.py) are amortized:

  CONTEXT  (gemma)   gather_context -> compact brief + curated premises (cached on ctx)
  [loop, bounded by --max-steps outer iterations / --max-hours wall clock]
    PLAN   (qwen)    PydanticAI planner agent (tools + structured Plan output) — replaces hand ReAct loop
    PROVE  (oprover) refute (if flagged) then prove every leaf in one resident burst
    ASSEMBLE+GATE    (model-free) build candidate -> edit_attempt (statement-preserved + final_verify)
                     CLEAN -> PROVED. else feed Lean feedback into the next PLAN (= REASSESS).

The gate (tools.t_edit_attempt -> final_verify_attempt) is the ONLY path to PROVED — a tool-driving
model can never weaken the statement or smuggle an axiom past it.

CLI:  python3 agent.py --node <NODE> [--max-hours H] [--max-steps N] [--allow-cloud-escalation]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

AGENTS = Path(__file__).resolve().parent
sys.path.insert(0, str(AGENTS))
import models as M  # noqa: E402
import pai_agents  # noqa: E402
import pipeline as P  # noqa: E402
import residency  # noqa: E402
import schemas  # noqa: E402
import tools as T  # noqa: E402


def _axiom_backed(ctx: T.Ctx) -> bool:
    txt = ctx.attempt_file.read_text(errors="ignore") if ctx.attempt_file.exists() else ctx.goal_src
    ps = ctx.proof_dir / "paper_source.md"
    if ps.exists():
        txt += ps.read_text(errors="ignore")
    low = (txt + ctx.node).lower()
    return any(
        k in low for k in ("quarantine", "axiom", "is_false", "trusted", "level_based_theorem")
    )


def _strip_imports(text: str) -> str:
    return "\n".join(
        ln for ln in text.splitlines() if not ln.strip().startswith(("import ", "open "))
    )


def _node_statement(goal_src: str) -> str:
    sig = P._goal_signature(goal_src)
    return sig.strip() if sig else goal_src.split(":=", 1)[0].strip()


def _gather_context(ctx: T.Ctx) -> None:
    """CONTEXT phase via PydanticAI context agent (gemma). Builds brief + curated premises on ctx."""
    attempt = (
        ctx.attempt_file.read_text(errors="ignore") if ctx.attempt_file.exists() else ctx.goal_src
    )
    paper = ""
    ps = ctx.proof_dir / "paper_source.md"
    if ps.exists():
        paper = ps.read_text(errors="ignore")[:8000]
    defs = P.definitions_for_goal(ctx.goal_src, ctx.project_root)
    candidates = T._lexical_prefilter(ctx.goal_src, P.project_lemma_corpus(ctx.project_root))
    prompt = (
        f"Goal file (proofs/{ctx.node}/attempt.lean):\n```lean\n{attempt[:6000]}\n```\n\n"
        f"Paper source notes:\n{paper or '(none)'}\n\n"
        f"In-scope definitions found in the project:\n{chr(10).join(defs) or '(none)'}\n\n"
        f"Candidate lemma signatures (pick the useful ones):\n{chr(10).join(candidates)}\n\n"
        "Focus: the sorry in this file"
    )
    try:
        ag = pai_agents.context()
        result = M.run_sync(ag, "gemma", prompt, deps=ctx, max_tokens=4096, temperature=0.2)
        out = result.output
    except Exception as e:  # noqa: BLE001
        P.LOG.warning("CONTEXT gemma PydanticAI call failed (%s) -> empty context", e)
        return
    brief, prem = out, []
    if "=== PREMISES ===" in out:
        brief, _, premblk = out.partition("=== PREMISES ===")
        prem = [
            ln.strip(" -\t")
            for ln in premblk.splitlines()
            if ln.strip() and ("theorem" in ln or "lemma" in ln)
        ][:12]
    brief = brief.replace("=== BRIEF ===", "").strip()
    ctx.brief = brief
    ctx.premises = prem


# ---------------- PLAN phase (qwen, resident; PydanticAI native) ----------------
def plan_phase(ctx: T.Ctx, feedback: str) -> dict:
    residency.use(M.PLANNER_MODEL)
    P.prog(ctx.project_root, "PLAN (qwen)", phase="PLAN", model=M.PLANNER_MODEL)
    user = (
        f"Node: {ctx.node}\nGoal:\n```lean\n{ctx.goal_src}\n```\n\n"
        f"Context brief (gemma):\n{ctx.brief or '(none)'}\n\n"
        f"Curated premises:\n{chr(10).join(ctx.premises) or '(none)'}\n\n"
        + (f"PRIOR ATTEMPT FAILED. Lean feedback to address:\n{feedback}\n\n" if feedback else "")
        + "Probe if needed, then emit the plan."
    )
    try:
        ag = pai_agents.planner()
        result = M.run_sync(ag, "qwen", user, deps=ctx, max_tokens=P.QWEN_GEN, temperature=0.3)
        plan: schemas.Plan = result.output  # type: ignore[assignment]
        P.LOG.info("PLAN: %s", plan.model_dump_json()[:300])
        return plan.model_dump()
    except Exception as e:  # noqa: BLE001
        P.LOG.warning("PLAN qwen PydanticAI call failed (%s) -> fallback direct", e)
        return {
            "mode": "prove",
            "direct": True,
            "leaves": [{"name": ctx.node, "goal_spec": ctx.goal_src, "sketch": ""}],
            "parent_proof": "",
        }


# ---------------- PROVE phase (oprover, resident burst) ----------------
def prove_phase(ctx: T.Ctx, plan: dict, deadline: float | None) -> tuple[str, dict, str]:
    """Returns (status, proved{name->text}, feedback). status in {DONE-CANDIDATE, FALSE, FAIL}."""
    residency.use(M.PROVER_MODEL)
    P.prog(ctx.project_root, "PROVE (oprover)", phase="PROVE", model=M.PROVER_MODEL)

    if plan.get("mode") == "refute_then_prove":
        neg = P.build_negation_goal(ctx.goal_src)
        if neg:
            P.prog(ctx.project_root, "refute: attempting counterexample")
            cex = P.prove_leaf(
                neg, ctx.project_root, "", ctx.premises, rounds=4, width=1, deadline=deadline
            )
            if cex:
                return "FALSE", {}, ""

    direct = plan.get("direct", True)
    leaves = plan.get("leaves") or [{"name": ctx.node, "goal_spec": ctx.goal_src, "sketch": ""}]
    if direct:  # prove the node statement itself (ignore model-supplied spec — use the real goal)
        leaves = [
            {"name": ctx.node, "goal_spec": ctx.goal_src, "sketch": leaves[0].get("sketch", "")}
        ]

    proved: dict = {}
    feedback = ""
    for leaf in leaves:
        if deadline and time.time() > deadline:
            break
        spec = leaf.get("goal_spec") or ctx.goal_src
        name = leaf.get("name", "leaf")
        P.prog(ctx.project_root, f"prove leaf {name}")
        proof = P.prove_leaf(
            spec,
            ctx.project_root,
            leaf.get("sketch", ""),
            ctx.premises,
            rounds=6,
            width=1,
            deadline=deadline,
        )
        proved[name] = proof
        if not proof:
            # REFUTE-ON-STUCK (Aristotle lesson): a model-invented helper that won't prove may be
            # MIS-STATED, not just hard (Aristotle caught + deleted its own false `faithful_active_
            # deficit` this way). Cheaply try to disprove it before REASSESS spends more budget. Sound:
            # refute only succeeds by proving the negation (gated) — a true lemma can never be refuted.
            # Skip for the direct node goal (the user's statement; axiom-backed ones are refuted upfront).
            if not direct:
                neg = P.build_negation_goal(spec)
                cex = (
                    P.prove_leaf(
                        neg,
                        ctx.project_root,
                        "",
                        ctx.premises,
                        rounds=3,
                        width=1,
                        deadline=deadline,
                    )
                    if neg
                    else None
                )
                if cex:
                    feedback += f"\nleaf {name} is FALSE (counterexample found) — DROP or RESTATE it; the decomposition is wrong."
                    P.prog(ctx.project_root, f"leaf {name} REFUTED (mis-stated)")
                    continue
            feedback += f"\nleaf {name} UNPROVED (no counterexample; likely true but hard)."
    return "DONE-CANDIDATE", proved, feedback


# ---------------- ASSEMBLE + GATE (model-free) ----------------
def assemble_and_gate(ctx: T.Ctx, plan: dict, proved: dict) -> tuple[bool, str]:
    if plan.get("direct", True):
        cand = proved.get(ctx.node)
        if not cand:
            return False, "direct leaf unproved"
        return _gate(ctx, cand)
    if any(v is None for v in proved.values()) or not proved:
        return False, "not all helper leaves proved"
    bodies = "\n\n".join(
        _strip_imports(proved[lf["name"]]) for lf in plan["leaves"] if proved.get(lf["name"])
    )
    parent_proof = (plan.get("parent_proof") or "").strip()
    if not parent_proof:
        return False, "no parent_proof to assemble helpers"
    if not parent_proof.startswith("by"):
        parent_proof = "by " + parent_proof
    cand = (
        P._imports_of(ctx.goal_src)
        + "\n\n"
        + bodies
        + "\n\n"
        + f"{_node_statement(ctx.goal_src)} := {parent_proof}\n"
    )
    return _gate(ctx, cand)


def _gate(ctx: T.Ctx, cand: str) -> tuple[bool, str]:
    """The only path to PROVED: tools.t_edit_attempt runs statement-preserved + final_verify."""
    msg = T.t_edit_attempt(ctx, cand)
    return ctx.verified_ok, msg


# ---------------- orchestrator ----------------
def run(
    node: str, project_root: Path, *, max_hours: float, max_steps: int, allow_cloud: bool
) -> str:
    proof_dir = project_root / "proofs" / node
    attempt_file = proof_dir / "attempt.lean"
    if not attempt_file.exists():
        print(f"RESULT: NOT PROVED (no proofs/{node}/attempt.lean)")
        return "UNPROVED"
    ctx = T.Ctx(
        project_root=project_root,
        node=node,
        proof_dir=proof_dir,
        attempt_file=attempt_file,
        goal_src=attempt_file.read_text(encoding="utf-8"),
        allow_cloud=allow_cloud,
    )
    logpath = P.init_log(project_root)
    deadline = (time.time() + max_hours * 3600.0) if max_hours > 0 else None
    P.init_progress(
        project_root,
        task=f"agent:{node}",
        mode="phase-batched",
        budget=(f"{max_hours}h" if deadline else f"{max_steps} iters"),
    )
    P.LOG.info(
        "=== phase-batched agent node=%s iters<=%d deadline=%s ===", node, max_steps, bool(deadline)
    )
    M.ensure_mtplx()
    residency.free()  # clean slate: no model resident

    # CONTEXT (gemma), once — PydanticAI context agent.
    residency.use(M.CONTEXT_MODEL)
    P.prog(project_root, "CONTEXT (gemma)", phase="CONTEXT", model=M.CONTEXT_MODEL)
    _gather_context(ctx)

    feedback = ""
    refute_flag = _axiom_backed(ctx)
    try:
        for it in range(1, max_steps + 1):
            if deadline and time.time() > deadline:
                break
            P.prog(project_root, f"iteration {it}", round=it)
            plan = plan_phase(ctx, feedback)
            if refute_flag and plan.get("mode") != "refute_then_prove":
                plan["mode"] = "refute_then_prove"  # force refute-first on axiom-backed nodes
            status, proved, fb = prove_phase(ctx, plan, deadline)
            if status == "FALSE":
                P.prog(
                    project_root,
                    "counterexample — FALSE",
                    phase="DONE",
                    status="unproved",
                    result="FALSE",
                )
                print(f"RESULT: FALSE (counterexample)  (node {node}; log {logpath})")
                return "FALSE"
            ok, msg = assemble_and_gate(ctx, plan, proved)
            if ok:
                P.prog(
                    project_root,
                    "final_verify CLEAN — PROVED",
                    phase="DONE",
                    status="proved",
                    result="PROVED",
                )
                print(f"RESULT: PROVED  (node {node}; log {logpath})")
                return "PROVED"
            feedback = (fb + "\n" + msg)[-4000:]
            refute_flag = False  # only force refute on the first iteration
            P.LOG.info(
                "iteration %d not closed; feedback head: %s",
                it,
                msg.splitlines()[0][:160] if msg else "",
            )
    finally:
        residency.free()  # free memory at end of run

    P.prog(
        project_root,
        "budget exhausted — UNPROVED",
        phase="DONE",
        status="unproved",
        result="UNPROVED",
    )
    print(f"RESULT: NOT PROVED (budget)  (node {node}; log {logpath})")
    return "UNPROVED"


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--node", required=True, help="prove proofs/<NODE>/attempt.lean (phase-batched)"
    )
    ap.add_argument(
        "--project-root", default=str(Path.home() / "projects" / "lean-runtime-analysis")
    )
    ap.add_argument(
        "--max-hours", type=float, default=0.0, help="wall-clock budget (0 = use --max-steps)"
    )
    ap.add_argument("--max-steps", type=int, default=6, help="outer PLAN/PROVE iterations")
    ap.add_argument("--allow-cloud-escalation", action="store_true")
    a = ap.parse_args()
    run(
        a.node,
        Path(a.project_root),
        max_hours=a.max_hours,
        max_steps=a.max_steps,
        allow_cloud=a.allow_cloud_escalation,
    )


if __name__ == "__main__":
    main()
