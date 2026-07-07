"""Tests for ghostdq.metrics.router — file backend selection."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from ghostdq.contract import parse_contract
from ghostdq.metrics import compute_metrics, compute_metrics_file


def test_auto_uses_streaming_for_csv(tmp_path: Path, contract_yaml_minimal: str) -> None:
    contract = parse_contract(contract_yaml_minimal)
    csv_path = tmp_path / "data.csv"
    pd.DataFrame({"id": [1, 2, 3]}).to_csv(csv_path, index=False)

    metrics = compute_metrics_file(csv_path, contract.rules, engine="auto")
    assert metrics["row_count"] == 3


def test_auto_uses_arrow_for_parquet(tmp_parquet: Path, contract_yaml_minimal: str) -> None:
    contract = parse_contract(contract_yaml_minimal)
    metrics = compute_metrics_file(tmp_parquet, contract.rules, engine="auto")
    assert metrics["row_count"] == 5


def test_pandas_engine_matches_dataframe(tmp_csv: Path, contract_yaml_minimal: str) -> None:
    contract = parse_contract(contract_yaml_minimal)
    df = pd.read_csv(tmp_csv)
    expected = compute_metrics(df, contract.rules)
    actual = compute_metrics_file(tmp_csv, contract.rules, engine="pandas")
    assert actual == expected
