#!/usr/bin/env python3
"""Model-free stress tests for the persistent proof DAG."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import dag as D


class DagStressTests(unittest.TestCase):
    def test_branching_root_closes_only_when_all_deps_are_proved(self) -> None:
        g = D.DAG(
            goal="root",
            nodes={
                "root": D.Node(id="root", status="open", deps=["left", "right"]),
                "left": D.Node(id="left", status="proved", axioms=D.STD_AXIOMS),
                "right": D.Node(id="right", status="open"),
            },
        )
        ok, blockers = g.axiom_rollup()
        self.assertFalse(ok)
        self.assertIn("right:open", blockers)

        g.nodes["right"].status = "proved"
        g.nodes["right"].axioms = D.STD_AXIOMS
        g.nodes["root"].status = "proved"
        g.nodes["root"].axioms = D.STD_AXIOMS
        ok, blockers = g.axiom_rollup()
        self.assertTrue(ok)
        self.assertEqual([], blockers)

    def test_refuted_false_helper_never_counts_as_proved(self) -> None:
        g = D.DAG(
            goal="root",
            nodes={
                "root": D.Node(id="root", status="open", deps=["bad_helper"]),
                "bad_helper": D.Node(id="bad_helper", status="refuted"),
            },
        )
        ok, blockers = g.axiom_rollup()
        self.assertFalse(ok)
        self.assertIn("bad_helper:refuted", blockers)
        self.assertEqual([], g.frontier())

    def test_resume_preserves_verified_nodes(self) -> None:
        g = D.DAG(
            goal="root",
            nodes={
                "root": D.Node(id="root", status="open", deps=["leaf"]),
                "leaf": D.Node(
                    id="leaf",
                    status="proved",
                    proof_path="proofs/leaf/attempt.lean",
                    axioms=D.STD_AXIOMS,
                ),
            },
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "dag.json"
            g.save(path)
            loaded = D.DAG.load(path)

        self.assertEqual("proved", loaded.nodes["leaf"].status)
        self.assertEqual("proofs/leaf/attempt.lean", loaded.nodes["leaf"].proof_path)
        self.assertEqual(D.STD_AXIOMS, loaded.nodes["leaf"].axioms)


if __name__ == "__main__":
    unittest.main()
