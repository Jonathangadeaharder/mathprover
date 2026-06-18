#!/usr/bin/env python3
"""Formal-first, compiler-in-the-loop proving pipeline — a LOCAL Aristotle (no cloud).

Roles (by model strength), NOT a god-object:
  gemma-4-26b-a4b-qat (262k ctx)  : autoformalize + premise retrieval (RAG over mathlib+project)
  qwen MTPLX 27B      (local)      : strategize (solve-or-split) + critique + fallback prover.
                                     NOTE: MTPLX 27B — do NOT max its long window; prompts stay
                                     small (<= QWEN_INPUT_CAP) and generation is capped (QWEN_GEN).
  oprover-8b          (40k ctx)   : the prover on a self-contained leaf (8k in / 32k solve).

No cloud. Recursion bottoms out locally: a leaf that oprover+qwen cannot close is decomposed
further; if it cannot be decomposed (compiler-rejected split) at max depth, it is reported UNPROVED.

The Lean compiler is in the loop at EVERY structural step — nothing is trusted from an LLM:
  * autoformalize       -> compile the stated `sorry`-lemma (retry on type errors)
  * decomposition       -> ENTAILMENT-CHECKED: compile [sub-lemmas as sorry] + parent proof
                           using them; accept the split ONLY if the parent body compiles
                           sorry-free given the sub-lemmas (no prose bridge)
  * truth probe         -> cheap `decide/norm_num/simp` to drop obviously-false sub-lemmas
  * prove leaf          -> lake-clean AND sorry-free gate (lean_pipeline)

Budget is tied to the PROVER (oprover, 40k): a node is a leaf iff its prompt <= 8000 tokens.
"""

from __future__ import annotations

import datetime
import json
import logging
import math
import re
import sys
import time
from pathlib import Path

LOG = logging.getLogger("mathprover.pipeline")


