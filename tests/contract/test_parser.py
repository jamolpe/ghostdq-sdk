"""Tests for ghostdq.contract — parsing and metric_keys derivation."""

from __future__ import annotations

import pytest
from ghostdq.contract import Contract, RuleSpec, parse_contract, required_columns


def test_parse_minimal(contract_yaml_minimal: str) -> None:
    c = parse_contract(contract_yaml_minimal)
    assert isinstance(c, Contract)
    assert c.dataset == "sales"
    assert c.version == 1
    assert len(c.rules) == 1
    assert c.rules[0].rule_type == "row_count"


def test_parse_full(contract_yaml_full: str) -> None:
    c = parse_contract(contract_yaml_full)
    assert len(c.rules) == 5
    types = [r.rule_type for r in c.rules]
    assert types == ["row_count", "null_rate", "unique", "value_range", "allowed_values"]


def test_all_metric_keys(contract_yaml_full: str) -> None:
    c = parse_contract(contract_yaml_full)
    keys = c.all_metric_keys()
    assert "row_count" in keys
    assert "null_rate:country" in keys
    assert "duplicate_count:id" in keys
    assert "value_min:amount" in keys
    assert "value_max:amount" in keys
    assert "disallowed_count:country" in keys


def test_required_columns(contract_yaml_full: str) -> None:
    c = parse_contract(contract_yaml_full)
    assert c.required_columns() == ["country", "id", "amount"]


def test_required_columns_row_count_only(contract_yaml_minimal: str) -> None:
    c = parse_contract(contract_yaml_minimal)
    assert c.required_columns() == []


def test_required_columns_deduplicates() -> None:
    rules = [
        RuleSpec(rule_type="null_rate", params={"column": "country", "max": 0.1}),
        RuleSpec(rule_type="allowed_values", params={"column": "country", "values": ["ES"]}),
        RuleSpec(rule_type="unique", params={"column": "id"}),
    ]
    assert required_columns(rules) == ["country", "id"]


def test_rule_spec_metric_keys() -> None:
    r = RuleSpec(rule_type="null_rate", params={"column": "email", "max": 0.1})
    assert r.metric_keys() == ["null_rate:email"]


def test_unknown_rule_type_raises() -> None:
    yaml_text = "dataset: d\nversion: 1\nrules:\n  - badtype: {}\n"
    with pytest.raises(ValueError, match="unknown rule type"):
        parse_contract(yaml_text)


def test_missing_dataset_raises() -> None:
    with pytest.raises(ValueError, match="dataset"):
        parse_contract("version: 1\nrules: []\n")


def test_empty_rules_ok() -> None:
    c = parse_contract("dataset: d\nversion: 1\nrules: []\n")
    assert c.rules == []
    assert c.all_metric_keys() == set()
