#!/usr/bin/env python3
"""Local deep-research for hard proof nodes — IterResearch + Heavy mode (BIG_PROBLEMS_DESIGN.md §5).

PydanticAI-native: the researcher agent handles probe→propose natively (tool-calling + ProposeResult
structured output), replacing the manual msg loop + JSON parsing. The synthesizer agent consolidates
N compressed reports via ProposeResult structured output, replacing gemma_compress + parse_json_action.

IterResearch workspace reconstruction: PydanticAI manages the full conversation internally. For bounded
research threads (4 rounds, compact tool responses), the context stays small — the explicit
report-reconstruction pattern is no longer needed. The compressed report is built from the agent result
for synthesis and persistence.

Residency cost for the whole call: 1 qwen load (all threads) + 1 gemma (synth, if N>1) + 1 oprover.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

from pydantic_ai import Agent

AGENTS = Path(__file__).resolve().parent
sys.path.insert(0, str(AGENTS))
import models as M  # noqa: E402
import pai_agents  # noqa: E402
import pipeline as P  # noqa: E402
import residency  # noqa: E402
import schemas  # noqa: E402
import tools as T  # noqa: E402

ANGLES = [
    ("direct", "Close the goal directly: find the single key lemma (search_premises/check_decl) and "
               "the tactic chain that applies it. Probe its exact type before proposing."),
    ("reduce", "Reduce to a known mathlib/project lemma: identify what standard result the goal is an "
               "instance of, verify it exists and its signature, then propose the reduction."),
    ("decompose", "Split into 2-4 GENERIC, easier sub-lemmas whose conjunction closes the goal; give a "
                  "parent_proof that uses them by name. Prefer reusable Mathlib-shaped helpers."),
    ("cases", "Attack by case analysis / contradiction / induction: identify the right split variable "
              "or the contradiction hypothesis, probe the relevant lemmas, propose the structured proof."),
]


def _research_prompt(ctx: T.Ctx, angle: tuple[str, str]) -> str:
    name, hint = angle
    return (f"[Research angle: {name} — {hint}]\n\n"
            f"Goal:\n```lean\n{ctx.goal_src}\n```\n\n"
            f"Context brief:\n{ctx.brief or '(none)'}\n\n"
            f"Premises:\n{chr(10).join(ctx.premises[:8]) or '(none)'}\n\n"
            "Probe with tools to reduce the gap, then propose attempts and/or a split.")


def research_thread(ctx: T.Ctx, angle: tuple[str, str], deadline: float | None) -> dict:
    """One IterResearch thread (qwen, PydanticAI researcher agent). Returns a compressed report."""
    name, _ = angle
    ag = pai_agents.researcher()
    prompt = _research_prompt(ctx, angle)
    rep: dict = {"angle": name, "attempts": [], "split": None, "confidence": 0.0}
    try:
        result = M.run_sync(ag, "qwen", prompt, deps=ctx, max_tokens=P.QWEN_GEN, temperature=0.3)
        pr: schemas.ProposeResult = result.output  # type: ignore[assignment]
        rep["attempts"] = [{"goal_spec": a.goal_spec, "sketch": a.sketch} for a in pr.attempts]
        if pr.split:
            rep["split"] = {"sublemmas": [{"name": s.name, "statement": s.statement}
                                          for s in pr.split.sublemmas],
                            "parent_proof": pr.split.parent_proof}
        rep["confidence"] = 0.5 if rep["attempts"] or rep["split"] else 0.0
        P.LOG.info("  research[%s]: proposed %d attempts%s", name, len(rep["attempts"]),
                   " +split" if rep["split"] else "")
    except Exception as e:  # noqa: BLE001
        P.LOG.warning("  research[%s] qwen fail: %s", name, e)
    return rep


def synthesize(ctx: T.Ctx, reports: list[dict]) -> dict:
    """gemma: consolidate N compressed reports → one action plan {attempts, split}."""
    blob = "\n\n---\n".join(
        f"REPORT (angle {r['angle']}, conf {r['confidence']}):\n"
        f"attempts: {json.dumps(r['attempts'])[:800]}\nsplit: {json.dumps(r['split'])[:800]}"
        for r in reports)
    prompt = (f"Goal:\n```lean\n{ctx.goal_src}\n```\n\n{len(reports)} research reports from diverse "
              f"angles:\n{blob}\n\nConsolidate into one action plan with attempts ordered best-first.")
    try:
        ag = pai_agents.synthesizer()
        result = M.run_sync(ag, "gemma", prompt, max_tokens=2048, temperature=0.2)
        pr: schemas.ProposeResult = result.output  # type: ignore[assignment]
        return {"attempts": [{"goal_spec": a.goal_spec, "sketch": a.sketch} for a in pr.attempts],
                "split": ({"sublemmas": [{"name": s.name, "statement": s.statement}
                                         for s in pr.split.sublemmas],
                           "parent_proof": pr.split.parent_proof}
                          if pr.split else None)}
    except Exception as e:  # noqa: BLE001
        P.LOG.warning("  synthesis gemma fail: %s -> using first thread's results", e)
        return {"attempts": reports[0]["attempts"], "split": reports[0]["split"]}


def deep_research(ctx: T.Ctx, project_root: Path, *, threads: int = 3, rounds: int = 4,
                  deadline: float | None = None) -> dict:
    """Heavy-mode entry. Returns {status: 'proved'|'split'|'exhausted', proof?, split?, reports}."""
    P.prog(project_root, f"deep-research {ctx.node}: {threads} threads", phase="RESEARCH")
    residency.use(M.PLANNER_MODEL)
    reports = []
    for t in range(threads):
        if deadline and time.time() > deadline:
            break
        P.prog(project_root, f"research thread {t} ({ANGLES[t % len(ANGLES)][0]})", model=M.PLANNER_MODEL)
        reports.append(research_thread(ctx, ANGLES[t % len(ANGLES)], deadline))
    if not reports:
        return {"status": "exhausted", "reports": []}
    if len(reports) > 1:
        residency.use(M.CONTEXT_MODEL)
        P.prog(project_root, "synthesis (gemma)", model=M.CONTEXT_MODEL)
        plan = synthesize(ctx, reports)
    else:
        plan = {"attempts": reports[0]["attempts"], "split": reports[0]["split"]}
    residency.use(M.PROVER_MODEL)
    P.prog(project_root, f"research attempts ({len(plan['attempts'])})", model=M.PROVER_MODEL)
    for att in plan["attempts"][:4]:
        if deadline and time.time() > deadline:
            break
        proof = P.prove_leaf(ctx.goal_src, project_root, att.get("sketch", ""), ctx.premises,
                             rounds=6, width=1, deadline=deadline)
        if proof:
            return {"status": "proved", "proof": proof, "reports": reports}
    sp = plan.get("split")
    if isinstance(sp, dict) and sp.get("sublemmas") and sp.get("parent_proof") \
            and P.verify_split(ctx.goal_src, sp, project_root):
        return {"status": "split", "split": sp, "reports": reports}
    return {"status": "exhausted", "reports": reports}


def write_report(project_root: Path, node_id: str, reports: list[dict]) -> str:
    """Persist the proof-state report(s) as the node's durable research artifact."""
    d = project_root / ".mathprover" / "dag"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{node_id}.report.md"
    body = f"# deep-research report: {node_id}\n\n"
    for r in reports:
        body += (f"## angle: {r['angle']}  (confidence {r['confidence']})\n"
                 f"attempts: {len(r['attempts'])}; split: {'yes' if r['split'] else 'no'}\n\n")
    path.write_text(body, encoding="utf-8")
    return f".mathprover/dag/{node_id}.report.md"
