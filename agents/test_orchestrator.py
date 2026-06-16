#!/usr/bin/env python3
"""Unit tests for orchestrator.py scheduling, decomposition, and state transitions."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import dag as D
import orchestrator as O
import tools as T


class OrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        # Seed a basic proof directory
        (self.root / "proofs").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    @patch("orchestrator.residency")
    @patch("orchestrator.AG")
    @patch("orchestrator.axiom_check")
    @patch("orchestrator.final_verify_attempt")
    def test_schedule_leaf_success(
        self,
        mock_final_verify: MagicMock,
        mock_axiom_check: MagicMock,
        mock_ag: MagicMock,
        mock_residency: MagicMock,
    ) -> None:
        # Mock final verify and axiom check
        mock_final_verify.return_value = (True, "gate clean")
        mock_axiom_check.return_value.combined = "depends on axioms: [propext, Classical.choice]"
        
        # Mock AG phases
        mock_ag._axiom_backed.return_value = False
        mock_ag._gather_context.return_value = None
        mock_ag.plan_phase.return_value = {
            "mode": "prove",
            "direct": True,
            "leaves": [{"name": "leaf", "goal_spec": "theorem leaf : True := by sorry"}],
        }
        mock_ag.prove_phase.return_value = ("DONE-CANDIDATE", {"leaf": "proof"}, "")
        mock_ag.assemble_and_gate.return_value = (True, "")

        # Set up a single leaf DAG
        dag = D.DAG(
            goal="leaf",
            nodes={
                "leaf": D.Node(
                    id="leaf",
                    statement="theorem leaf : True := by sorry",
                    status="open",
                    folder="proofs/leaf",
                )
            },
        )
        
        # Run orchestrator schedule
        O.schedule(self.root, dag, max_hours=1.0, max_nodes=1, allow_research=False)

        # The leaf should now be proved
        self.assertEqual("proved", dag.nodes["leaf"].status)
        self.assertEqual(["propext", "Classical.choice"], dag.nodes["leaf"].axioms)

    @patch("orchestrator.residency")
    @patch("orchestrator.AG")
    def test_schedule_false_helper_refuted(
        self,
        mock_ag: MagicMock,
        mock_residency: MagicMock,
    ) -> None:
        # Mock AG phases returning FALSE (refuted)
        mock_ag._axiom_backed.return_value = False
        mock_ag._gather_context.return_value = None
        mock_ag.plan_phase.return_value = {
            "mode": "refute_then_prove",
            "direct": True,
            "leaves": [{"name": "leaf", "goal_spec": "theorem leaf : False := by sorry"}],
        }
        mock_ag.prove_phase.return_value = ("FALSE", {}, "refuted")

        # Set up a single leaf DAG
        dag = D.DAG(
            goal="leaf",
            nodes={
                "leaf": D.Node(
                    id="leaf",
                    statement="theorem leaf : False := by sorry",
                    status="open",
                    folder="proofs/leaf",
                )
            },
        )
        
        O.schedule(self.root, dag, max_hours=1.0, max_nodes=1, allow_research=False)

        # The leaf should be refuted
        self.assertEqual("refuted", dag.nodes["leaf"].status)

    @patch("orchestrator.residency")
    @patch("orchestrator.AG")
    @patch("orchestrator.axiom_check")
    @patch("orchestrator.assemble_parent")
    @patch("orchestrator.P.verify_split")
    @patch("orchestrator.P.propose_split")
    def test_schedule_decomposition_and_parent_assembly(
        self,
        mock_propose_split: MagicMock,
        mock_verify_split: MagicMock,
        mock_assemble_parent: MagicMock,
        mock_axiom_check: MagicMock,
        mock_ag: MagicMock,
        mock_residency: MagicMock,
    ) -> None:
        # Mock propose split to return empty dict
        mock_propose_split.return_value = {}
        # Mock verify split to succeed
        mock_verify_split.return_value = True
        # Mock assembly of parent to succeed
        mock_assemble_parent.return_value = (True, "assembly clean")
        mock_axiom_check.return_value.combined = "depends on axioms: [propext]"

        # Stage 1: Leaf proving mock setup
        mock_ag._axiom_backed.return_value = False
        mock_ag._gather_context.return_value = None
        
        # First plan returns a decomposition (direct=False)
        def plan_side_effect(ctx, feedback):
            if ctx.node == "parent":
                return {
                    "mode": "prove",
                    "direct": False,
                    "leaves": [
                        {"name": "child1", "goal_spec": "theorem child1 : True := by sorry"},
                        {"name": "child2", "goal_spec": "theorem child2 : True := by sorry"}
                    ],
                    "parent_proof": "by exact child1 child2",
                }
            else:
                return {
                    "mode": "prove",
                    "direct": True,
                    "leaves": [{"name": ctx.node, "goal_spec": ctx.goal_src, "sketch": ""}],
                    "parent_proof": "",
                }
        mock_ag.plan_phase.side_effect = plan_side_effect

        def prove_side_effect(ctx, plan, deadline):
            if ctx.node == "parent":
                return "DONE-CANDIDATE", {"parent__child1": "proof1", "parent__child2": "proof2"}, ""
            else:
                return "DONE-CANDIDATE", {}, "unproved"
        mock_ag.prove_phase.side_effect = prove_side_effect

        def assemble_gate_side_effect(ctx, plan, proved):
            if ctx.node == "parent":
                return False, "stuck leaf -> decompose"
            else:
                return False, "unproved"
        mock_ag.assemble_and_gate.side_effect = assemble_gate_side_effect

        # Set up parent DAG
        dag = D.DAG(
            goal="parent",
            nodes={
                "parent": D.Node(
                    id="parent",
                    statement="theorem parent : True := by sorry",
                    status="open",
                    folder="proofs/parent",
                )
            },
        )

        # Run scheduler sweep. In the first sweep, parent should be planning (decomposed)
        # and child nodes materialized.
        O.schedule(self.root, dag, max_hours=1.0, max_nodes=3, allow_research=False)

        # Parent is now planning and waiting for kids
        self.assertEqual("planning", dag.nodes["parent"].status)
        self.assertIn("parent__child1", dag.nodes["parent"].deps)
        self.assertIn("parent__child2", dag.nodes["parent"].deps)
        self.assertIn("parent__child1", dag.nodes)
        self.assertIn("parent__child2", dag.nodes)

        # Now, child1 and child2 are "open" in the DAG.
        # Let's mock child1 and child2 to be proved.
        dag.nodes["parent__child1"].status = "proved"
        dag.nodes["parent__child1"].axioms = D.STD_AXIOMS
        dag.nodes["parent__child1"].proof_path = "proofs/parent__child1/attempt.lean"
        
        dag.nodes["parent__child2"].status = "proved"
        dag.nodes["parent__child2"].axioms = D.STD_AXIOMS
        dag.nodes["parent__child2"].proof_path = "proofs/parent__child2/attempt.lean"

        # Now run schedule again. Parent has all deps proved, so it should be assembled and proved.
        O.schedule(self.root, dag, max_hours=1.0, max_nodes=3, allow_research=False)

        self.assertEqual("proved", dag.nodes["parent"].status)
        self.assertEqual(["propext"], dag.nodes["parent"].axioms)

    def test_resume_scenario_ignores_proved_nodes(self) -> None:
        # Pre-seed a proved leaf node
        dag = D.DAG(
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
        
        # Save dag
        dpath = O._dag_path(self.root)
        dag.save(dpath)

        # Load dag and check status
        loaded = D.DAG.load(dpath)
        self.assertEqual("proved", loaded.nodes["leaf"].status)
        self.assertEqual("open", loaded.nodes["root"].status)
        self.assertEqual(["root"], loaded.frontier())


if __name__ == "__main__":
    unittest.main()
