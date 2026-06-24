"""Tests for ghostdq.io_pandas — file reading."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pandas as pd
import pytest
from ghostdq.io_pandas import read_csv, read_file


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


def test_read_csv(tmp_csv: Path) -> None:
    df = read_csv(tmp_csv)
    assert list(df.columns) == ["id", "value"]
    assert len(df) == 2


def test_read_file_csv(tmp_csv: Path) -> None:
    df = read_file(tmp_csv)
    assert len(df) == 2


def test_read_file_parquet(tmp_parquet: Path) -> None:
    df = read_file(tmp_parquet)
    assert len(df) == 5  # simple_df has 5 rows


def test_read_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        read_file("/no/such/file.csv")


def test_read_file_unsupported_extension(tmp_path: Path) -> None:
    p = tmp_path / "data.xlsx"
    p.write_text("x")
    with pytest.raises(ValueError, match="Unsupported file type"):
        read_file(p)
