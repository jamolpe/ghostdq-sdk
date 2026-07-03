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
#   allowed_values     → "disallowed_count:{column}"
#   out_of_range_rate  → "out_of_range_rate:{column}"
#   regex_match        → "regex_match_rate:{column}"

SUPPORTED_RULES = frozenset(
    [
        "row_count",
        "null_rate",
        "unique",
        "duplicate_rate",
        "value_range",
        "allowed_values",
        "out_of_range_rate",
        "regex_match",
    ]
)


@dataclass
class SchemaField:
    """Declared column in a contract ``schema`` block.

    Attributes:
        name: Column name as it appears in the dataset.
        type: Expected logical type (``string``, ``int``, ``float``, ``bool``, ``timestamp``).
            Used for documentation today; type enforcement is planned (see internal roadmap).
    """

    name: str
    type: SchemaType


@dataclass
class RuleSpec:
    """One data-quality rule parsed from contract YAML.

    Each YAML entry is a single-key mapping, e.g. ``null_rate: {column: email, max: 0.01}``.
    The key becomes ``rule_type``; the value dict becomes ``params``.

    Attributes:
        rule_type: Rule identifier (must be in :data:`SUPPORTED_RULES`).
        params: Rule-specific parameters (``column``, thresholds, ``values``, ``pattern``, …).

    See :meth:`metric_keys` for the aggregated metrics the SDK must compute before evaluation.
    """

    rule_type: str
    params: dict[str, Any]

    def metric_keys(self) -> list[str]:
        """Return metric names this rule needs (e.g. ``null_rate:country``)."""
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
        if self.rule_type == "out_of_range_rate":
            return [f"out_of_range_rate:{col}"]
        if self.rule_type == "regex_match":
            return [f"regex_match_rate:{col}"]
        return []


@dataclass
class Contract:
    """Parsed GhostDQ dataset contract.

    A contract names a dataset, optional schema fields, and an ordered list of rules.
    The SDK uses it to know which columns to scan and which metrics to produce.

    Attributes:
        dataset: Dataset identifier (string slug or logical name).
        version: Contract version number (positive integer).
        schema_fields: Optional declared columns (not yet enforced at runtime).
        rules: Ordered list of :class:`RuleSpec` entries from the ``rules:`` block.

    Example:
        >>> contract = parse_contract(open("sales_contract.yaml").read())
        >>> contract.required_columns()
        ['country', 'order_id', 'amount']
    """

    dataset: str
    version: int
    schema_fields: list[SchemaField] = field(default_factory=list)
    rules: list[RuleSpec] = field(default_factory=list)

    def all_metric_keys(self) -> set[str]:
        """Union of every metric key required by all rules (deduplicated)."""
        keys: set[str] = set()
        for rule in self.rules:
            keys.update(rule.metric_keys())
        return keys

    def required_columns(self) -> list[str]:
        """Column names referenced by rules, in first-seen order."""
        from ghostdq.contract.parser import required_columns

        return required_columns(self.rules)
