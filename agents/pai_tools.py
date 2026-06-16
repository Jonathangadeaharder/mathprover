#!/usr/bin/env python3
"""PydanticAI tool wrappers — native tool-calling replaces dispatch + JSON parsing.

Two tool sets for two agents:
  planner_tools  — qwen PLAN phase: navigate + probe + structure (no model-swapping tools)
  researcher_tools — qwen IterResearch: probe only (run_lean, check_decl, search_premises, grep_project, read_file)

Each tool wraps the corresponding tools.py function, reading state from RunContext[Ctx].deps.
The model-swapping tools (gather_context, prove, refute, search_premises via embed) are NOT here —
they belong in their own phase agents or stay as direct calls (residency constraint).
"""

from __future__ import annotations

from pydantic_ai import RunContext

import tools as T


def _c(ctx: RunContext[T.Ctx]) -> T.Ctx:
    return ctx.deps


# ---- Navigate / read ----

def list_dir(ctx: RunContext[T.Ctx], path: str = ".") -> str:
    """List directory contents under the project root."""
    return T.t_list_dir(_c(ctx), path=path)


def read_file(ctx: RunContext[T.Ctx], path: str, start: int = 1, count: int = 120) -> str:
    """Read a file's contents (paginated). Paths relative to project root."""
    return T.t_read_file(_c(ctx), path=path, start=start, count=count)


def grep_project(ctx: RunContext[T.Ctx], pattern: str, glob: str = "*.lean") -> str:
    """Search the project for a regex pattern in files matching glob."""
    return T.t_grep_project(_c(ctx), pattern=pattern, glob=glob)


# ---- Probe (model-free Lean compilation) ----

def run_lean(ctx: RunContext[T.Ctx], snippet: str) -> str:
    """Compile a Lean 4 snippet in a scratch file. Returns COMPILES or FAIL."""
    return T.t_run_lean(_c(ctx), snippet=snippet)


def check_decl(ctx: RunContext[T.Ctx], name: str, imports: str = "import LBTCoupling") -> str:
    """Run #check @<name> to verify a declaration exists and see its type."""
    return T.t_check_decl(_c(ctx), name=name, imports=imports)


def open_private(ctx: RunContext[T.Ctx], names: str, module: str) -> str:
    """Test whether private names can be opened from a module."""
    return T.t_open_private(_c(ctx), names=names, module=module)


def search_premises(ctx: RunContext[T.Ctx], goal: str = "", k: int = 12) -> str:
    """RAG: retrieve top-k lemma signatures relevant to the goal."""
    return T.t_search_premises(_c(ctx), goal=goal, k=k)


# ---- Structure ----

def architect(ctx: RunContext[T.Ctx], goal: str = "") -> str:
    """Build a semantic spine + helper-DAG for the goal."""
    return T.t_architect(_c(ctx), goal=goal)


def scaffold_helpers(ctx: RunContext[T.Ctx], helpers: list[dict] | None = None) -> str:
    """Record helper sorries (scaffold-then-fill). helpers: [{name, statement}]."""
    return T.t_scaffold_helpers(_c(ctx), helpers=helpers)


# ---- Tool sets for agents ----

PLANNER_TOOLS = [list_dir, read_file, grep_project, run_lean, check_decl,
                 open_private, search_premises, architect, scaffold_helpers]

RESEARCHER_TOOLS = [run_lean, check_decl, search_premises, grep_project, read_file]
