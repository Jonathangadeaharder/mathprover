"""Prompt builders for Goedel and Aristotle (translate published proofs)."""

from __future__ import annotations

from pathlib import Path

GOEDEL_COMPLETION_TEMPLATE = """\
Complete the following Lean 4 code:

```lean4
{formal_statement}```

{paper_section}Before producing the Lean 4 code to formally prove the given theorem, provide a detailed proof plan outlining the main proof steps and strategies.
The plan should highlight key ideas, intermediate lemmas, and proof structures that will guide the construction of the final formal proof."""

GOEDEL_CORRECTION_TEMPLATE = """\
The proof (Round {round_index}) is not correct. Following is the compilation error message from the Lean 4 compiler:

{error_message}

Before producing the Lean 4 code to formally prove the given theorem, provide a detailed analysis of the error message."""


def read_paper_source(proof_dir: Path, *, max_chars: int = 12000) -> str:
    path = proof_dir / "paper_source.md"
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8").strip()
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[... truncated ...]"
    return text


def paper_section_for_goedel(paper_text: str) -> str:
    if not paper_text:
        return ""
    return (
        "Published proof to translate (follow this structure; do not invent new mathematics):\n\n"
        f"{paper_text}\n\n"
    )


def build_goedel_initial_prompt(formal_statement: str, paper_text: str) -> str:
    return GOEDEL_COMPLETION_TEMPLATE.format(
        formal_statement=formal_statement.strip(),
        paper_section=paper_section_for_goedel(paper_text),
    )


def build_goedel_correction_message(*, round_index: int, error_message: str) -> str:
    return GOEDEL_CORRECTION_TEMPLATE.format(
        round_index=round_index,
        error_message=error_message.strip(),
    )


def build_aristotle_prompt(
    *,
    proof_dir: Path,
    attempt_file: Path,
    project_root: Path,
) -> str:
    rel_attempt = attempt_file.relative_to(project_root).as_posix()
    paper = read_paper_source(proof_dir)
    paper_block = ""
    if paper:
        paper_block = (
            "\n\nPublished proof to translate (follow this structure exactly; "
            "do not invent new mathematics):\n\n"
            f"{paper}\n"
        )

    return (
        f"Close ONLY the `sorry` in `{rel_attempt}`. Do not modify other files in the project.\n"
        "Use the existing definitions and helper lemmas already in that file and in the project.\n"
        "Mark the proof region with a comment `-- PROVIDED SOLUTION` immediately above the completed proof.\n"
        f"{paper_block}\n"
        "Replace the sorry with a complete proof that typechecks in this Lean 4.28 project."
    )
