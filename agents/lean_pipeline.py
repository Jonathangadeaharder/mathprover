"""Lean compile/extract helpers shared by Goedel and Aristotle backends."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tarfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CompileResult:
    ok: bool
    stdout: str
    stderr: str
    combined: str

    def error_excerpt(self, max_chars: int = 8000) -> str:
        text = self.combined.strip() or self.stderr.strip() or self.stdout.strip()
        if len(text) <= max_chars:
            return text
        half = max_chars // 2
        return text[:half] + "\n\n[... truncated ...]\n\n" + text[-half:]


def extract_lean4_blocks(text: str) -> list[str]:
    patterns = [
        r"```lean4\n(.*?)\n```",
        r"```lean4\n(.*?)```",
        r"```lean\n(.*?)```",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        if matches:
            return [m.strip() for m in matches if m.strip()]
    return []


def replace_first_sorry(source: str, proof_body: str) -> str:
    proof_body = proof_body.strip()
    if proof_body.startswith("by "):
        proof_body = proof_body[3:].lstrip()
    if proof_body.startswith("by\n"):
        proof_body = proof_body[3:].lstrip()
    idx = source.find("sorry")
    if idx < 0:
        return source
    return source[:idx] + proof_body + source[idx + len("sorry") :]


def apply_generated_proof(original: str, model_output: str) -> str | None:
    blocks = extract_lean4_blocks(model_output)
    if not blocks:
        return None
    code = blocks[-1].strip()
    if not code:
        return None

    if "sorry" not in code:
        if "import " in code:
            return code
        if re.search(r"\b(theorem|lemma)\b", code) and "sorry" in original:
            tail = code.split(":= by", 1)[-1] if ":= by" in code else code
            merged = replace_first_sorry(original, tail)
            if "sorry" not in merged:
                return merged
        if re.search(r"\b(theorem|lemma)\b", code):
            return code

    if "sorry" in original:
        return replace_first_sorry(original, code)
    return None


def _resolve_lake() -> str:
    """Find `lake` even when PATH lacks elan (UI/agent subprocesses often do)."""
    import shutil

    found = shutil.which("lake")
    if found:
        return found
    cand = Path.home() / ".elan" / "bin" / "lake"
    return str(cand) if cand.exists() else "lake"


def compile_lean_file(
    *, project_root: Path, lean_file: Path, timeout_s: int = 600
) -> CompileResult:
    env = os.environ.copy()
    elan_bin = str(Path.home() / ".elan" / "bin")
    if elan_bin not in env.get("PATH", ""):
        env["PATH"] = elan_bin + os.pathsep + env.get("PATH", "")
    cmd = [_resolve_lake(), "env", "lean", str(lean_file.resolve())]
    proc = subprocess.run(
        cmd,
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout_s,
        env=env,
    )
    combined = proc.stdout or ""
    return CompileResult(
        ok=proc.returncode == 0,
        stdout=combined,
        stderr="",
        combined=combined,
    )


def strip_lean_comments(text: str) -> str:
    """Remove Lean line comments (`-- …`) and (nestable) block comments (`/- … -/`).

    Placeholder scans must run on *active code only*: a documented `sorry`/`axiom` inside a
    comment is not a real placeholder. (A clean Aristotle disproof was once false-rejected because
    its module docstring mentioned `sorry`.)
    """
    out: list[str] = []
    i, n, depth = 0, len(text), 0
    while i < n:
        if depth == 0 and text.startswith("--", i):
            j = text.find("\n", i)
            if j < 0:
                break
            i = j  # keep the newline, drop the comment body
            continue
        if text.startswith("/-", i):
            depth += 1
            i += 2
            continue
        if depth > 0 and text.startswith("-/", i):
            depth -= 1
            i += 2
            continue
        if depth == 0:
            out.append(text[i])
        i += 1
    return "".join(out)


def has_sorry(text: str) -> bool:
    return bool(re.search(r"\bsorry\b", strip_lean_comments(text)))


FORBIDDEN_PLACEHOLDER_RE = re.compile(
    r"(?<![A-Za-z0-9_'.])(sorry|admit|exact\?|sorryAx)(?![A-Za-z0-9_'.])"
)
AXIOM_DECL_RE = re.compile(r"^\s*axiom\s+[A-Za-z0-9_'.]+", re.M)
DECL_NAME_RE = re.compile(r"\b(?:theorem|lemma)\s+([A-Za-z0-9_'.]+)")
STANDARD_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}


def forbidden_placeholders(text: str) -> list[str]:
    """Return proof placeholders that must not survive a successful run, scanning ACTIVE CODE
    ONLY (comments stripped first).

    Lean treats `sorry` as a warning, and `exact?` can be left as an interactive
    query in text. A successful proof artifact should contain neither, and it
    must not smuggle in a new `axiom`.
    """
    code = strip_lean_comments(text)
    seen: list[str] = []
    for match in FORBIDDEN_PLACEHOLDER_RE.finditer(code):
        token = match.group(1)
        if token not in seen:
            seen.append(token)
    if AXIOM_DECL_RE.search(code) and "axiom" not in seen:
        seen.append("axiom")
    return seen


def theorem_names(text: str) -> list[str]:
    return [m.group(1) for m in DECL_NAME_RE.finditer(text)]


def axiom_check(
    *, project_root: Path, lean_file: Path, theorem: str | None = None, timeout_s: int = 600
) -> CompileResult:
    """Compile a copy of `lean_file` with `#print axioms <theorem>` appended."""
    source = lean_file.read_text(encoding="utf-8")
    names = theorem_names(source)
    target = theorem or (names[-1] if names else None)
    if target is None:
        return CompileResult(
            ok=False,
            stdout="",
            stderr="",
            combined="could not infer theorem/lemma name for axiom check",
        )
    work = project_root / ".mathprover" / "axiom_check"
    work.mkdir(parents=True, exist_ok=True)
    temp = work / f"{lean_file.stem}.{target}.axioms.lean"
    temp.write_text(source.rstrip() + f"\n\n#print axioms {target}\n", encoding="utf-8")
    return compile_lean_file(project_root=project_root, lean_file=temp, timeout_s=timeout_s)


def unexpected_axioms(output: str) -> list[str]:
    """Extract custom axioms from Lean's `#print axioms` output conservatively."""
    found: list[str] = []
    for line in output.splitlines():
        if "axiom" not in line.lower():
            continue
        bracket = re.search(r"\[([^\]]*)\]", line)
        if not bracket:
            continue
        for raw in bracket.group(1).split(","):
            axiom = raw.strip()
            if axiom and axiom not in STANDARD_AXIOMS and axiom not in found:
                found.append(axiom)
    return found


