"""Select Goedel (local) vs Aristotle (cloud) for a proof node."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config import MathProverConfig


@dataclass
class RouteDecision:
    prover: str
    reason: str


def _normalize_node(node: str) -> str:
    return node.strip().removesuffix("/")


def _folder_for_node(node: str, config: MathProverConfig) -> str:
    node = _normalize_node(node)
    proofs = config.project_root / "proofs"
    if (proofs / node).is_dir():
        return node
    matches = sorted(p for p in proofs.glob(f"{node}*") if p.is_dir())
    if len(matches) == 1:
        return matches[0].name
    return node


def count_failures(proof_dir: Path) -> int:
    attempts_dir = proof_dir.parents[1] / ".mathprover" / "attempts" / proof_dir.name
    if not attempts_dir.exists():
        return 0
    return sum(1 for p in attempts_dir.glob("*.log") if p.stat().st_size > 0)


def has_subproofs(proof_dir: Path) -> bool:
    sub = proof_dir / "subproofs"
    return sub.exists() and any(sub.iterdir())


def select_prover(
    node: str,
    config: MathProverConfig,
    *,
    override: str | None = None,
    auto: bool = True,
) -> RouteDecision:
    if override and override != "auto":
        if override not in config.provers:
            raise ValueError(f"Unknown prover {override!r}; choose from {list(config.provers)}")
        return RouteDecision(override, f"manual override: {override}")

    folder = _folder_for_node(node, config)
    proof_dir = config.project_root / "proofs" / folder
    routing = config.routing

    capstone_folders = {c["folder"] for c in routing.capstone}
    if folder in capstone_folders or _normalize_node(node) == routing.capstone_node:
        return RouteDecision(
            routing.default_capstone,
            f"capstone node {folder} -> {routing.default_capstone}",
        )

    failures = count_failures(proof_dir)
    if failures >= routing.escalate_after_failures:
        return RouteDecision(
            routing.default_capstone,
            f"escalation after {failures} failed attempts",
        )

    if has_subproofs(proof_dir):
        return RouteDecision(
            routing.default_capstone,
            "subproof tree exists and leaf still stuck -> aristotle",
        )

    return RouteDecision(
        routing.default_leaf,
        f"frontier/second-wave leaf {folder} -> {routing.default_leaf}",
    )
