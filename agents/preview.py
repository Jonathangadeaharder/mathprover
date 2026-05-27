#!/usr/bin/env python3
"""Print routing decision as JSON for the UI preview endpoint."""

from __future__ import annotations

import json
import sys
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parent
if str(AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(AGENTS_DIR))

from config import load_config  # noqa: E402
from dispatch import resolve_proof_folder  # noqa: E402
from router import select_prover  # noqa: E402


def preview(node: str, prover: str = "auto", project_root: Path | None = None) -> dict:
    config = load_config(project_root)
    folder = resolve_proof_folder(node, config.project_root)
    override = None if prover == "auto" else prover
    decision = select_prover(folder, config, override=override, auto=prover == "auto")
    return {
        "folder": folder,
        "prover": decision.prover,
        "reason": decision.reason,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("node", help="Node id or proofs/ folder name")
    parser.add_argument(
        "prover",
        nargs="?",
        default="auto",
        help="auto|goedel|aristotle",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Lean project root (mathprover.toml)",
    )
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else None
    print(json.dumps(preview(args.node, args.prover, root)))


if __name__ == "__main__":
    main()
