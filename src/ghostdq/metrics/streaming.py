"""Chunked CSV metric computation for large files."""

from __future__ import annotations

import csv
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ghostdq.contract import RuleSpec, required_columns
from ghostdq.metrics.accumulators import StreamingState
from ghostdq.metrics.plans import build_metric_plan
from ghostdq.reading.types import PathLike


class StreamingCsvMetricsEngine:
    """Compute metrics by scanning a CSV file in chunks (constant memory).

    Uses :class:`~ghostdq.metrics.accumulators.StreamingState` instead of loading
    the full file into pandas. Supports the same metric keys as
    :class:`MetricsEngine` but only for ``.csv`` files.

    Prefer this backend for large CSV files; use :class:`~ghostdq.metrics.ArrowMetricsEngine`
    for Parquet.
    """

    def compute(
        self,
        path: PathLike,
        rules: list[RuleSpec],
        *,
        columns: Sequence[str] | None = None,
        chunksize: int = 100_000,
    ) -> dict[str, Any]:
        """Scan *path* and return aggregated metrics for *rules*.

        Args:
            path: Path to a UTF-8 CSV file with a header row.
            rules: Contract rules defining which metrics to compute.
            columns: Subset of columns to read; defaults to
                :func:`~ghostdq.contract.required_columns`.
            chunksize: Number of rows per in-memory batch.

        Raises:
            FileNotFoundError: If *path* does not exist.
            ValueError: If the file is not ``.csv`` or a required column is missing.
        """
        if chunksize < 1:
            raise ValueError("chunksize must be at least 1")

        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")
        if p.suffix.lower() != ".csv":
            raise ValueError("streaming metrics only support .csv files")

        needed = list(columns) if columns is not None else required_columns(rules)
        need_row_count, plans = build_metric_plan(rules)
        state = StreamingState()

        with p.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                return state.finalize(need_row_count, plans)

            if needed:
                missing = [col for col in needed if col not in reader.fieldnames]
                if missing:
                    raise ValueError(
                        f"Column {missing[0]!r} not found in file. "
                        f"Available columns: {list(reader.fieldnames)}"
                    )

            chunk: list[dict[str, Any]] = []
            for row in reader:
                if needed:
                    chunk.append({col: row.get(col) for col in needed})
                else:
                    chunk.append(dict(row))

                if len(chunk) >= chunksize:
                    state.observe_chunk(chunk, plans)
                    chunk = []

            if chunk:
                state.observe_chunk(chunk, plans)

        return state.finalize(need_row_count, plans)


_default_streaming_engine = StreamingCsvMetricsEngine()


def compute_csv_streaming(
    path: PathLike,
    rules: list[RuleSpec],
    *,
    columns: Sequence[str] | None = None,
    chunksize: int = 100_000,
) -> dict[str, Any]:
    """Compute metrics from a CSV file without loading it fully into memory."""
    return _default_streaming_engine.compute(
        path,
        rules,
        columns=columns,
        chunksize=chunksize,
    )
