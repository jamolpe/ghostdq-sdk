"""Per-column metric computation plans."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ghostdq.contract import RuleSpec


@dataclass
class ColumnMetricsPlan:
    null_rate: bool = False
    duplicate_count: bool = False
    duplicate_rate: bool = False
    value_min: bool = False
    value_max: bool = False
    allowed_values: list[Any] | None = None

    @property
    def needs_duplicate_tracking(self) -> bool:
        return self.duplicate_count or self.duplicate_rate


def build_metric_plan(rules: list[RuleSpec]) -> tuple[bool, dict[str, ColumnMetricsPlan]]:
    """Map each column to the metrics that must be computed for it."""
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
            else:
                raise ValueError(f"Don't know how to compute metric {key!r}")

    return need_row_count, plans
