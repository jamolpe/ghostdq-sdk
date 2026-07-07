"""Tests for ghostdq.metrics.duckdb_engine — optional DuckDB backend."""

from __future__ import annotations

import pandas as pd
import pytest
from ghostdq.contract import parse_contract
from ghostdq.metrics import compute_metrics


def test_duckdb_matches_pandas_csv(tmp_csv, contract_yaml_full: str, simple_df: pd.DataFrame) -> None:
    duckdb = pytest.importorskip("duckdb")
    from ghostdq.metrics.duckdb_engine import DuckDBMetricsEngine

    contract = parse_contract(contract_yaml_full)
    expected = compute_metrics(simple_df, contract.rules)

    # tmp_csv only has id,value — write a richer csv
    path = tmp_csv.parent / "sales.csv"
    simple_df.to_csv(path, index=False)

    conn = duckdb.connect()
    actual = DuckDBMetricsEngine().compute_path(conn, path, contract.rules)
    assert actual == expected


def test_duckdb_parquet(tmp_parquet, contract_yaml_minimal: str) -> None:
    duckdb = pytest.importorskip("duckdb")
    from ghostdq.metrics.duckdb_engine import DuckDBMetricsEngine

    contract = parse_contract(contract_yaml_minimal)
    conn = duckdb.connect()
    metrics = DuckDBMetricsEngine().compute_path(conn, tmp_parquet, contract.rules)
    assert metrics["row_count"] == 5
