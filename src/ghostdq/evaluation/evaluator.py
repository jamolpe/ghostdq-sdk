"""Evaluate computed metrics against contract rules (local, no network).

Logic mirrors ghostdq_core.rules — keep in sync when rule types change.
"""

from __future__ import annotations

import math
from typing import Any

from ghostdq.contract import RuleSpec
from ghostdq.evaluation.models import RuleEvaluation


class RuleEvaluator:
    """Check computed metrics against contract rules."""

    def evaluate(
        self,
        rules: list[RuleSpec],
        metrics: dict[str, Any],
    ) -> list[RuleEvaluation]:
        """Return one evaluation per rule, in contract order."""
        return [self._evaluate_one(rule, metrics) for rule in rules]

    def format_line(self, result: RuleEvaluation) -> str:
        """Format one rule result for terminal output."""
        mark = "✓" if result.passed else "✗"
        name = result.rule_type.ljust(14)
        value = result.value_display.ljust(14)
        constraint = f"  {result.constraint_display}" if result.constraint_display else ""
        column = f"  (column: {result.column})" if result.column else ""
        return f"{mark} {name} {value}{constraint}{column}"

    def _evaluate_one(self, rule: RuleSpec, metrics: dict[str, Any]) -> RuleEvaluation:
        col = rule.params.get("column")
        column = str(col) if col else None

        if rule.rule_type == "row_count":
            value = metrics["row_count"]
            passed = True
            parts: list[str] = []
            if "min" in rule.params:
                passed = value >= rule.params["min"]
                parts.append(f"min={rule.params['min']}")
            if "max" in rule.params:
                passed = passed and value <= rule.params["max"]
                parts.append(f"max={rule.params['max']}")
            return RuleEvaluation(
                rule_type="row_count",
                passed=passed,
                value_display=_format_scalar(value),
                constraint_display="  ".join(parts),
            )

        if rule.rule_type == "null_rate":
            value = metrics[f"null_rate:{col}"]
            limit = rule.params["max"]
            return RuleEvaluation(
                rule_type="null_rate",
                passed=value <= limit,
                value_display=_format_scalar(value),
                constraint_display=f"max={limit}",
                column=column,
            )

        if rule.rule_type == "unique":
            dupes = metrics[f"duplicate_count:{col}"]
            passed = dupes == 0
            return RuleEvaluation(
                rule_type="unique",
                passed=passed,
                value_display="ok" if passed else f"{_format_scalar(dupes)} duplicates",
                constraint_display="",
                column=column,
            )

        if rule.rule_type == "duplicate_rate":
            value = metrics[f"duplicate_rate:{col}"]
            limit = rule.params["max"]
            return RuleEvaluation(
                rule_type="duplicate_rate",
                passed=value <= limit,
                value_display=_format_scalar(value),
                constraint_display=f"max={limit}",
                column=column,
            )

        if rule.rule_type == "value_range":
            vmin = metrics[f"value_min:{col}"]
            vmax = metrics[f"value_max:{col}"]
            passed = True
            parts = []
            if "min" in rule.params:
                passed = not math.isnan(vmin) and vmin >= rule.params["min"]
                parts.append(f"min={rule.params['min']}")
            if "max" in rule.params:
                passed = passed and not math.isnan(vmax) and vmax <= rule.params["max"]
                parts.append(f"max={rule.params['max']}")
            return RuleEvaluation(
                rule_type="value_range",
                passed=passed,
                value_display=f"{_format_scalar(vmin)}…{_format_scalar(vmax)}",
                constraint_display="  ".join(parts),
                column=column,
            )

        if rule.rule_type == "allowed_values":
            bad = metrics[f"disallowed_count:{col}"]
            passed = bad == 0
            return RuleEvaluation(
                rule_type="allowed_values",
                passed=passed,
                value_display="ok" if passed else f"{_format_scalar(bad)} disallowed",
                constraint_display="",
                column=column,
            )

        raise ValueError(f"unknown rule type {rule.rule_type!r}")


def _format_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int):
        return f"{value:,}".replace(",", " ")
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        if value == int(value) and abs(value) < 1e15:
            return f"{int(value):,}".replace(",", " ")
        text = f"{value:.6f}".rstrip("0").rstrip(".")
        return text
    return str(value)


_default_evaluator = RuleEvaluator()


def evaluate_rules(rules: list[RuleSpec], metrics: dict[str, Any]) -> list[RuleEvaluation]:
    """Evaluate rules using the default :class:`RuleEvaluator`."""
    return _default_evaluator.evaluate(rules, metrics)


def format_evaluation_line(result: RuleEvaluation) -> str:
    """Format one rule result for terminal output."""
    return _default_evaluator.format_line(result)
