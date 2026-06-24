"""Evaluation result models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuleEvaluation:
    rule_type: str
    passed: bool
    value_display: str
    constraint_display: str
    column: str | None = None