def init_log(project_root: Path, run_id: str | None = None) -> Path:
    """File + console logging so every run is debuggable after the fact."""
    run_id = run_id or datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    d = project_root / ".mathprover" / "pipeline" / "logs"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{run_id}.log"
    LOG.setLevel(logging.DEBUG)
    LOG.handlers.clear()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S")
    fh = logging.FileHandler(path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    LOG.addHandler(fh)
    LOG.addHandler(ch)
    LOG.info(f"=== pipeline run {run_id}  log={path} ===")
    return path


AGENTS = Path(__file__).resolve().parent
sys.path.insert(0, str(AGENTS))
import models as M  # noqa: E402
import pai_agents  # noqa: E402
import schemas  # noqa: E402
import trajectory  # noqa: E402  (structured JSONL proving-step recorder)
from lean_pipeline import (  # noqa: E402
    apply_generated_proof,
    compile_lean_file,
    extract_lean4_blocks,
    forbidden_placeholders,
    has_sorry,
)
from prompts import build_aristotle_prompt  # noqa: E402  (the EXACT Aristotle execution prompt)
from proof_architecture import build_architecture, render_markdown  # noqa: E402

ROLE_PROVER = M.NAMES["oprover"]
ROLE_FORMALIZER = ROLE_PROVER
ROLE_RESEARCHER = M.NAMES["gemma"]
ROLE_STRATEGIST = M.NAMES["qwen"]
EMBED_MODEL = M.EMBED_MODEL

INPUT_LIMIT = M.INPUT_LIMIT
SOLVE_RESERVE = M.SOLVE_RESERVE
QWEN_GEN = 12288  # cap qwen generation (4-bit 27B; don't ask for huge outputs)
QWEN_INPUT_CAP = 64000  # qwen context kept ~64k (fine for 4-bit 27B; far below the nasty 262k)

# OProver agentic refinement (arXiv:2605.17283): the prover was TRAINED on a multi-round loop
# state X_t = (statement, retrieved proofs, prev attempt, raw Lean feedback) -> revised proof.
# Their ablation (Table 3) shows multi-turn compiler feedback is the PRIMARY gain driver
# (-FB drops Pass@32 by 4-9 pts). So prove_leaf is that loop, not one-shot whole-proof gen.
REFINE_ROUNDS = 8  # R: refinement rounds per leaf (paper: R=8 good for hard goals)
# Generation cap = the SOLVE_RESERVE the 40k window was split for (INPUT_LIMIT 8k + 32k solve),
# minus headroom because later rounds append prev-attempt+feedback to the prompt. 8192 was wrong:
# it left ~24k of the window unused and TRUNCATED any proof longer than 8k tokens (the hard goals).
# It is a CAP not a target (won't slow short proofs); chat() shrinks max_tokens on a 400 if a grown
# prompt + this cap ever exceeds the window.
GEN_PER_ROUND = 24576  # ~SOLVE_RESERVE minus ~8k prompt-growth headroom
REFINE_TEMP = 0.8  # paper samples at temp~1.0; 0.8 gives round-to-round diversity
ANSI_RE = re.compile(
    r"\x1b\[[0-9;]*m"
)  # strip ANSI so feedback is the raw text the model trained on


# ---------- live progress (Aristotle-style dashboard) ----------
_PROG: dict = {}


def _prog_paths(project_root: Path) -> tuple[Path, Path]:
    d = project_root / ".mathprover" / "pipeline"
    d.mkdir(parents=True, exist_ok=True)
    return d / "progress.json", d / "progress.html"


def init_progress(project_root: Path, *, task: str, mode: str, budget: str) -> None:
    """Start a fresh progress record and drop the static viewer (open progress.html in a browser)."""
    global _PROG
    _PROG = {
        "task": task,
        "mode": mode,
        "budget": budget,
        "status": "running",
        "started": time.time(),
        "updated": time.time(),
        "round": 0,
        "phase": "",
        "model": "",
        "current": task,
        "result": "",
        "events": [],
    }
    jpath, hpath = _prog_paths(project_root)
    hpath.write_text(_PROGRESS_HTML, encoding="utf-8")
    _flush_progress(project_root)


def prog(project_root: Path, msg: str, **fields) -> None:
    if not _PROG:
        return
    _PROG.update(fields)
    _PROG["updated"] = time.time()
    _PROG["events"] = (_PROG.get("events", []) + [{"t": time.time(), "msg": msg}])[-200:]
    _flush_progress(project_root)


def _flush_progress(project_root: Path) -> None:
    jpath, _ = _prog_paths(project_root)
    try:
        jpath.write_text(json.dumps(_PROG), encoding="utf-8")
    except Exception:  # noqa: BLE001 — never let UI bookkeeping break proving
        pass


# Self-contained dark/monospace/blue viewer modelled on the Aristotle dashboard; polls progress.json.
_PROGRESS_HTML = """<!doctype html><meta charset=utf-8><title>MathProver — progress</title>
<style>
 body{background:#171717;color:#e6e6e6;font:13px/1.5 ui-monospace,Menlo,Consolas,monospace;margin:0;padding:24px}
 .accent{color:#5b8def}.muted{color:#888}
 h1{font-size:15px;font-weight:600;margin:0 0 4px}
 .bar{height:10px;background:#222;border-radius:5px;overflow:hidden;margin:12px 0}
 .fill{height:100%;background:#03439b;width:0%}
 .row{display:flex;gap:16px;flex-wrap:wrap;margin:8px 0}
 .k{color:#888}.v{color:#e6e6e6}
 .feed{margin-top:16px;border-top:1px solid #2a2a2a;padding-top:12px}
 .ev{padding:2px 0;border-bottom:1px solid #1f1f1f;white-space:pre-wrap}
 .ev .ts{color:#5b8def;margin-right:10px}
 .ok{color:#3fb950}.fail{color:#e5534b}.run{color:#d29922}
</style>
<h1>MathProver <span class=accent>·</span> <span id=task></span></h1>
<div class=row><span class=k>mode</span> <span class=v id=mode></span>
 <span class=k>phase</span> <span class=v accent id=phase></span>
 <span class=k>model</span> <span class=v id=model></span>
 <span class=k>status</span> <span class=v id=status></span>
 <span class=k>elapsed</span> <span class=v id=elapsed></span>
 <span class=k>round</span> <span class=v id=round></span>
 <span class=k>budget</span> <span class=v id=budget></span></div>
<div class=bar><div class=fill id=fill></div></div>
<div class=k id=result></div>
<div class=feed id=feed></div>
<script>
function fmt(s){s=Math.max(0,Math.floor(s));let h=Math.floor(s/3600),m=Math.floor(s%3600/60),x=s%60;return (h?h+'h ':'')+(m||h?m+'m ':'')+x+'s';}
async function tick(){
 try{const r=await fetch('progress.json?'+Date.now());const d=await r.json();
  task.textContent=d.task||'';mode.textContent=d.mode||'';budget.textContent=d.budget||'';
  phase.textContent=d.phase||'';model.textContent=d.model||'';
  const st=d.status||'';status.textContent=st;status.className='v '+(st==='proved'?'ok':st==='running'?'run':st==='error'||st==='unproved'||(d.result||'').includes('FALSE')?'fail':'');
  const el=((d.updated||0)-(d.started||0));elapsed.textContent=fmt(el);round.textContent=d.round||0;
  result.textContent=d.result||'';
  fill.style.width=(st==='proved'?100:Math.min(95,(d.round||0)*8))+'%';
  feed.innerHTML=(d.events||[]).slice().reverse().map(e=>{
    const t=new Date(e.t*1000).toLocaleTimeString();
    return '<div class=ev><span class=ts>'+t+'</span>'+(e.msg||'').replace(/</g,'&lt;')+'</div>';}).join('');
 }catch(e){}
}
setInterval(tick,2000);tick();
</script>"""


def aristotle_user_prompt(
    proof_dir: Path, attempt_file: Path, project_root: Path, prev: str | None, fb: str | None
) -> str:
    """EXACT Aristotle execution prompt (prompts.build_aristotle_prompt), with a compiler-feedback
    refinement block appended on retries so the local loop matches Aristotle's iterate-on-feedback."""
    base = build_aristotle_prompt(
        proof_dir=proof_dir, attempt_file=attempt_file, project_root=project_root
    )
    # Aristotle (cloud agent) READS the file; our local model cannot — inline the file contents so
    # the instruction "close the sorry in <file>" is actionable, and output the COMPLETE file.
    rel = attempt_file.relative_to(project_root).as_posix()
    base = (
        f"The file `{rel}` currently contains:\n```lean\n{attempt_file.read_text(encoding='utf-8')}\n```\n\n"
        + base
        + "\nOutput the COMPLETE file in one ```lean block (keep the theorem name and statement "
        "verbatim)."
    )
    if prev:
        base += (
            f"\n\nYour previous attempt did not compile. Previous attempt:\n```lean\n{prev}\n```\n"
            f"Lean compiler feedback:\n```\n{fb or ''}\n```\nRevise the proof accordingly."
        )
    return base


# ---------- LM Studio (OpenAI-compatible) — delegated to models.py ----------
def chat(
    model: str, messages: list[dict], *, max_tokens: int = 4096, temperature: float = 0.2
) -> str:
    return M.chat_sync(model, messages, max_tokens=max_tokens, temperature=temperature)


def prompt_tokens(text: str, model: str = ROLE_PROVER) -> int:
    return M.prompt_tokens(text, model=model)


def embed(texts: list[str]) -> list[list[float]]:
    return M.embed(texts)


def _cos(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb + 1e-9)


# ---------- premise retrieval (the RAG that actually helps: mathlib+project lemmas) ----------
def project_lemma_corpus(project_root: Path, limit: int = 4000) -> list[str]:
    sigs: list[str] = []
    for f in project_root.glob("*.lean"):
        for m in re.finditer(
            r"^(?:theorem|lemma)\s+([A-Za-z0-9_']+)[^\n]*", f.read_text(errors="ignore"), re.M
        ):
            sigs.append(m.group(0).strip()[:300])
            if len(sigs) >= limit:
                return sigs
    return sigs


def retrieve_premises(goal_src: str, project_root: Path, k: int = 12, pool: int = 600) -> list[str]:
    t0 = time.time()
    corpus = project_lemma_corpus(project_root)[
        :pool
    ]  # cap the pool (was embedding ~4000 in one call)
    if not corpus:
        LOG.info("retrieve_premises: empty corpus -> no premises")
        return []
    try:
        qv = embed([goal_src])[0]
        cvs: list[list[float]] = []
        for i in range(0, len(corpus), 64):  # batch to avoid one giant /embeddings request
            cvs.extend(embed(corpus[i : i + 64]))
    except Exception as e:  # noqa: BLE001 — RAG is an enhancement, never block proving on it
        LOG.warning("retrieve_premises: embed failed (%s) -> proceeding with no premises", e)
        return []
    scored = sorted(zip(corpus, cvs, strict=False), key=lambda cb: _cos(qv, cb[1]), reverse=True)
    LOG.info("retrieve_premises: %d/%d premises in %.1fs", k, len(corpus), time.time() - t0)
    return [c for c, _ in scored[:k]]


# ---------- roles ----------
def autoformalize(
    informal: str, project_root: Path, *, imports: str = "import Mathlib"
) -> str | None:
    """gemma: informal goal -> a compiling `sorry`-lemma. Compiler in loop (retry on type error)."""
    msgs = [
        {
            "role": "system",
            "content": "You are a Lean 4 autoformalizer. Output ONE ```lean block: necessary imports, then a "
            "single `theorem ... := by sorry`. The statement must typecheck; the proof is just `sorry`.",
        },
        {"role": "user", "content": f"Imports available: {imports}\n\nFormalize:\n{informal}"},
    ]
    for _ in range(3):
        out = chat(ROLE_FORMALIZER, msgs, max_tokens=2048)
        blocks = extract_lean4_blocks(out)
        cand = blocks[-1] if blocks else None
        if not cand:
            continue
        r = compile_lean_file(project_root=project_root, lean_file=_scratch(project_root, cand))
        if r.ok:  # compiles (sorry warning ok)
            return cand
        msgs += [
            {"role": "assistant", "content": out},
            {
                "role": "user",
                "content": f"That did not typecheck:\n```\n{r.error_excerpt(1500)}\n```\nFix the STATEMENT.",
            },
        ]
    return None


def strategize(goal_src: str, premises: list[str]) -> dict:
    """qwen: decide solve-vs-split + give a sketch. PydanticAI strategizer agent."""
    prem = "\n".join(premises[:12])
    prompt = f"Premises:\n{prem}\n\nGoal:\n```lean\n{goal_src}\n```"
    try:
        ag = pai_agents.strategizer()
        result = M.run_sync(ag, "qwen", prompt, max_tokens=768, temperature=0.3)
        sr: schemas.StrategizeResult = result.output  # type: ignore[assignment]
        return {"action": sr.action, "sketch": sr.sketch}
    except Exception as e:  # noqa: BLE001
        LOG.warning("strategize PydanticAI call failed (%s) -> fallback solve", e)
        return {"action": "solve", "sketch": ""}


def propose_split(goal_src: str, premises: list[str]) -> dict:
    """gemma: emit sub-lemmas + a parent proof that uses them. PydanticAI splitter agent."""
    prem = "\n".join(premises[:8])
    prompt = f"Premises:\n{prem}\n\nGoal:\n```lean\n{goal_src}\n```"
    try:
        ag = pai_agents.splitter()
        result = M.run_sync(ag, "gemma", prompt, max_tokens=SOLVE_RESERVE, temperature=0.2)
        sp: schemas.Split = result.output  # type: ignore[assignment]
        return {
            "sublemmas": [{"name": s.name, "statement": s.statement} for s in sp.sublemmas],
            "parent_proof": sp.parent_proof,
        }
    except Exception as e:  # noqa: BLE001
        LOG.warning("propose_split PydanticAI call failed (%s) -> empty split", e)
        return {"sublemmas": [], "parent_proof": ""}


# ---------- the compiler-in-the-loop gates ----------
def _imports_of(src: str) -> str:
    return "\n".join(ln for ln in src.splitlines() if ln.strip().startswith(("import ", "open ")))


def verify_split(goal_src: str, split: dict, project_root: Path) -> bool:
    """SOUND decomposition gate: compile [sub-lemmas as `:= by sorry`] + the parent declaration
    with `parent_proof` referencing them. Accept iff it compiles AND parent_proof is sorry-free."""
    subs, parent_proof = split["sublemmas"], split["parent_proof"].strip()
    if not subs or not parent_proof or has_sorry(parent_proof):
        return False
    # parent statement = goal with its `:= by sorry` replaced by `:= <parent_proof>`
    stmt = re.split(r":=\s*by\s+sorry|:=\s*sorry", goal_src)[0].rstrip()
    parent_proof = parent_proof if parent_proof.startswith("by") else "by " + parent_proof
    body = _imports_of(goal_src) + "\n\n"
    body += "\n\n".join(s["statement"] for s in subs) + "\n\n"
    body += f"{stmt} := {parent_proof}\n"
    r = compile_lean_file(project_root=project_root, lean_file=_scratch(project_root, body))
    LOG.debug(
        "verify_split: %s%s",
        "OK (entails)" if r.ok else "FAIL",
        "" if r.ok else " :: " + r.error_excerpt(400),
    )
    return r.ok


def truth_probe(goal_src: str, project_root: Path) -> bool:
    """Cheap counter-evidence gate: if a one-shot `decide/norm_num/simp_all/omega` makes the file
    OUTRIGHT FAIL with a falsity-style error, flag it. Conservative: only returns False on hard fail."""
    for tac in ("decide", "norm_num", "simp_all", "omega"):
        cand = re.sub(r"(:=\s*by\s+)sorry", r"\1" + tac, goal_src, count=1)
        if compile_lean_file(
            project_root=project_root, lean_file=_scratch(project_root, cand)
        ).ok and not has_sorry(cand):
            return True  # actually proved by a one-liner — definitely true & trivial
    return True  # inconclusive -> let the prover try (do not falsely reject)


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _goal_signature(src: str) -> str | None:
    """The statement of the goal: `(theorem|lemma) NAME ... :` up to the `:=` proof separator."""
    m = re.search(r"\b(?:theorem|lemma)\b.*?(?=:=)", src, re.DOTALL)
    return m.group(0).strip() if m else None


def _statement_preserved(goal_src: str, cand: str) -> bool:
    """SOUNDNESS GUARD: the candidate must prove EXACTLY our statement, not a weakened/changed
    one. `apply_generated_proof` returns the model's file verbatim when it carries imports, so a
    model that quietly edits the statement would otherwise pass the compile+sorry gate. Require
    our statement (whitespace-normalized) to appear verbatim in the candidate."""
    sig = _goal_signature(goal_src)
    if not sig:
        return True  # could not extract a signature; do not block (rare; other gates still apply)
    return _norm_ws(sig) in _norm_ws(cand)


_DECL_BOUNDARY = re.compile(
    r"\n(?=(?:noncomputable\s+|private\s+|protected\s+)*"
    r"(?:def|abbrev|lemma|theorem|structure|inductive|instance|/--|namespace|section|end)\b)"
)
_GOAL_SKIP = {
    "theorem",
    "lemma",
    "by",
    "fun",
    "if",
    "then",
    "else",
    "let",
    "Nat",
    "Set",
    "Real",
    "Measure",
    "MeasureTheory",
    "ENNReal",
    "BigOperators",
    "Finset",
    "sorry",
    "open",
    "import",
    "Type",
    "Prop",
    "Population",
    "BitString",
}


def definitions_for_goal(
    goal_src: str, project_root: Path, max_defs: int = 5, max_chars: int = 800
) -> list[str]:
    """Source of the DEFINITIONS named in the goal statement. Lemma signatures (RAG) tell the
    prover which lemmas exist; this tells it what the goal's symbols MEAN, so it can `unfold`/
    `simp only [...]` them instead of hallucinating a re-definition (observed failure: oprover
    wrote `def coea_sel_measure ...` inside `:= by`)."""
    head = goal_src.split(":=", 1)[0]
    names: list[str] = []
    for tok in re.findall(r"[A-Za-z_][A-Za-z0-9_']*", head):
        if tok in _GOAL_SKIP or len(tok) <= 2 or tok in names:
            continue
        names.append(tok)
    files = list(project_root.glob("*.lean"))
    out: list[str] = []
    for name in names:
        if len(out) >= max_defs:
            break
        pat = re.compile(
            rf"^(?:noncomputable\s+|private\s+|protected\s+)*(?:def|abbrev)\s+{re.escape(name)}\b",
            re.M,
        )
        for f in files:
            text = f.read_text(errors="ignore")
            m = pat.search(text)
            if not m:
                continue
            rest = text[m.start() :]
            stop = _DECL_BOUNDARY.search(rest[5:])
            block = rest[: stop.start() + 5] if stop else rest[:max_chars]
            out.append(block.strip()[:max_chars])
            break
    return out


# Goal-shape -> strategic hint, distilled from successful Aristotle runs (see PROOF_PATTERNS.md).
# Injected into the prover prompt so the trained model gets the canonical move up front, the way
# Aristotle leaned on retrieved patterns. Keep these short and tactically concrete.
PATTERN_HINTS: list[tuple[tuple[str, ...], str]] = [
    (
        ("expected_generations", "expected number of generations", "hitting", "< ⊤", "drift"),
        "Expected-hitting-time bound (`expected_generations … ≤ B`, or `… < ⊤`): apply "
        "`kernel_additive_drift` with potential `fun P => if P ∈ target then 0 else <bound>`, then "
        "discharge the one-step drift obligation; `ENNReal.toReal_nonneg` gives the trivial lower side.",
    ),
    (
        ("∫⁻", "lintegral", "lintegral_"),
        "Lower-bounding a Lebesgue integral by one point: `f a * μ {a} ≤ ∫⁻ x, f x ∂μ` — prove a "
        "GENERIC `lintegral_singleton_le` (via `lintegral_mono` on an indicator + `lintegral_indicator`) "
        "and reuse it.",
    ),
    (
        ("truncated_expectation", "recurrence", "induction", "∑ ", "Finset"),
        "Recurrence/sum bound: prove the ONE-STEP step as its own lemma (`E 0 = 0`, "
        "`E (k+1) = 1 + E k · β`), then finish by induction on `k`.",
    ),
    (
        ("coea_sel_measure", "coea_measure", "A_ge", "A_lvl", "sel_cdf"),
        "These are project defs: `unfold`/`simp only [...]` them; for the best-of-λ CDF use the "
        "weight-level decomposition and telescide the `sel_cdf` differences. Do not redefine them.",
    ),
]


def pattern_hints(goal_src: str) -> list[str]:
    g = goal_src.lower()
    hits: list[str] = []
    for keys, hint in PATTERN_HINTS:
        if any(k.lower() in g or k in goal_src for k in keys) and hint not in hits:
            hits.append(hint)
    # Always-on strategic nudge mirroring how Aristotle cracked hard goals.
    hits.append(
        "If you cannot close this directly, introduce a small GENERIC helper lemma "
        "(state it, prove it first, then use it) — general facts are easier and reusable."
    )
    return hits


def _build_refine_prompt(
    goal_src: str,
    premises: list[str],
    defs: list[str],
    hints: list[str],
    prev: str | None,
    fb: str | None,
) -> str:
    """OProver prompt template (paper App. B.1), single template across all rounds, augmented
    with the in-scope definitions of the goal's symbols."""
    refs = "\n\n".join(premises[:6]) if premises else "(none)"
    defs_blk = "\n\n".join(defs) if defs else "(none)"
    return (
        "**Current Task:**\nComplete the following Lean 4 code:\n\n"
        f"```lean\n{goal_src}\n```\n\n"
        "Before producing the Lean 4 proof, first provide a concise proof plan summarizing the "
        "intended strategy, key lemmas, and proof structure. If a previous attempt and Lean "
        "feedback are provided, revise the proof accordingly. Output the COMPLETE file (imports, "
        "any helper lemmas, and the theorem with its proof) in ONE ```lean block, with no `sorry`. "
        "Keep the theorem statement EXACTLY as given — do not weaken or change it. The definitions "
        "below already exist (via the imports); `unfold`/`simp only [...]` them — do NOT redefine "
        "them.\n\n"
        f"Definitions in scope (do NOT redefine):\n{defs_blk}\n\n"
        f"Strategy hints:\n{chr(10).join('- ' + h for h in hints) if hints else '(none)'}\n\n"
        f"Reference theorems and proofs:\n{refs}\n\n"
        f"Previous Failed Attempt:\n{prev.strip() if prev else '(none)'}\n\n"
        f"Lean Feedback:\n{fb.strip() if fb else '(none)'}\n"
    )


def prove_leaf(
    goal_src: str,
    project_root: Path,
    sketch: str,
    premises: list[str],
    rounds: int | None = None,
    width: int = 4,
    deadline: float | None = None,
    prompt_override=None,
) -> str | None:
    """OProver agentic refinement loop (arXiv:2605.17283 §2.1): the prover is the TRAINED policy
    over state (statement, retrieved proofs, prev attempt, raw Lean feedback). Compact state —
    only the most recent attempt+feedback is carried. Compiler in the loop; accept only when the
    candidate is lake-clean, sorry-free, AND preserves our exact statement. qwen escalation/split
    happens above in solve(); this loop is oprover-only (the policy that was trained on it).

    `rounds` overrides REFINE_ROUNDS (used by the refutation probe with a smaller budget)."""
    total_rounds = rounds if rounds is not None else REFINE_ROUNDS
    sys_msg = (
        "You are OProver, a Lean 4 theorem prover. Given a goal to complete, relevant "
        "retrieved lemmas, and (after round 1) your previous attempt with raw Lean compiler "
        "feedback, produce a concise proof plan then the full corrected file in one ```lean "
        "block with no `sorry`."
    )
    refs = (
        ([f"Proof idea (strategy hint): {sketch}"] + list(premises)) if sketch else list(premises)
    )
    defs = definitions_for_goal(goal_src, project_root)
    hints = pattern_hints(goal_src)
    LOG.info(
        "  prove_leaf: %d in-scope definitions, %d premises, %d pattern hints",
        len(defs),
        len(premises),
        len(hints),
    )
    k = max(1, width)
    branches = [(None, None)] * k
    rnd = 0
    # Session id for trajectory recording (use pipeline run id or generate one)
    _traj_run_id = _PROG.get("task", "") or datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    _traj_node = _PROG.get("task", "")
    trajectory.begin_session(
        run_id=_traj_run_id, node_id=_traj_node, prover="oprover", project_root=project_root
    )
    while True:
        rnd += 1
        if deadline is not None:
            if time.time() > deadline:
                LOG.info("  prove_leaf: wall-clock deadline reached at round %d, UNPROVED", rnd - 1)
                prog(
                    project_root,
                    f"deadline reached after {rnd - 1} rounds — UNPROVED",
                    status="unproved",
                )
                trajectory.end_session()
                return None
            budget_label = f"round {rnd} (until deadline)"
        else:
            if rnd > total_rounds:
                break
            budget_label = f"round {rnd}/{total_rounds}"
        next_branches = []
        for i, (prev, fb) in enumerate(branches):
            LOG.info(
                "  prove_leaf r%d b%d: querying %s (gen<=%d, T=%.1f)",
                rnd,
                i,
                ROLE_PROVER,
                GEN_PER_ROUND,
                REFINE_TEMP,
            )
            prog(project_root, f"Proving — {budget_label}, branch {i} (oprover-8b)", round=rnd)
            content = (
                prompt_override(prev, fb)
                if prompt_override
                else _build_refine_prompt(goal_src, refs, defs, hints, prev, fb)
            )
            t0_call = time.time()
            prompt_msgs = [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": content},
            ]
            try:
                out = chat(
                    ROLE_PROVER, prompt_msgs, max_tokens=GEN_PER_ROUND, temperature=REFINE_TEMP
                )
            except Exception as e:  # noqa: BLE001 — one bad API response must not kill the whole run
                LOG.warning(
                    "  prove_leaf r%d b%d: chat failed (%s) -> keep prior state, continue",
                    rnd,
                    i,
                    e,
                )
                trajectory.record_proving_step(
                    run_id=_traj_run_id,
                    node_id=_traj_node,
                    prover="oprover",
                    round=rnd,
                    branch=i,
                    phase="generate",
                    gate="chat_error",
                    prompt={
                        "messages": [
                            {"role": m["role"], "content": m["content"][:500]} for m in prompt_msgs
                        ]
                    },
                    latency_s=round(time.time() - t0_call, 3),
                    temperature=REFINE_TEMP,
                    max_tokens=GEN_PER_ROUND,
                    metadata={"error": str(e)[:200]},
                    project_root=project_root,
                )
                next_branches.append((prev, fb))
                continue
            cand = apply_generated_proof(goal_src, out)
            if not cand:
                LOG.info("  prove_leaf r%d b%d: no lean block extracted -> retry", rnd, i)
                trajectory.record_proving_step(
                    run_id=_traj_run_id,
                    node_id=_traj_node,
                    prover="oprover",
                    round=rnd,
                    branch=i,
                    phase="generate",
                    gate="no_block",
                    prompt={
                        "messages": [
                            {"role": m["role"], "content": m["content"][:500]} for m in prompt_msgs
                        ]
                    },
                    model_output=out[:4000],
                    latency_s=round(time.time() - t0_call, 3),
                    temperature=REFINE_TEMP,
                    max_tokens=GEN_PER_ROUND,
                    project_root=project_root,
                )
                next_branches.append((None, None))
                continue
            for imp in _imports_of(
                goal_src
            ).splitlines():  # premise injection: re-prepend dropped imports/opens
                if imp.strip() and imp.strip() not in cand:
                    cand = imp + "\n" + cand
            if not _statement_preserved(goal_src, cand):
                LOG.info(
                    "  prove_leaf r%d b%d: REJECTED — statement changed (soundness guard)", rnd, i
                )
                LOG.debug("    expected sig: %r", _goal_signature(goal_src))
                LOG.debug("    cand sig    : %r", _goal_signature(cand))
                trajectory.record_proving_step(
                    run_id=_traj_run_id,
                    node_id=_traj_node,
                    prover="oprover",
                    round=rnd,
                    branch=i,
                    phase="gate",
                    gate="statement_changed",
                    prompt={
                        "messages": [
                            {"role": m["role"], "content": m["content"][:500]} for m in prompt_msgs
                        ]
                    },
                    model_output=out[:4000],
                    candidate=cand[:4000],
                    latency_s=round(time.time() - t0_call, 3),
                    temperature=REFINE_TEMP,
                    max_tokens=GEN_PER_ROUND,
                    project_root=project_root,
                )
                next_branches.append(
                    (
                        cand,
                        (
                            "You changed the theorem statement. You MUST prove EXACTLY this "
                            f"statement, verbatim:\n{_goal_signature(goal_src)}"
                        ),
                    )
                )
                continue
            forbidden = forbidden_placeholders(cand)
            if forbidden:
                LOG.info(
                    "  prove_leaf r%d b%d: candidate still has placeholders %s -> refine",
                    rnd,
                    i,
                    forbidden,
                )
                trajectory.record_proving_step(
                    run_id=_traj_run_id,
                    node_id=_traj_node,
                    prover="oprover",
                    round=rnd,
                    branch=i,
                    phase="gate",
                    gate="forbidden_placeholder",
                    prompt={
                        "messages": [
                            {"role": m["role"], "content": m["content"][:500]} for m in prompt_msgs
                        ]
                    },
                    model_output=out[:4000],
                    candidate=cand[:4000],
                    latency_s=round(time.time() - t0_call, 3),
                    temperature=REFINE_TEMP,
                    max_tokens=GEN_PER_ROUND,
                    metadata={"forbidden": forbidden},
                    project_root=project_root,
                )
                next_branches.append(
                    (
                        cand,
                        "Your proof still contains a forbidden placeholder (`sorry`, `admit`, `exact?`, `sorryAx`, or `axiom`). Provide a complete proof.",
                    )
                )
                continue
            r = compile_lean_file(project_root=project_root, lean_file=_scratch(project_root, cand))
            if r.ok:
                saved = project_root / ".mathprover" / "pipeline" / "proved"
                saved.mkdir(parents=True, exist_ok=True)
                name = (
                    re.search(r"\b(?:theorem|lemma)\s+([A-Za-z0-9_']+)", cand) or [None, "leaf"]
                )[1]
                out_f = saved / f"{name}.lean"
                out_f.write_text(cand, encoding="utf-8")
                LOG.info(
                    "  prove_leaf r%d b%d: VERIFIED (lake-clean, sorry-free, statement preserved) -> %s",
                    rnd,
                    i,
                    out_f,
                )
                prog(
                    project_root,
                    f"VERIFIED at round {rnd} (lake-clean, sorry-free) — PROVED",
                    status="proved",
                    result="PROVED",
                )
                trajectory.record_proving_step(
                    run_id=_traj_run_id,
                    node_id=_traj_node,
                    prover="oprover",
                    round=rnd,
                    branch=i,
                    phase="compile",
                    gate="compile_ok",
                    prompt={
                        "messages": [
                            {"role": m["role"], "content": m["content"][:500]} for m in prompt_msgs
                        ]
                    },
                    model_output=out[:4000],
                    candidate=cand[:4000],
                    compile_ok=True,
                    compile_feedback=r.combined[:4000],
                    latency_s=round(time.time() - t0_call, 3),
                    temperature=REFINE_TEMP,
                    max_tokens=GEN_PER_ROUND,
                    metadata={"proof_path": str(out_f)},
                    project_root=project_root,
                )
                trajectory.end_session()
                return cand
            new_fb = ANSI_RE.sub("", r.error_excerpt(4000))
            first = (new_fb.splitlines() or [""])[0][:140]
            LOG.info("  prove_leaf r%d b%d: compile FAIL -> refine :: %s", rnd, i, first)
            prog(project_root, f"compile FAIL (r{rnd} b{i}): {first}")
            trajectory.record_proving_step(
                run_id=_traj_run_id,
                node_id=_traj_node,
                prover="oprover",
                round=rnd,
                branch=i,
                phase="compile",
                gate="compile_fail",
                prompt={
                    "messages": [
                        {"role": m["role"], "content": m["content"][:500]} for m in prompt_msgs
                    ]
                },
                model_output=out[:4000],
                candidate=cand[:4000],
                compile_ok=False,
                compile_feedback=new_fb,
                latency_s=round(time.time() - t0_call, 3),
                temperature=REFINE_TEMP,
                max_tokens=GEN_PER_ROUND,
                metadata={"feedback_head": first},
                project_root=project_root,
            )
            next_branches.append((cand, new_fb))
        branches = next_branches
    LOG.info(
        "  prove_leaf: exhausted %d refinement rounds on %d branches, UNPROVED", total_rounds, k
    )
    prog(project_root, f"exhausted {total_rounds} rounds — UNPROVED", status="unproved")
    trajectory.end_session()
    return None


def build_negation_goal(goal_src: str) -> str | None:
    """Refutation scaffold (Aristotle's LBT lesson): turn `theorem NAME <binders> : CONCL := by
    sorry` into `theorem NAME_is_false : ¬ (∀ <binders>, CONCL) := by sorry`, preserving the
    file's imports/opens/namespace. Proving THIS sorry-free is a machine-checked counterexample,
    i.e. proof the original statement is FALSE (e.g. a missing hypothesis like `z_j ≤ 1`)."""
    m = re.search(r"\b(theorem|lemma)\s+([A-Za-z0-9_'.]+)", goal_src)
    if not m:
        return None
    name = m.group(2)
    after = goal_src[m.end() :]
    depth = 0
    colon = -1
    assign = -1
    i = 0
    while i < len(after):
        two = after[i : i + 2]
        c = after[i]
        if two == ":=" and depth == 0:
            assign = i
            break
        if c in "([{⟨":
            depth += 1
        elif c in ")]}⟩":
            depth -= 1
        elif c == ":" and depth == 0 and colon < 0:
            colon = i
        i += 1
    if colon < 0 or assign < 0:
        return None
    binders = after[:colon].strip()
    concl = after[colon + 1 : assign].strip()
    neg = (
        f"theorem {name}_is_false :\n    ¬ (∀ {binders},\n    {concl}) := by\n  sorry\n"
        if binders
        else f"theorem {name}_is_false : ¬ ({concl}) := by\n  sorry\n"
    )
    # Splice: preamble (imports/opens/namespace) up to the decl keyword, then the negation,
    # then any trailing lines after the original `:= by ...` proof (e.g. `end Namespace`).
    decl_start = m.start()
    proof_rest = after[assign:]
    tail = ""
    mt = re.search(r"\n(end\b[^\n]*)\s*$", proof_rest)
    if mt:
        tail = "\n" + mt.group(1) + "\n"
    return goal_src[:decl_start] + neg + tail


def refute(goal_src: str, project_root: Path, rounds: int = 4) -> str | None:
    """Try to DISPROVE the goal: build `¬(∀ …)` and run the agentic loop on it (bounded budget).
    Returns the verified counterexample proof if found, else None. This is the diagnose-before-
    grind step Aristotle used to catch a false (axiom-quarantined) theorem."""
    neg = build_negation_goal(goal_src)
    if not neg:
        LOG.info("refute: could not build a negation goal (signature parse failed)")
        return None
    LOG.info("refute: attempting counterexample (<=%d rounds):\n%s", rounds, neg.strip())
    premises = retrieve_premises(neg, project_root)
    proof = prove_leaf(neg, project_root, "", premises, rounds=rounds, width=1)
    if proof:
        LOG.info("refute: COUNTEREXAMPLE FOUND — the original statement is FALSE")
    else:
        LOG.info("refute: no counterexample within budget (statement may be true)")
    return proof


def _scratch(project_root: Path, content: str) -> Path:
    d = project_root / ".mathprover" / "pipeline"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "scratch.lean"
    f.write_text(content)
    return f


def solve(goal_src: str, project_root: Path, depth: int, max_depth: int, log) -> bool:
    n = prompt_tokens(goal_src)
    leaf = n <= INPUT_LIMIT
    log(f"{'  ' * depth}{n} tok {'[leaf]' if leaf else '[over budget]'}")
    if depth == 0:
        architecture = build_architecture(goal_src, project_root)
        arch_dir = project_root / ".mathprover" / "pipeline"
        arch_dir.mkdir(parents=True, exist_ok=True)
        arch_path = arch_dir / f"{architecture.theorem}.architecture.md"
        arch_path.write_text(render_markdown(architecture, []), encoding="utf-8")
        log(f"architect-proof: wrote {arch_path}")
    premises = retrieve_premises(goal_src, project_root)
    if leaf:
        log(f"{'  ' * depth}  proving leaf directly (oprover->qwen)...")
        proof = prove_leaf(goal_src, project_root, "", premises)
        if proof:
            log(f"{'  ' * depth}  PROVED (lake-verified)")
            return True
        log(f"{'  ' * depth}  direct prove failed -> strategize for a sketch + retry")
        strat = strategize(goal_src, premises)
        log(f"{'  ' * depth}  strategist: action={strat['action']} sketch={strat['sketch'][:80]!r}")
        if strat["action"] == "solve":
            proof = prove_leaf(goal_src, project_root, strat["sketch"], premises)
            if proof:
                log(f"{'  ' * depth}  PROVED (with sketch, lake-verified)")
                return True
        log(f"{'  ' * depth}  leaf still unproved -> decomposing further (local)")
        # fall through to decomposition (local Aristotle: recurse, never cloud)
    if depth >= max_depth:
        log(f"{'  ' * depth}  max depth reached; UNPROVED (local).")
        return False
    split = propose_split(goal_src, premises)
    if not verify_split(goal_src, split, project_root):
        log(
            f"{'  ' * depth}  split REJECTED by compiler (does not entail parent); UNPROVED (local)."
        )
        return False
    log(
        f"{'  ' * depth}  split ENTAILS parent (compiler-checked): {[s['name'] for s in split['sublemmas']]}"
    )
    return all(
        solve(s["statement"], project_root, depth + 1, max_depth, log) for s in split["sublemmas"]
    )


def prove_node_longrun(
    root: Path, node: str, *, prompt_style: str, max_hours: float, max_rounds: int, logpath: Path
) -> None:
    """Prove a node's `attempt.lean` directly, for hours if asked, with the chosen prompt style
    (`oprover` = our OProver template; `aristotle` = the EXACT Aristotle execution prompt) and a
    live Aristotle-style progress dashboard. Writes the verified proof back to attempt.lean."""
    proof_dir = root / "proofs" / node
    attempt_file = proof_dir / "attempt.lean"
    if not attempt_file.exists():
        LOG.error("no attempt.lean for node %s", node)
        print("RESULT: NOT PROVED")
        return
    src = attempt_file.read_text(encoding="utf-8")
    deadline = (time.time() + max_hours * 3600.0) if max_hours > 0 else None
    budget = f"{max_hours}h" if deadline else f"{max_rounds} rounds"
    init_progress(root, task=node, mode=f"prove ({prompt_style})", budget=budget)
    LOG.info("goal (node %s):\n%s", node, src.strip()[:1200])
    override = None
    if prompt_style == "aristotle":
        override = lambda prev, fb: aristotle_user_prompt(proof_dir, attempt_file, root, prev, fb)  # noqa: E731
    premises = retrieve_premises(src, root)
    proof = prove_leaf(
        src,
        root,
        "",
        premises,
        rounds=(None if deadline else max_rounds),
        width=1,
        deadline=deadline,
        prompt_override=override,
    )
    if proof:
        attempt_file.write_text(proof, encoding="utf-8")
        LOG.info("RESULT: PROVED (written to %s)", attempt_file)
        print(f"RESULT: PROVED  (node {node}; log: {logpath})")
    else:
        LOG.info("RESULT: NOT PROVED (node %s)", node)
        print(f"RESULT: NOT PROVED  (node {node}; log: {logpath})")


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--goal-file")
    ap.add_argument("--informal")
    ap.add_argument("--node", help="prove proofs/<NODE>/attempt.lean directly (long-run capable)")
    ap.add_argument(
        "--prompt",
        choices=["oprover", "aristotle"],
        default="oprover",
        help="prompt style for --node: our OProver template, or the EXACT Aristotle prompt",
    )
    ap.add_argument(
        "--max-hours",
        type=float,
        default=0.0,
        help="run the node prover until proved or this many hours elapse (0 = use --max-rounds)",
    )
    ap.add_argument(
        "--max-rounds", type=int, default=8, help="refinement-round cap when --max-hours=0"
    )
    ap.add_argument(
        "--project-root", default=str(Path.home() / "projects" / "lean-runtime-analysis")
    )
    ap.add_argument("--max-depth", type=int, default=3)
    ap.add_argument(
        "--refute",
        action="store_true",
        help="only attempt to DISPROVE the goal (build ¬(∀…) and prove it)",
    )
    ap.add_argument(
        "--refute-first",
        type=int,
        default=0,
        metavar="N",
        help="before proving, spend N rounds trying to disprove; stop if a counterexample is found",
    )
    a = ap.parse_args()
    root = Path(a.project_root)
    logpath = init_log(root)
    if a.node:
        prove_node_longrun(
            root,
            a.node,
            prompt_style=a.prompt,
            max_hours=a.max_hours,
            max_rounds=a.max_rounds,
            logpath=logpath,
        )
        return
    src = Path(a.goal_file).read_text() if a.goal_file else autoformalize(a.informal, root)
    if not src:
        LOG.error("autoformalize FAILED (no compiling statement)")
        print("RESULT: NOT PROVED")
        return
    LOG.info("goal:\n%s", src.strip())
    if a.refute:
        cex = refute(src, root, rounds=max(a.max_depth, 4))
        verdict = "FALSE (counterexample found)" if cex else "no counterexample within budget"
        LOG.info("RESULT: %s", verdict)
        print(f"RESULT: {verdict}  (log: {logpath})")
        return
    if a.refute_first:
        cex = refute(src, root, rounds=a.refute_first)
        if cex:
            LOG.info("RESULT: FALSE — original statement disproved; not attempting to prove it")
            print(f"RESULT: FALSE (counterexample found)  (log: {logpath})")
            return
        LOG.info("refute-first: no counterexample; proceeding to prove")
    ok = solve(src, root, 0, a.max_depth, LOG.info)
    LOG.info("RESULT: %s", "PROVED" if ok else "NOT PROVED")
    print(f"RESULT: {'PROVED' if ok else 'NOT PROVED'}  (log: {logpath})")


if __name__ == "__main__":
    main()
