"""Tests for ghostdq.reading — file reading."""

from __future__ import annotations

from pathlib import Path

import pytest
from ghostdq.reading import read_avro, read_csv, read_file, read_parquet


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


def test_read_csv_with_columns(tmp_csv: Path) -> None:
    df = read_csv(tmp_csv, columns=["id"])
    assert list(df.columns) == ["id"]
    assert list(df["id"]) == [1, 2]


def test_read_parquet_with_columns(tmp_parquet: Path) -> None:
    df = read_parquet(tmp_parquet, columns=["country", "amount"])
    assert list(df.columns) == ["country", "amount"]
    assert len(df) == 5


def test_read_file_with_columns(tmp_parquet: Path) -> None:
    df = read_file(tmp_parquet, columns=["id"])
    assert list(df.columns) == ["id"]
    assert len(df) == 5


def test_read_avro(tmp_path: Path) -> None:
    fastavro = pytest.importorskip("fastavro")

    path = tmp_path / "data.avro"
    schema = {
        "type": "record",
        "name": "Row",
        "fields": [
            {"name": "id", "type": "int"},
            {"name": "value", "type": "string"},
        ],
    }
    records = [{"id": 1, "value": "a"}, {"id": 2, "value": "b"}]
    with open(path, "wb") as f:
        fastavro.writer(f, schema, records)

    df = read_avro(path)
    assert list(df.columns) == ["id", "value"]
    assert len(df) == 2

    subset = read_avro(path, columns=["id"])
    assert list(subset.columns) == ["id"]
    assert list(subset["id"]) == [1, 2]
