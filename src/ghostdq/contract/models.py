"""Contract domain models.

Intentionally duplicated from ghostdq_core.contract so the SDK has zero
dependency on the core package (which drags in SQLAlchemy, boto3, etc.).

Keep in sync with packages/core/src/ghostdq_core/contract.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

SchemaType = Literal["string", "int", "float", "bool", "timestamp"]

# Metric key format per rule type (must match ghostdq_core.rules):
#   row_count       → "row_count"
#   null_rate       → "null_rate:{column}"
#   unique          → "duplicate_count:{column}"
#   duplicate_rate  → "duplicate_rate:{column}"
#   value_range     → "value_min:{column}", "value_max:{column}"
#   allowed_values  → "disallowed_count:{column}"

SUPPORTED_RULES = frozenset(
    ["row_count", "null_rate", "unique", "duplicate_rate", "value_range", "allowed_values"]
)


@dataclass
class SchemaField:
    name: str
    type: SchemaType


@dataclass
class RuleSpec:
    """One rule parsed from the contract YAML.

    `rule_type` is the key (e.g. "null_rate"), `params` is its value dict.
    """

    rule_type: str
    params: dict[str, Any]

    def metric_keys(self) -> list[str]:
        """Return the metric names this rule needs the SDK to compute."""
        col = self.params.get("column", "")
        if self.rule_type == "row_count":
            return ["row_count"]
        if self.rule_type == "null_rate":
            return [f"null_rate:{col}"]
        if self.rule_type == "unique":
            return [f"duplicate_count:{col}"]
        if self.rule_type == "duplicate_rate":
            return [f"duplicate_rate:{col}"]
        if self.rule_type == "value_range":
            return [f"value_min:{col}", f"value_max:{col}"]
        if self.rule_type == "allowed_values":
            return [f"disallowed_count:{col}"]
        return []


@dataclass
class Contract:
    dataset: str
    version: int
    schema_fields: list[SchemaField] = field(default_factory=list)
    rules: list[RuleSpec] = field(default_factory=list)

    def all_metric_keys(self) -> set[str]:
        keys: set[str] = set()
        for rule in self.rules:
            keys.update(rule.metric_keys())
        return keys

    def required_columns(self) -> list[str]:
        """Column names referenced by rules, in first-seen order."""
        from ghostdq.contract.parser import required_columns

        return required_columns(self.rules)
