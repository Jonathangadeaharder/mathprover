#!/usr/bin/env python3
"""PydanticAI Agent definitions — the native framework replaces hand-rolled ReAct loops.

Six agents, one per role:
  planner     qwen + Plan output + planner_tools  — replaces plan_phase() manual msg loop
  researcher  qwen + ProposeResult + researcher_tools  — replaces research_thread() manual msg loop
  context     gemma + str output  — replaces gemma_compress() (plain text, brief+premises format)
  synthesizer gemma + ProposeResult output  — replaces synthesize() + parse_json_action
  strategizer qwen + StrategizeResult output  — replaces pipeline.strategize() + JSON parse
  splitter    gemma + Split output  — replaces pipeline.propose_split() + JSON parse

Each agent uses models.run_sync() which enforces turn-based residency before every call.
"""

from __future__ import annotations

import models as M
import pai_tools
import schemas
import tools as T
from pydantic_ai import Agent
from typing import Any

PLAN_SYS = (
    "You are the PLANNER of a turn-based theorem-proving agent. You do NOT write Lean proofs; "
    "a specialist prover (oprover) proves the leaves you define. Probe with tools if needed, "
    "then emit a plan.\n\n"
    "Rules: prefer direct=true for a small goal. Use direct=false + generic, easiest-first leaves "
    "for a compound goal; then parent_proof must close the original goal with NO sorry using the "
    "leaves. Keep leaf goal_spec self-contained and compilable."
)

RESEARCH_SYS = (
    "You are a Lean 4 proof RESEARCHER. You do NOT emit final proofs. "
    "You maintain a compact proof-state report and, each turn, take ONE action to reduce the gap.\n\n"
    "Use `propose` once you have a concrete candidate (attempts and/or a split); `split` is optional. "
    "Keep goal_spec self-contained and compilable."
)

SYNTH_SYS = (
    "You are a proof SYNTHESIZER. Given research reports from diverse angles, consolidate into one "
    "action plan: resolve contradictions, pick the convergent best approach, graft the most promising "
    "proof fragments. Output attempts ordered best-first, and optionally a split."
)

STRAT_SYS = (
    "You are a Lean 4 proof strategist. Given a goal and candidate premises, decide whether to solve "
    "directly or split into sub-lemmas. Choose split only if the goal is too compound for a direct "
    "~30-line proof. Provide a concise sketch of the tactic plan or decomposition rationale."
)

SPLIT_SYS = (
    "You are a Lean 4 proof architect. Decompose the given goal into 2-5 SELF-CONTAINED sub-lemmas "
    "that together prove it. Each sub-lemma must be small enough to prove in isolation. The parent_proof "
    "must close the original goal using the sub-lemmas by name, with NO sorry."
)


def _planner() -> Any:
    ag = Agent(M.model("qwen"), deps_type=T.Ctx, output_type=schemas.Plan,
               system_prompt=PLAN_SYS, retries=3)
    for t in pai_tools.PLANNER_TOOLS:
        ag.tool(t)
    return ag


def _researcher() -> Any:
    ag = Agent(M.model("qwen"), deps_type=T.Ctx, output_type=schemas.ProposeResult,
               system_prompt=RESEARCH_SYS, retries=2)
    for t in pai_tools.RESEARCHER_TOOLS:
        ag.tool(t)
    return ag


def _context() -> Any:
    return Agent(M.model("gemma"), deps_type=T.Ctx, output_type=str, retries=2,
                 system_prompt=(
                     "You are a Lean 4 context librarian. You read large project context and emit a "
                     "COMPACT, self-contained summary for a downstream prover with a small window. "
                     "Be terse and exact; never invent lemma names or definitions — only report what "
                     "is actually present.\n\n"
                     "Output EXACTLY two sections:\n"
                     "=== BRIEF ===\n(<800 words) the exact goal statement; the key in-scope definitions "
                     "and what they unfold to; candidate strategy; any traps.\n"
                     "=== PREMISES ===\nup to 12 candidate signatures, ONE per line, verbatim."))


def _synthesizer() -> Any:
    return Agent(M.model("gemma"), output_type=schemas.ProposeResult, retries=2,
                 system_prompt=SYNTH_SYS)


def _strategizer() -> Any:
    return Agent(M.model("qwen"), output_type=schemas.StrategizeResult, retries=2,
                 system_prompt=STRAT_SYS)


def _splitter() -> Any:
    return Agent(M.model("gemma"), output_type=schemas.Split, retries=2,
                 system_prompt=SPLIT_SYS)


_planner_ag: Any = None
_researcher_ag: Any = None
_context_ag: Any = None
_synthesizer_ag: Any = None
_strategizer_ag: Any = None
_splitter_ag: Any = None


def planner() -> Any:
    global _planner_ag
    if _planner_ag is None:
        _planner_ag = _planner()
    return _planner_ag


def researcher() -> Any:
    global _researcher_ag
    if _researcher_ag is None:
        _researcher_ag = _researcher()
    return _researcher_ag


def context() -> Any:
    global _context_ag
    if _context_ag is None:
        _context_ag = _context()
    return _context_ag


def synthesizer() -> Any:
    global _synthesizer_ag
    if _synthesizer_ag is None:
        _synthesizer_ag = _synthesizer()
    return _synthesizer_ag


def strategizer() -> Any:
    global _strategizer_ag
    if _strategizer_ag is None:
        _strategizer_ag = _strategizer()
    return _strategizer_ag


def splitter() -> Any:
    global _splitter_ag
    if _splitter_ag is None:
        _splitter_ag = _splitter()
    return _splitter_ag
