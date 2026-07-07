"""Per-column metric computation plans.

Translates a list of :class:`~ghostdq.contract.RuleSpec` into a deduplicated
:class:`ColumnMetricsPlan` per column — the bridge between contract rules and
all metrics backends (pandas, streaming, Arrow, Polars, DuckDB).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ghostdq.contract import RuleSpec


@dataclass
class ColumnMetricsPlan:
    """Per-column checklist of metrics to compute for a scan.

    Built by :func:`build_metric_plan` from a list of :class:`~ghostdq.contract.RuleSpec`.
    Multiple rules on the same column merge into one plan so each metric is computed once.

    Boolean flags turn on simple aggregations; optional fields carry rule parameters
    (allowed enum values, numeric bounds, regex pattern) needed during computation.

    Attributes:
        null_rate: Compute ``null_rate:{column}``.
        duplicate_count: Compute ``duplicate_count:{column}``.
        duplicate_rate: Compute ``duplicate_rate:{column}``.
        value_min: Compute ``value_min:{column}`` (dataset-level minimum).
        value_max: Compute ``value_max:{column}`` (dataset-level maximum).
        allowed_values: If set, compute ``disallowed_count:{column}`` against this list.
        out_of_range_min: Lower bound for row-level ``out_of_range_rate:{column}``.
        out_of_range_max: Upper bound for row-level ``out_of_range_rate:{column}``.
        out_of_range_rate: Compute ``out_of_range_rate:{column}``.
        regex_pattern: Compiled pattern source for ``regex_match_rate:{column}``.
        regex_match_rate: Compute ``regex_match_rate:{column}``.
    """
    null_rate: bool = False
    duplicate_count: bool = False
    duplicate_rate: bool = False
    value_min: bool = False
    value_max: bool = False
    allowed_values: list[Any] | None = None
    out_of_range_min: float | None = None
    out_of_range_max: float | None = None
    out_of_range_rate: bool = False
    regex_pattern: str | None = None
    regex_match_rate: bool = False

    @property
    def needs_duplicate_tracking(self) -> bool:
        """Whether duplicate detection needs a per-value counter (memory cost)."""
        return self.duplicate_count or self.duplicate_rate


def build_metric_plan(rules: list[RuleSpec]) -> tuple[bool, dict[str, ColumnMetricsPlan]]:
    """Derive a deduplicated computation plan from contract rules.

    Returns:
        A tuple ``(need_row_count, plans)`` where ``need_row_count`` is ``True`` if any
        rule needs ``row_count``, and ``plans`` maps each column name to a
        :class:`ColumnMetricsPlan` describing what to aggregate during the scan.
    """
    need_row_count = False
    plans: dict[str, ColumnMetricsPlan] = {}
    computed_keys: set[str] = set()

    for rule in rules:
        for key in rule.metric_keys():
            if key in computed_keys:
                continue
            computed_keys.add(key)

            if key == "row_count":
                need_row_count = True
                continue

            col = rule.params.get("column")
            if not isinstance(col, str) or not col:
                raise ValueError(f"Don't know how to compute metric {key!r}")

            plan = plans.setdefault(col, ColumnMetricsPlan())

            if key.startswith("null_rate:"):
                plan.null_rate = True
            elif key.startswith("duplicate_count:"):
                plan.duplicate_count = True
            elif key.startswith("duplicate_rate:"):
                plan.duplicate_rate = True
            elif key.startswith("value_min:"):
                plan.value_min = True
            elif key.startswith("value_max:"):
                plan.value_max = True
            elif key.startswith("disallowed_count:"):
                plan.allowed_values = rule.params.get("values", [])
            elif key.startswith("out_of_range_rate:"):
                plan.out_of_range_rate = True
                if "min" in rule.params:
                    plan.out_of_range_min = float(rule.params["min"])
                if "max" in rule.params:
                    plan.out_of_range_max = float(rule.params["max"])
            elif key.startswith("regex_match_rate:"):
                plan.regex_match_rate = True
                plan.regex_pattern = str(rule.params.get("pattern", ""))
            else:
                raise ValueError(f"Don't know how to compute metric {key!r}")

    return need_row_count, plans
