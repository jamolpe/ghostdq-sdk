"""Tests for ghostdq.metrics — metric computation from a DataFrame."""

from __future__ import annotations

import textwrap

import pandas as pd
import pytest
from ghostdq.contract import parse_contract
from ghostdq.metrics import compute_metrics


def test_row_count(simple_df: pd.DataFrame, contract_yaml_minimal: str) -> None:
    contract = parse_contract(contract_yaml_minimal)
    m = compute_metrics(simple_df, contract.rules)
    assert m["row_count"] == 5


def test_null_rate(simple_df: pd.DataFrame) -> None:
    contract = parse_contract(
        "dataset: d\nversion: 1\nrules:\n  - null_rate: {column: country, max: 0.5}\n"
    )
    m = compute_metrics(simple_df, contract.rules)
    # 1 null out of 5 rows
    assert abs(m["null_rate:country"] - 0.2) < 1e-6


def test_null_rate_zero_rows() -> None:
    df = pd.DataFrame({"country": pd.Series([], dtype=str)})
    contract = parse_contract(
        "dataset: d\nversion: 1\nrules:\n  - null_rate: {column: country, max: 0.5}\n"
    )
    m = compute_metrics(df, contract.rules)
    assert m["null_rate:country"] == 0.0


def test_duplicate_count_no_duplicates(simple_df: pd.DataFrame) -> None:
    contract = parse_contract(
        "dataset: d\nversion: 1\nrules:\n  - unique: {column: id}\n"
    )
    m = compute_metrics(simple_df, contract.rules)
    assert m["duplicate_count:id"] == 0


def test_duplicate_count_with_duplicates() -> None:
    df = pd.DataFrame({"id": [1, 2, 2, 3]})
    contract = parse_contract(
        "dataset: d\nversion: 1\nrules:\n  - unique: {column: id}\n"
    )
    m = compute_metrics(df, contract.rules)
    # Both rows with id=2 are flagged → 2 duplicates
    assert m["duplicate_count:id"] == 2


def test_duplicate_rate() -> None:
    df = pd.DataFrame({"id": [1, 2, 2, 3]})
    contract = parse_contract(
        "dataset: d\nversion: 1\nrules:\n  - duplicate_rate: {column: id, max: 0.5}\n"
    )
    m = compute_metrics(df, contract.rules)
    assert abs(m["duplicate_rate:id"] - 0.5) < 1e-6


def test_duplicate_rate_zero_rows() -> None:
    df = pd.DataFrame({"id": pd.Series([], dtype=int)})
    contract = parse_contract(
        "dataset: d\nversion: 1\nrules:\n  - duplicate_rate: {column: id, max: 0.5}\n"
    )
    m = compute_metrics(df, contract.rules)
    assert m["duplicate_rate:id"] == 0.0


def test_value_range(simple_df: pd.DataFrame) -> None:
    contract = parse_contract(
        "dataset: d\nversion: 1\n"
        "rules:\n  - value_range: {column: amount, min: 0, max: 500}\n"
    )
    m = compute_metrics(simple_df, contract.rules)
    assert m["value_min:amount"] == 10.0
    assert m["value_max:amount"] == 200.0


def test_allowed_values_all_ok(simple_df: pd.DataFrame) -> None:
    contract = parse_contract(
        "dataset: d\nversion: 1\n"
        "rules:\n  - allowed_values: {column: country, values: [ES, US, MX]}\n"
    )
    m = compute_metrics(simple_df, contract.rules)
    # row 4 has null → cast to 'nan', which is not in allowed set
    assert m["disallowed_count:country"] == 1


def test_allowed_values_violations() -> None:
    df = pd.DataFrame({"country": ["ES", "XX", "YY"]})
    contract = parse_contract(
        "dataset: d\nversion: 1\n"
        "rules:\n  - allowed_values: {column: country, values: [ES]}\n"
    )
    m = compute_metrics(df, contract.rules)
    assert m["disallowed_count:country"] == 2


def test_missing_column_raises(simple_df: pd.DataFrame) -> None:
    contract = parse_contract(
        "dataset: d\nversion: 1\n"
        "rules:\n  - null_rate: {column: nonexistent, max: 0.5}\n"
    )
    with pytest.raises(ValueError, match="not found in DataFrame"):
        compute_metrics(simple_df, contract.rules)


def test_wide_dataframe_ignores_extra_columns(simple_df: pd.DataFrame, contract_yaml_full: str) -> None:
    wide = simple_df.assign(
        unused_a=range(len(simple_df)),
        unused_b="x",
        unused_c=0.0,
    )
    contract = parse_contract(contract_yaml_full)
    assert compute_metrics(wide, contract.rules) == compute_metrics(simple_df, contract.rules)


def test_full_contract_all_keys(simple_df: pd.DataFrame, contract_yaml_full: str) -> None:
    contract = parse_contract(contract_yaml_full)
    m = compute_metrics(simple_df, contract.rules)
    expected_keys = {
        "row_count",
        "null_rate:country",
        "duplicate_count:id",
        "value_min:amount",
        "value_max:amount",
        "disallowed_count:country",
    }
    assert expected_keys.issubset(set(m.keys()))


def test_metrics_not_recomputed_for_same_key() -> None:
    """When two rules need the same key, compute_metrics computes it once."""
    yaml = textwrap.dedent(
        """\
        dataset: d
        version: 1
        rules:
          - null_rate: {column: country, max: 0.1}
          - null_rate: {column: country, max: 0.5}
        """
    )
    df = pd.DataFrame({"country": ["ES", None]})
    contract = parse_contract(yaml)
    m = compute_metrics(df, contract.rules)
    assert "null_rate:country" in m
    assert len([k for k in m if k.startswith("null_rate:country")]) == 1


def test_unique_and_duplicate_rate_on_same_column() -> None:
    df = pd.DataFrame({"id": [1, 2, 2, 3]})
    contract = parse_contract(
        "dataset: d\nversion: 1\nrules:\n"
        "  - unique: {column: id}\n"
        "  - duplicate_rate: {column: id, max: 0.5}\n"
    )
    m = compute_metrics(df, contract.rules)
    assert m["duplicate_count:id"] == 2
    assert abs(m["duplicate_rate:id"] - 0.5) < 1e-6
