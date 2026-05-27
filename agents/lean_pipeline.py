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


def compile_lean_file(*, project_root: Path, lean_file: Path, timeout_s: int = 600) -> CompileResult:
    cmd = ["lake", "env", "lean", str(lean_file.resolve())]
    proc = subprocess.run(
        cmd,
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout_s,
    )
    combined = proc.stdout or ""
    return CompileResult(
        ok=proc.returncode == 0,
        stdout=combined,
        stderr="",
        combined=combined,
    )


def has_sorry(text: str) -> bool:
    return bool(re.search(r"\bsorry\b", text))


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
    if result.ok and not has_sorry(candidate):
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
