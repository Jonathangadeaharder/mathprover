#!/usr/bin/env python3
"""Tests for proof-artifact soundness gates."""

from __future__ import annotations

import unittest

from lean_pipeline import forbidden_placeholders


class LeanPipelineGateTests(unittest.TestCase):
    def test_rejects_active_placeholders_and_axioms(self) -> None:
        src = """
        -- sorry in a comment is fine
        /- axiom documented_only : True -/
        axiom bad : True
        theorem t : True := by
          exact?
          admit
          sorry
        """
        self.assertEqual(["exact?", "admit", "sorry", "axiom"], forbidden_placeholders(src))

    def test_ignores_comments(self) -> None:
        src = """
        /-
        sorry
        admit
        exact?
        axiom bad : True
        -/
        theorem t : True := by
          trivial
        """
        self.assertEqual([], forbidden_placeholders(src))


if __name__ == "__main__":
    unittest.main()
