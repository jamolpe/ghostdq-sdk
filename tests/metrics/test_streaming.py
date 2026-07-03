"""Tests for ghostdq.metrics.streaming — chunked CSV metrics."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pandas as pd
from ghostdq.contract import parse_contract
from ghostdq.metrics import compute_csv_streaming, compute_metrics


def _write_csv(path: Path, rows: int) -> None:
    lines = ["id,country,amount"]
    for i in range(rows):
        country = "ES" if i % 5 else ""
        lines.append(f"{i},{country},{i * 10}")
    path.write_text("\n".join(lines) + "\n")


def test_streaming_matches_pandas(tmp_path: Path) -> None:
    csv_path = tmp_path / "large.csv"
    _write_csv(csv_path, rows=250)

    contract = parse_contract(
        textwrap.dedent(
            """\
            dataset: d
            version: 1
            rules:
              - row_count: {min: 1}
              - null_rate: {column: country, max: 0.5}
              - unique: {column: id}
              - value_range: {column: amount, min: 0, max: 5000}
            """
        )
    )

    df = pd.read_csv(csv_path)
    expected = compute_metrics(df, contract.rules)
    actual = compute_csv_streaming(csv_path, contract.rules, chunksize=50)

    assert actual == expected


def test_streaming_duplicate_counts(tmp_path: Path) -> None:
    csv_path = tmp_path / "dupes.csv"
    csv_path.write_text("id\n1\n2\n2\n3\n")

    contract = parse_contract(
        "dataset: d\nversion: 1\nrules:\n  - duplicate_rate: {column: id, max: 0.5}\n"
    )
    metrics = compute_csv_streaming(csv_path, contract.rules, chunksize=2)
    assert abs(metrics["duplicate_rate:id"] - 0.5) < 1e-6


def test_streaming_out_of_range_and_regex(tmp_path: Path) -> None:
    csv_path = tmp_path / "checks.csv"
    csv_path.write_text("amount,code\n10,AB\n200,XY\n,bad\n")

    contract = parse_contract(
        textwrap.dedent(
            """\
            dataset: d
            version: 1
            rules:
              - out_of_range_rate: {column: amount, min: 0, max: 100, max_rate: 0.5}
              - regex_match: {column: code, pattern: '^[A-Z]{2}$', min_rate: 0.5}
            """
        )
    )

    df = pd.read_csv(csv_path)
    expected = compute_metrics(df, contract.rules)
    actual = compute_csv_streaming(csv_path, contract.rules, chunksize=1)
    assert actual == expected
