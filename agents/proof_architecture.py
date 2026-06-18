#!/usr/bin/env python3
"""Proof-architecture helpers learned from the Aristotle A3a run.

This module is intentionally lightweight: it does not prove anything by itself.
It gives the planner and workers durable artifacts for hard Lean goals:

* `architect-proof`: a semantic spine plus helper-lemma DAG scaffold.
* `scratch-probe`: a disposable Lean file for `#check`, imports, private helper access.
* `final-verify`: compile + placeholder scan + `#print axioms`.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from lean_pipeline import final_verify_attempt

DECL_RE = re.compile(r"\b(?:theorem|lemma)\s+([A-Za-z0-9_'.]+)")
IMPORT_OPEN_RE = re.compile(r"^\s*(?:import|open)\b.*$", re.M)
PRIVATE_RE = re.compile(
    r"^\s*(?:private\s+)?(?:noncomputable\s+)?(?:lemma|theorem|def|abbrev)\s+([A-Za-z0-9_'.]+)",
    re.M,
)


@dataclass
class HelperNode:
    name: str
    purpose: str
    depends_on: list[str]
    status: str = "planned"


@dataclass
class ProofArchitecture:
    theorem: str
    semantic_spine: list[str]
    scratch_probe_goals: list[str]
    helper_dag: list[HelperNode]
    final_gates: list[str]


def _theorem_name(source: str) -> str:
    if "sorry" in source:
        before_sorry = source[: source.find("sorry")]
        matches = list(DECL_RE.finditer(before_sorry))
        if matches:
            return matches[-1].group(1)
    matches = list(DECL_RE.finditer(source))
    return matches[-1].group(1) if matches else "target_theorem"


def _goal_terms(source: str) -> list[str]:
    head = source.split(":=", 1)[0]
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_']*", head)
    skip = {
        "theorem",
        "lemma",
        "by",
        "Prop",
        "Type",
        "Nat",
        "Int",
        "Real",
        "Set",
        "Finset",
        "Measure",
        "MeasureTheory",
        "ProbabilityTheory",
        "ENNReal",
        "Classical",
    }
    out: list[str] = []
    for token in tokens:
        if len(token) <= 2 or token in skip or token in out:
            continue
        out.append(token)
    return out[:18]


def discover_private_helpers(
    project_root: Path, terms: list[str], limit: int = 20
) -> list[dict[str, str]]:
    helpers: list[dict[str, str]] = []
    for lean_file in sorted(project_root.glob("*.lean")):
        text = lean_file.read_text(encoding="utf-8", errors="ignore")
        for match in PRIVATE_RE.finditer(text):
            name = match.group(1)
            if terms and not any(term in name or name in term for term in terms):
                continue
            helpers.append({"name": name, "module": lean_file.stem, "file": lean_file.name})
            if len(helpers) >= limit:
                return helpers
    return helpers


def build_architecture(source: str, project_root: Path) -> ProofArchitecture:
    theorem = _theorem_name(source)
    terms = _goal_terms(source)
    private_helpers = discover_private_helpers(project_root, terms)
    helper_hint = private_helpers[0]["name"] if private_helpers else "existing_project_bridge"

    return ProofArchitecture(
        theorem=theorem,
        semantic_spine=[
            "Pin the original theorem statement and identify the mathematical invariant/value function.",
            "Create a concrete one-step operator or bridge lemma that exposes the transition as a finite sum.",
            "Prove boundary/base cases before the interior recurrence.",
            "Prove the harmonicity or recurrence lemma for the target value.",
            "Prove the strict inequality/subsolution/drift core as its own helper.",
            "Assemble the final theorem from the generic principle and concrete helpers.",
        ],
        scratch_probe_goals=[
            "Check imports and namespace opens from the target file.",
            "Run #check on candidate public and private helper lemmas.",
            "If a needed helper is private, test Batteries.Tactic.OpenPrivate in scratch before editing the target.",
            "Test tiny concrete instances or negated forms when a helper may be false.",
        ],
        helper_dag=[
            HelperNode(
                "generic_principle",
                "Finite maximum/induction/recurrence principle matching the theorem shape.",
                [],
            ),
            HelperNode(
                "concrete_operator",
                "Expose the project transition/kernel/operator in the form the principle expects.",
                [],
            ),
            HelperNode(
                "kernel_or_state_bridge",
                f"Bridge target notation to existing project helpers such as {helper_hint}.",
                ["concrete_operator"],
            ),
            HelperNode(
                "boundary_values",
                "Close target and stopping/base cases explicitly.",
                ["kernel_or_state_bridge"],
            ),
            HelperNode(
                "harmonicity_or_recursion",
                "Show the value function satisfies the one-step recurrence off the boundary.",
                ["boundary_values"],
            ),
            HelperNode(
                "strict_subsolution_or_drift",
                "Prove the analytic/combinatorial core inequality separately.",
                ["kernel_or_state_bridge"],
            ),
            HelperNode(
                "main_assembly",
                "Use the generic principle plus helpers to close the pinned theorem.",
                ["generic_principle", "harmonicity_or_recursion", "strict_subsolution_or_drift"],
            ),
        ],
        final_gates=[
            "lake env lean <attempt.lean>",
            "grep for sorry, admit, exact?, sorryAx, axiom",
            "#print axioms <theorem>",
            "confirm the theorem statement was not weakened or edited",
        ],
    )


def render_markdown(architecture: ProofArchitecture, private_helpers: list[dict[str, str]]) -> str:
    lines = [f"# Proof Architecture: {architecture.theorem}", ""]
    lines.append("## Semantic Spine")
    lines.extend(f"- {item}" for item in architecture.semantic_spine)
    lines.append("")
    lines.append("## Scratch Probe")
    lines.extend(f"- {item}" for item in architecture.scratch_probe_goals)
    if private_helpers:
        lines.append("")
        lines.append("## Candidate Private Helpers")
        lines.extend(
            f"- `{h['name']}` from `{h['module']}` (`{h['file']}`)" for h in private_helpers
        )
    lines.append("")
    lines.append("## Helper DAG")
    for node in architecture.helper_dag:
        deps = ", ".join(node.depends_on) if node.depends_on else "none"
        lines.append(f"- `{node.name}` ({node.status}; depends on: {deps}) - {node.purpose}")
    lines.append("")
    lines.append("## Final Gates")
    lines.extend(
        f"- `{gate}`" if gate.startswith(("lake", "grep", "#print")) else f"- {gate}"
        for gate in architecture.final_gates
    )
    lines.append("")
    return "\n".join(lines)


def write_scratch_probe(
    *, project_root: Path, goal_file: Path, names: list[str], open_private_from: str | None
) -> Path:
    source = goal_file.read_text(encoding="utf-8")
    imports = [
        line
        for line in IMPORT_OPEN_RE.findall(source)
        if not line.strip().startswith("open private ")
    ]
    if "import Batteries.Tactic.OpenPrivate" not in source:
        imports.insert(1 if imports else 0, "import Batteries.Tactic.OpenPrivate")
    body = "\n".join(dict.fromkeys(line.strip() for line in imports if line.strip()))
    if open_private_from and names:
        body += "\n\nopen private " + " ".join(names) + f" from {open_private_from}\n"
    body += "\n\n"
    body += "\n".join(f"#check @{name}" for name in names)
    body += "\n\nexample : True := trivial\n"
    work = project_root / ".mathprover" / "scratch"
    work.mkdir(parents=True, exist_ok=True)
    out = work / f"{goal_file.stem}.probe.lean"
    out.write_text(body, encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="MathProver proof architecture utilities.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    architect = sub.add_parser("architect-proof")
    architect.add_argument("--goal-file", required=True)
    architect.add_argument("--project-root", required=True)
    architect.add_argument("--out", default=None)
    architect.add_argument("--json", action="store_true")

    probe = sub.add_parser("scratch-probe")
    probe.add_argument("--goal-file", required=True)
    probe.add_argument("--project-root", required=True)
    probe.add_argument("--check", nargs="*", default=[])
    probe.add_argument("--open-private-from", default=None)

    verify = sub.add_parser("final-verify")
    verify.add_argument("--file", required=True)
    verify.add_argument("--project-root", required=True)
    verify.add_argument("--theorem", default=None)

    args = parser.parse_args()
    project_root = Path(args.project_root).resolve()
    if args.cmd == "architect-proof":
        goal = Path(args.goal_file).resolve()
        source = goal.read_text(encoding="utf-8")
        architecture = build_architecture(source, project_root)
        helpers = discover_private_helpers(project_root, _goal_terms(source))
        if args.json:
            text = json.dumps(asdict(architecture), indent=2)
        else:
            text = render_markdown(architecture, helpers)
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
        print(text)
    elif args.cmd == "scratch-probe":
        out = write_scratch_probe(
            project_root=project_root,
            goal_file=Path(args.goal_file).resolve(),
            names=args.check,
            open_private_from=args.open_private_from,
        )
        print(out)
    elif args.cmd == "final-verify":
        ok, message = final_verify_attempt(
            project_root=project_root,
            lean_file=Path(args.file).resolve(),
            theorem=args.theorem,
        )
        print(message)
        raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
