#!/usr/bin/env python3
"""PydanticAI structured-output schemas — replace the hand-rolled JSON parsing/validation.

Agents declare these as `output_type`; PydanticAI validates (and auto-retries the model on a
validation failure), so `parse_json_action` + scattered `dict.get` defaults + try/except go away.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Leaf(BaseModel):
    name: str
    goal_spec: str = Field(description="self-contained Lean: imports + open + `lemma … := by sorry`")
    sketch: str = ""


class Plan(BaseModel):
    """PLAN-phase output: prove the node directly, or decompose into leaves + a parent proof."""
    mode: Literal["prove", "refute_then_prove"] = "prove"
    direct: bool = True
    leaves: list[Leaf] = Field(default_factory=list)
    parent_proof: str | None = None


class Sublemma(BaseModel):
    name: str
    statement: str = Field(description="`lemma <name> … := by sorry`")


class Split(BaseModel):
    sublemmas: list[Sublemma] = Field(default_factory=list)
    parent_proof: str = Field(description="`by …` closing the parent USING the sublemmas by name")


class Attempt(BaseModel):
    goal_spec: str
    sketch: str = ""


class ProposeResult(BaseModel):
    """deep-research thread / synthesis output: candidate proof attempts and/or a verified-later split."""
    attempts: list[Attempt] = Field(default_factory=list)
    split: Split | None = None


class StrategizeResult(BaseModel):
    """strategize-phase output: solve directly, or split into sub-lemmas."""
    action: Literal["solve", "split"] = "solve"
    sketch: str = ""
