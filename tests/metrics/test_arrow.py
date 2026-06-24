"""Tests for ghostdq.metrics.arrow — PyArrow-native metrics."""

from __future__ import annotations

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from ghostdq.contract import parse_contract
from ghostdq.metrics import ArrowMetricsEngine, compute_metrics
from ghostdq.metrics.arrow import compute_arrow_metrics


def test_arrow_matches_pandas_on_table(simple_df: pd.DataFrame, contract_yaml_full: str) -> None:
    contract = parse_contract(contract_yaml_full)
    table = pa.Table.from_pandas(simple_df, preserve_index=False)

    expected = compute_metrics(simple_df, contract.rules)
    actual = compute_arrow_metrics(table, contract.rules)

    assert actual == expected


def test_arrow_parquet_without_pandas(tmp_path, simple_df: pd.DataFrame, contract_yaml_full: str) -> None:
    contract = parse_contract(contract_yaml_full)
    path = tmp_path / "data.parquet"
    pq.write_table(pa.Table.from_pandas(simple_df, preserve_index=False), path)

    metrics = ArrowMetricsEngine().compute_parquet(path, contract.rules)
    assert metrics["row_count"] == 5
    assert "null_rate:country" in metrics
