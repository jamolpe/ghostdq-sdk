"""Fixtures for CLI tests."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

_GHOSTDQ_ENV_KEYS = ("GHOSTDQ_DATASET_ID", "GHOSTDQ_API_KEY", "GHOSTDQ_INGEST_URL")


@pytest.fixture(autouse=True)
def _clear_ghostdq_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI tests must not inherit GHOSTDQ_* vars from the developer shell."""
    for key in _GHOSTDQ_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

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
