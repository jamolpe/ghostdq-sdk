"""Shared fixtures for the SDK test suite."""

from __future__ import annotations

import io
import textwrap
from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture()
def simple_df() -> pd.DataFrame:
    """A small sales DataFrame with known properties:

    - 5 rows
    - 'country' column: 3 unique values (ES, US, null)
    - 'amount' column: numeric, range [10, 200]
    - 'id' column: all unique
    """
    csv = textwrap.dedent(
        """\
        id,country,amount
        1,ES,100
        2,US,200
        3,ES,50
        4,,10
        5,MX,75
        """
    )
    return pd.read_csv(io.StringIO(csv))


@pytest.fixture()
def contract_yaml_minimal() -> str:
    return textwrap.dedent(
        """\
        dataset: sales
        version: 1
        rules:
          - row_count: {min: 1}
        """
    )


@pytest.fixture()
def contract_yaml_full() -> str:
    return textwrap.dedent(
        """\
        dataset: sales
        version: 1
        rules:
          - row_count: {min: 1, max: 1000}
          - null_rate: {column: country, max: 0.5}
          - unique: {column: id}
          - value_range: {column: amount, min: 0, max: 500}
          - allowed_values: {column: country, values: [ES, US, MX]}
        """
    )


@pytest.fixture()
def tmp_csv(tmp_path: Path) -> Path:
    p = tmp_path / "data.csv"
    p.write_text(
        textwrap.dedent(
            """\
            id,value
            1,100
            2,200
            """
        )
    )
    return p


@pytest.fixture()
def tmp_parquet(tmp_path: Path, simple_df: pd.DataFrame) -> Path:
    p = tmp_path / "data.parquet"
    simple_df.to_parquet(p, index=False, engine="pyarrow")
    return p
