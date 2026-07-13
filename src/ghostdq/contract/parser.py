"""YAML contract parsing."""

from __future__ import annotations

import yaml

from typing import Any

from ghostdq.contract.models import Contract, RuleSpec, SchemaField, SUPPORTED_RULES

# Table-level rules that need every declared schema column (no per-rule `column` param).
_TABLE_SCHEMA_RULES = frozenset({"columns_match", "column_types"})


class ContractParser:
    """Parse GhostDQ contract YAML into :class:`Contract` objects.

    Validates structure, known rule types, and required top-level fields.
    Does not evaluate rules — only builds the in-memory representation used
    by metrics engines and :class:`~ghostdq.evaluation.RuleEvaluator`.
    """

    def parse(self, yaml_text: str) -> Contract:
        """Parse a YAML contract.

        Raises:
            ValueError: on malformed input.
        """
        raw = yaml.safe_load(yaml_text)
        if not isinstance(raw, dict):
            raise ValueError("contract must be a YAML mapping")

        dataset = raw.get("dataset")
        if not dataset or not isinstance(dataset, str):
            raise ValueError("contract must have a `dataset` string field")

        version = raw.get("version", 1)
        if not isinstance(version, int) or version < 1:
            raise ValueError("`version` must be a positive integer")

        schema_fields: list[SchemaField] = []
        for sf in raw.get("schema", []):
            schema_fields.append(SchemaField(name=sf["name"], type=sf["type"]))

        rules: list[RuleSpec] = []
        for i, entry in enumerate(raw.get("rules", [])):
            if not isinstance(entry, dict) or len(entry) != 1:
                raise ValueError(
                    f"rule #{i}: must be a single-key mapping like `row_count: {{...}}`"
                )
            (rule_type, params), = entry.items()
            if rule_type not in SUPPORTED_RULES:
                raise ValueError(
                    f"rule #{i}: unknown rule type {rule_type!r}. "
                    f"Supported: {sorted(SUPPORTED_RULES)}"
                )
            rules.append(RuleSpec(rule_type=rule_type, params=params or {}))

        return Contract(
            dataset=dataset,
            version=version,
            schema_fields=schema_fields,
            rules=rules,
        )


def parse_contract(yaml_text: str) -> Contract:
    """Parse a YAML contract into a :class:`Contract`."""
    return ContractParser().parse(yaml_text)


def _columns_from_rule_params(params: dict[str, Any]) -> list[str]:
    """Extract column names referenced directly in rule params."""
    cols: list[str] = []

    col = params.get("column")
    if isinstance(col, str) and col:
        cols.append(col)

    for key in ("left", "right"):
        val = params.get(key)
        if isinstance(val, str) and val:
            cols.append(val)

    multi = params.get("columns")
    if isinstance(multi, list):
        for item in multi:
            if isinstance(item, str) and item:
                cols.append(item)

    return cols


def required_columns(
    rules: list[RuleSpec],
    *,
    schema_fields: list[SchemaField] | None = None,
) -> list[str]:
    """Return column names needed to compute metrics for the given rules.

    Reads ``column``, ``columns``, ``left``, and ``right`` from rule params.
    Table-level schema rules (:data:`_TABLE_SCHEMA_RULES`) union every name from
    ``schema_fields`` when provided.

    ``row_count`` does not reference a column. Duplicate names are omitted while
    preserving first-seen order.
    """
    seen: set[str] = set()
    cols: list[str] = []

    def add(name: str) -> None:
        if name and name not in seen:
            seen.add(name)
            cols.append(name)

    for rule in rules:
        for col in _columns_from_rule_params(rule.params):
            add(col)
        if rule.rule_type in _TABLE_SCHEMA_RULES and schema_fields:
            for field in schema_fields:
                add(field.name)

    return cols
