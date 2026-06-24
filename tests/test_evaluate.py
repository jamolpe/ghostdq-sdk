"""Tests for ghostdq.evaluate — local rule evaluation."""

from __future__ import annotations

from ghostdq.contract import parse_contract
from ghostdq.evaluate import evaluate_rules, format_evaluation_line
from ghostdq.metrics import compute_metrics


def _eval(yaml_text: str, df) -> list:
    contract = parse_contract(yaml_text)
    metrics = compute_metrics(df, contract.rules)
    return evaluate_rules(contract.rules, metrics)


def test_row_count_pass(simple_df) -> None:
    results = _eval(
        "dataset: d\nversion: 1\nrules:\n  - row_count: {min: 1, max: 10}\n",
        simple_df,
    )
    assert results[0].passed is True
    assert results[0].value_display == "5"
    assert "min=1" in results[0].constraint_display


def test_row_count_fail() -> None:
    import pandas as pd

    df = pd.DataFrame({"id": [1]})
    results = _eval(
        "dataset: d\nversion: 1\nrules:\n  - row_count: {min: 100}\n",
        df,
    )
    assert results[0].passed is False


def test_null_rate_pass(simple_df) -> None:
    results = _eval(
        "dataset: d\nversion: 1\nrules:\n  - null_rate: {column: country, max: 0.5}\n",
        simple_df,
    )
    assert results[0].passed is True
    assert results[0].column == "country"


def test_unique_fail() -> None:
    import pandas as pd

    df = pd.DataFrame({"order_id": [1, 1, 2]})
    results = _eval(
        "dataset: d\nversion: 1\nrules:\n  - unique: {column: order_id}\n",
        df,
    )
    assert results[0].passed is False
    assert "duplicates" in results[0].value_display


def test_format_line() -> None:
    from ghostdq.evaluate import RuleEvaluation

    line = format_evaluation_line(
        RuleEvaluation(
            rule_type="null_rate",
            passed=True,
            value_display="0.003",
            constraint_display="max=0.05",
            column="amount",
        )
    )
    assert line.startswith("✓ null_rate")
    assert "max=0.05" in line
    assert "(column: amount)" in line


def test_full_contract(contract_yaml_full, simple_df) -> None:
    contract = parse_contract(contract_yaml_full)
    metrics = compute_metrics(simple_df, contract.rules)
    results = evaluate_rules(contract.rules, metrics)
    assert len(results) == 5
    assert results[0].rule_type == "row_count" and results[0].passed
    assert results[1].rule_type == "null_rate" and results[1].passed
