"""Tests for ghostdq.metrics.polars_engine — optional Polars backend."""

from __future__ import annotations

import pandas as pd
import pytest
from ghostdq.contract import parse_contract
from ghostdq.metrics import compute_metrics


def test_polars_matches_pandas(simple_df: pd.DataFrame, contract_yaml_full: str) -> None:
    pl = pytest.importorskip("polars")
    from ghostdq.metrics.polars_engine import PolarsMetricsEngine

    contract = parse_contract(contract_yaml_full)
    expected = compute_metrics(simple_df, contract.rules)
    actual = PolarsMetricsEngine().compute(pl.from_pandas(simple_df), contract.rules)
    assert actual == expected


def test_polars_scan_parquet(tmp_parquet, contract_yaml_minimal: str) -> None:
    pytest.importorskip("polars")
    from ghostdq.metrics.polars_engine import PolarsMetricsEngine

    contract = parse_contract(contract_yaml_minimal)
    metrics = PolarsMetricsEngine().compute_parquet(tmp_parquet, contract.rules)
    assert metrics["row_count"] == 5