def final_verify_attempt(
    *, project_root: Path, lean_file: Path, theorem: str | None = None
) -> tuple[bool, str]:
    """Final Aristotle-style proof gate: compile, placeholders, then axiom print."""
    source = lean_file.read_text(encoding="utf-8")
    forbidden = forbidden_placeholders(source)
    if forbidden:
        return False, "forbidden placeholders remain: " + ", ".join(forbidden)
    compile_result = compile_lean_file(project_root=project_root, lean_file=lean_file)
    if not compile_result.ok:
        return False, "compile failed:\n" + compile_result.error_excerpt()
    axiom_result = axiom_check(project_root=project_root, lean_file=lean_file, theorem=theorem)
    if not axiom_result.ok:
        return False, "axiom check failed:\n" + axiom_result.error_excerpt()
    custom = [
        ax
        for ax in unexpected_axioms(axiom_result.combined)
        if ax not in STANDARD_AXIOMS and ax not in theorem_names(source)
    ]
    if custom:
        return False, "unexpected/custom axioms may be present:\n" + axiom_result.error_excerpt()
    return True, axiom_result.combined.strip() or "axiom check completed"


def write_if_compiles(
    *,
    project_root: Path,
    candidate: str,
    target: Path,
    work_dir: Path,
) -> CompileResult | None:
    work_dir.mkdir(parents=True, exist_ok=True)
    temp = work_dir / f"{target.name}.candidate.lean"
    temp.write_text(candidate, encoding="utf-8")
    result = compile_lean_file(project_root=project_root, lean_file=temp)
    if result.ok and not forbidden_placeholders(candidate):
        target.write_text(candidate, encoding="utf-8")
        return result
    return None


def _safe_extractall(tar: tarfile.TarFile, destination: Path) -> None:
    dest = destination.resolve()
    for member in tar.getmembers():
        target = (dest / member.name).resolve()
        if not str(target).startswith(str(dest) + os.sep) and target != dest:
            raise tarfile.TarError(f"unsafe path in archive: {member.name}")
    if sys.version_info >= (3, 12):
        tar.extractall(dest, filter="data")
    else:
        for member in tar.getmembers():
            tar.extract(member, dest)


def extract_tarball(archive: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:*") as tar:
        _safe_extractall(tar, destination)
    return destination


def find_attempt_lean(root: Path, *, rel_hint: str | None = None) -> Path | None:
    if rel_hint:
        direct = root / rel_hint
        if direct.is_file():
            return direct
    matches = sorted(root.rglob("attempt.lean"))
    if not matches:
        return None
    if rel_hint:
        for path in matches:
            if path.as_posix().endswith(rel_hint):
                return path
    return matches[0]
