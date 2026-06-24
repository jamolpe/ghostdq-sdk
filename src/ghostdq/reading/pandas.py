"""Pandas-based readers for CSV, Parquet, and Avro files."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from ghostdq.reading.types import PathLike


class PandasFileReader:
    """Read tabular files into a pandas DataFrame.

    The SDK never writes data back; this class is strictly read-only.
    Optional ``columns`` limits which fields are loaded at the format level.
    """

    def read(
        self,
        path: PathLike,
        columns: Sequence[str] | None = None,
    ) -> pd.DataFrame:
        """Dispatch to the correct reader based on file extension."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")

        suffix = p.suffix.lower()
        if suffix == ".csv":
            return self.read_csv(p, columns=columns)
        if suffix == ".parquet":
            return self.read_parquet(p, columns=columns)
        if suffix == ".avro":
            return self.read_avro(p, columns=columns)

        raise ValueError(
            f"Unsupported file type: {suffix!r}. "
            "GhostDQ SDK supports .csv, .parquet, and .avro"
        )

    def read_csv(
        self,
        path: PathLike,
        columns: Sequence[str] | None = None,
    ) -> pd.DataFrame:
        """Read a CSV file into a DataFrame."""
        kwargs: dict[str, object] = {}
        if columns is not None:
            kwargs["usecols"] = list(columns)
        return pd.read_csv(path, **kwargs)

    def read_parquet(
        self,
        path: PathLike,
        columns: Sequence[str] | None = None,
    ) -> pd.DataFrame:
        """Read a Parquet file via pyarrow."""
        kwargs: dict[str, object] = {"engine": "pyarrow"}
        if columns is not None:
            kwargs["columns"] = list(columns)
        return pd.read_parquet(path, **kwargs)

    def read_avro(
        self,
        path: PathLike,
        columns: Sequence[str] | None = None,
    ) -> pd.DataFrame:
        """Read an Avro file via fastavro."""
        import fastavro

        with open(path, "rb") as f:
            df = pd.DataFrame(fastavro.reader(f))

        if columns is None:
            return df

        return self._select_columns(df, list(columns))

    @staticmethod
    def _select_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
        missing = [col for col in columns if col not in df.columns]
        if missing:
            raise ValueError(
                f"Column {missing[0]!r} not found in file. "
                f"Available columns: {list(df.columns)}"
            )
        return df[columns]


_default_reader = PandasFileReader()

read_file = _default_reader.read
read_csv = _default_reader.read_csv
read_parquet = _default_reader.read_parquet
read_avro = _default_reader.read_avro
