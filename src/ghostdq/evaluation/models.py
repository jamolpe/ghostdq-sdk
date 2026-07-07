"""Evaluation result models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuleEvaluation:
    """Pass/fail result for one contract rule after local evaluation.

    Attributes:
        rule_type: Rule identifier (e.g. ``null_rate``).
        passed: Whether computed metrics satisfy the rule constraints.
        value_display: Human-readable observed value for CLI output.
        constraint_display: Human-readable expected bounds (may be empty).
        column: Affected column name, if the rule is column-scoped.
    """

    rule_type: str
    passed: bool
    value_display: str
    constraint_display: str
    column: str | None = None
