"""Fixtures for CLI tests."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

CONTRACT_YAML = textwrap.dedent(
    """\
    dataset: sales
    version: 1
    rules:
      - row_count: {min: 1}
    """
)

CSV_CONTENT = textwrap.dedent(
    """\
    id,country,amount
    1,ES,100
    2,US,200
    """
)


@pytest.fixture()
def contract_file(tmp_path: Path) -> Path:
    p = tmp_path / "contract.yaml"
    p.write_text(CONTRACT_YAML)
    return p


@pytest.fixture()
def data_file(tmp_path: Path) -> Path:
    p = tmp_path / "data.csv"
    p.write_text(CSV_CONTENT)
    return p
