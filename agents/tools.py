#!/usr/bin/env python3
"""Tool surface for the local-Aristotle agent (LOCAL_ARISTOTLE_DESIGN.md §2).

Every tool runs in this Python harness and returns a COMPACT string (never a raw 100k dump — that
is gemma's job to compress). The dispatcher is resilient: a malformed/unknown call is answered with
a schema reminder, never crashes the loop. All proving routes through pipeline.prove_leaf (oprover's
trained loop); the agent (qwen) only ever drives these tools.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

AGENTS = Path(__file__).resolve().parent
sys.path.insert(0, str(AGENTS))
import models as M  # noqa: E402
import pipeline as P  # noqa: E402
from lean_pipeline import (  # noqa: E402
    compile_lean_file,
    final_verify_attempt,
    forbidden_placeholders,
)
from proof_architecture import build_architecture, render_markdown, write_scratch_probe  # noqa: E402


@dataclass
class Ctx:
    """Shared agent state the tools read/write."""
    project_root: Path
    node: str
    proof_dir: Path
    attempt_file: Path
    goal_src: str                     # the ORIGINAL statement (statement-preservation anchor)
    allow_cloud: bool = False
    verified_ok: bool = False         # set True only by a clean final_verify; gate for "done"
    last_verify_msg: str = ""
    helpers: list[dict] = field(default_factory=list)
    brief: str = ""                   # gemma's compact context brief (CONTEXT phase output)
    premises: list[str] = field(default_factory=list)  # gemma-selected premises (no nomic in hot path)


def _rel(ctx: Ctx, p: Path) -> str:
    try:
        return p.resolve().relative_to(ctx.project_root.resolve()).as_posix()
    except Exception:  # noqa: BLE001
        return str(p)


def _clip(s: str, n: int = 2500) -> str:
    s = s or ""
    return s if len(s) <= n else s[:n] + f"\n…[+{len(s) - n} chars clipped]"


def _safe_path(ctx: Ctx, path: str) -> Path | None:
    """Confine reads to the project tree."""
    p = (ctx.project_root / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    try:
        p.relative_to(ctx.project_root.resolve())
    except ValueError:
        return None
    return p


# ---------------- Navigate / read ----------------
def t_list_dir(ctx: Ctx, path: str = ".") -> str:
    p = _safe_path(ctx, path)
    if not p or not p.exists():
        return f"ERROR: no such path {path}"
    if p.is_file():
        return f"{_rel(ctx, p)} (file, {p.stat().st_size} bytes)"
    entries = sorted(p.iterdir())[:200]
    return "\n".join(("d " if e.is_dir() else "f ") + _rel(ctx, e) for e in entries) or "(empty)"


def t_read_file(ctx: Ctx, path: str, start: int = 1, count: int = 120) -> str:
    p = _safe_path(ctx, path)
    if not p or not p.is_file():
        return f"ERROR: no such file {path}"
    lines = p.read_text(errors="ignore").splitlines()
    seg = lines[max(0, start - 1):max(0, start - 1) + count]
    return _clip("\n".join(f"{start + i}: {ln}" for i, ln in enumerate(seg)), 4000)


def t_grep_project(ctx: Ctx, pattern: str, glob: str = "*.lean") -> str:
    try:
        rx = re.compile(pattern)
    except re.error as e:
        return f"ERROR: bad regex: {e}"
    hits: list[str] = []
    for f in sorted(ctx.project_root.glob(glob)):
        if not f.is_file():
            continue
        for i, ln in enumerate(f.read_text(errors="ignore").splitlines(), 1):
            if rx.search(ln):
                hits.append(f"{_rel(ctx, f)}:{i}: {ln.strip()[:160]}")
                if len(hits) >= 60:
                    return "\n".join(hits) + "\n…[capped at 60]"
    return "\n".join(hits) or "(no matches)"


def _lexical_prefilter(goal_src: str, corpus: list[str], keep: int = 150) -> list[str]:
    """Free harness prefilter: rank lemma signatures by shared-identifier overlap with the goal, so
    gemma only has to pick from the most plausible ~150 (not the whole 4000-sig corpus)."""
    kw = P._GOAL_SKIP | {"theorem", "lemma", "def", "Prop", "True", "False"}
    gid = {t for t in re.findall(r"[A-Za-z_][A-Za-z0-9_']{2,}", goal_src.split(":=", 1)[0]) if t not in kw}
    if not gid:
        return corpus[:keep]
    scored = sorted(corpus, key=lambda s: len(gid & {t for t in re.findall(
        r"[A-Za-z_][A-Za-z0-9_']{2,}", s) if t not in kw}), reverse=True)
    return scored[:keep]


def t_gather_context(ctx: Ctx, focus: str = "") -> str:
    """CONTEXT phase (gemma, heavy — call once per node, batched). Reads the node attempt +
    paper_source + in-scope def bodies + lexically-prefiltered lemma signatures, then gemma (a)
    writes a compact self-contained brief and (b) SELECTS the curated premises (replaces nomic in the
    hot path). Stores brief + premises on ctx for the planner/executor."""
    attempt = ctx.attempt_file.read_text(errors="ignore") if ctx.attempt_file.exists() else ctx.goal_src
    paper = ""
    ps = ctx.proof_dir / "paper_source.md"
    if ps.exists():
        paper = ps.read_text(errors="ignore")[:8000]
    defs = P.definitions_for_goal(ctx.goal_src, ctx.project_root)
    candidates = _lexical_prefilter(ctx.goal_src, P.project_lemma_corpus(ctx.project_root))
    prompt = (f"Goal file (proofs/{ctx.node}/attempt.lean):\n```lean\n{attempt[:6000]}\n```\n\n"
              f"Paper source notes:\n{paper or '(none)'}\n\n"
              f"In-scope definitions found in the project:\n{chr(10).join(defs) or '(none)'}\n\n"
              f"Candidate lemma signatures (pick the useful ones):\n{chr(10).join(candidates)}\n\n"
              f"Focus: {focus or 'the sorry in this file'}\n\n"
              "Output EXACTLY two sections:\n"
              "=== BRIEF ===\n(<800 words) the exact goal statement; the key in-scope definitions "
              "and what they unfold to; candidate strategy; any traps. Report only what is present.\n"
              "=== PREMISES ===\nup to 12 of the candidate signatures above that are most likely "
              "useful, ONE per line, verbatim, no commentary.")
    out = M.chat_sync(M.CONTEXT_MODEL, [
        {"role": "system", "content":
         "You are a Lean 4 context librarian. You read large project context and emit a COMPACT, "
         "self-contained summary for a downstream prover with a small window. Be terse and exact; "
         "never invent lemma names or definitions — only report what is actually present.\n\n"
         "Output EXACTLY two sections:\n"
         "=== BRIEF ===\n(<800 words) the exact goal statement; the key in-scope definitions "
         "and what they unfold to; candidate strategy; any traps. Report only what is present.\n"
         "=== PREMISES ===\nup to 12 candidate signatures, ONE per line, verbatim."},
        {"role": "user", "content": prompt}], max_tokens=4096, temperature=0.2)
    brief, prem = out, []
    if "=== PREMISES ===" in out:
        brief, _, premblk = out.partition("=== PREMISES ===")
        prem = [ln.strip(" -\t") for ln in premblk.splitlines()
                if ln.strip() and ("theorem" in ln or "lemma" in ln)][:12]
    brief = brief.replace("=== BRIEF ===", "").strip()
    ctx.brief = brief
    ctx.premises = prem
    return _clip(brief, 4000) + f"\n\n[gemma selected {len(prem)} premises; cached for prove]"


# ---------------- Probe ----------------
def t_run_lean(ctx: Ctx, snippet: str) -> str:
    r = compile_lean_file(project_root=ctx.project_root, lean_file=P._scratch(ctx.project_root, snippet))
    return ("COMPILES (ok)" if r.ok else "FAIL:\n" + _clip(r.error_excerpt(2000)))


def t_check_decl(ctx: Ctx, name: str, imports: str = "import LBTCoupling") -> str:
    snip = f"{imports}\n#check @{name}\n"
    r = compile_lean_file(project_root=ctx.project_root, lean_file=P._scratch(ctx.project_root, snip))
    return _clip(r.error_excerpt(1500)) if r.combined.strip() else ("ok" if r.ok else "FAIL")


def t_open_private(ctx: Ctx, names: str, module: str) -> str:
    namelist = [n for n in re.split(r"[,\s]+", names) if n]
    probe = write_scratch_probe(project_root=ctx.project_root, goal_file=ctx.attempt_file,
                                names=namelist, open_private_from=module)
    r = compile_lean_file(project_root=ctx.project_root, lean_file=probe)
    return ("open-private OK: " + " ".join(namelist)) if r.ok else "FAIL:\n" + _clip(r.error_excerpt(1500))


def t_search_premises(ctx: Ctx, goal: str = "", k: int = 12) -> str:
    prem = P.retrieve_premises(goal or ctx.goal_src, ctx.project_root, k=k)
    return "\n".join(prem) or "(no premises)"


# ---------------- Prove ----------------
def t_prove(ctx: Ctx, goal: str = "", sketch: str = "", rounds: int = 6) -> str:
    """oprover refinement loop on a self-contained goal. Uses gemma-selected premises (ctx.premises)
    to stay in the oprover residency burst — only falls back to nomic retrieval if none were cached
    (which would swap models). Returns proof head or failure feedback."""
    src = goal.strip() or ctx.goal_src
    prem = ctx.premises or P.retrieve_premises(src, ctx.project_root)
    proof = P.prove_leaf(src, ctx.project_root, sketch, prem, rounds=rounds, width=1)
    if proof:
        return "PROVED. proof file written to .mathprover/pipeline/proved/. Now edit_attempt + final_verify."
    return "NOT PROVED within budget. Decompose (architect) or probe more, then retry."


def t_refute(ctx: Ctx, goal: str = "", rounds: int = 4) -> str:
    """Mandatory first call on axiom-backed/quarantined statements: try to build ¬(∀…) and prove it."""
    cex = P.refute(goal.strip() or ctx.goal_src, ctx.project_root, rounds=rounds)
    if cex:
        return "COUNTEREXAMPLE FOUND — the statement is FALSE. Do not try to prove it; report FALSE."
    return "no counterexample within budget — statement may be true; proceed to prove."


# ---------------- Structure ----------------
def t_architect(ctx: Ctx, goal: str = "") -> str:
    arch = build_architecture(goal.strip() or ctx.goal_src, ctx.project_root)
    return _clip(render_markdown(arch, []), 3000)


def t_scaffold_helpers(ctx: Ctx, helpers: list | None = None) -> str:
    """Record helper sorries (scaffold-then-fill). `helpers`: [{name, statement}]."""
    helpers = helpers or []
    good = [h for h in helpers if isinstance(h, dict) and h.get("statement")]
    ctx.helpers = good
    body = P._imports_of(ctx.goal_src) + "\n\n" + "\n\n".join(h["statement"] for h in good)
    P._scratch(ctx.project_root, body)  # written for inspection; prove() works per-helper
    return f"scaffolded {len(good)} helper(s): {[h.get('name', '?') for h in good]}"


# ---------------- Commit (gated) ----------------
def t_edit_attempt(ctx: Ctx, new_text: str) -> str:
    """Write candidate to attempt.lean ONLY if it (a) preserves the statement, (b) no active
    placeholders, (c) final_verify clean. Anything less is rejected — the soundness firewall."""
    if not P._statement_preserved(ctx.goal_src, new_text):
        return "REJECTED: statement changed. You must prove EXACTLY the original statement."
    forb = forbidden_placeholders(new_text)
    if forb:
        return f"REJECTED: active placeholders present {forb}."
    # stage to a scratch and final_verify before touching the real file
    staged = P._scratch(ctx.project_root, new_text)
    ok, msg = final_verify_attempt(project_root=ctx.project_root, lean_file=staged)
    if not ok:
        ctx.verified_ok = False
        ctx.last_verify_msg = msg
        return "REJECTED by final_verify:\n" + _clip(msg, 2000)
    ctx.attempt_file.write_text(new_text, encoding="utf-8")
    ctx.verified_ok = True
    ctx.last_verify_msg = msg
    return "ACCEPTED: attempt.lean written and final_verify CLEAN. You may finish (done=true)."


def t_final_verify(ctx: Ctx, theorem: str = "") -> str:
    """The gate. Runs against the current on-disk attempt.lean."""
    if not ctx.attempt_file.exists():
        return "ERROR: attempt.lean missing"
    ok, msg = final_verify_attempt(project_root=ctx.project_root, lean_file=ctx.attempt_file,
                                   theorem=theorem or None)
    ctx.verified_ok = ok
    ctx.last_verify_msg = msg
    return ("CLEAN (compiles, no placeholders, axioms ⊆ standard, statement preserved)"
            if ok else "FAIL:\n" + _clip(msg, 2000))


# ---------------- Escalate (optional) ----------------
def t_submit_aristotle(ctx: Ctx, node: str = "") -> str:
    if not ctx.allow_cloud:
        return "BLOCKED: cloud escalation disabled (run with --allow-cloud-escalation)."
    return ("Cloud escalation is a separate, rate-limited tool. Run out-of-band:\n"
            f"  python3 agents/dispatch.py --node {node or ctx.node} --prover aristotle --skip-verify\n"
            "then monitor with agents/aristotle_attach.py. Not auto-invoked from the loop.")


# ---------------- registry + dispatch ----------------
# name -> (fn, "arg schema for the planner")
TOOLS: dict[str, tuple] = {
    "list_dir":        (t_list_dir,        '{"path": str}'),
    "read_file":       (t_read_file,       '{"path": str, "start": int?, "count": int?}'),
    "grep_project":    (t_grep_project,    '{"pattern": str, "glob": str?}'),
    "gather_context":  (t_gather_context,  '{"focus": str?}  (gemma; heavy — call sparingly)'),
    "run_lean":        (t_run_lean,        '{"snippet": str}  (compile a scratch Lean file)'),
    "check_decl":      (t_check_decl,      '{"name": str, "imports": str?}  (#check @name)'),
    "open_private":    (t_open_private,    '{"names": str, "module": str}  (test OpenPrivate access)'),
    "search_premises": (t_search_premises, '{"goal": str?, "k": int?}  (RAG top-k lemma sigs)'),
    "prove":           (t_prove,           '{"goal": str?, "sketch": str?, "rounds": int?}  (oprover)'),
    "refute":          (t_refute,          '{"goal": str?, "rounds": int?}  (try to DISPROVE)'),
    "architect":       (t_architect,       '{"goal": str?}  (semantic spine + helper-DAG)'),
    "scaffold_helpers": (t_scaffold_helpers, '{"helpers": [{"name": str, "statement": str}]}'),
    "edit_attempt":    (t_edit_attempt,    '{"new_text": str}  (gated write-back; runs final_verify)'),
    "final_verify":    (t_final_verify,    '{"theorem": str?}  (the gate; only path to done)'),
    "submit_aristotle": (t_submit_aristotle, '{"node": str?}  (optional cloud; off by default)'),
}


def tool_catalog() -> str:
    return "\n".join(f"- {name} {schema}" for name, (_, schema) in TOOLS.items())


def dispatch(ctx: Ctx, call: dict) -> str:
    """Execute one {"tool","args"} call. Resilient: bad tool/args -> schema reminder, never raise."""
    name = call.get("tool")
    args = call.get("args", {}) or {}
    if name not in TOOLS:
        return (f"ERROR: unknown tool {name!r}. Available tools:\n{tool_catalog()}")
    if not isinstance(args, dict):
        return f"ERROR: 'args' must be an object. Schema: {TOOLS[name][1]}"
    fn = TOOLS[name][0]
    try:
        return fn(ctx, **args)
    except TypeError as e:
        return f"ERROR: bad args for {name}: {e}. Schema: {TOOLS[name][1]}"
    except Exception as e:  # noqa: BLE001 — a tool failure must not kill the loop
        return f"ERROR: {name} raised {type(e).__name__}: {e}"
