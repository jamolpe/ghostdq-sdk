"""Shared fixtures for the SDK test suite."""

from __future__ import annotations

import io
import textwrap

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
