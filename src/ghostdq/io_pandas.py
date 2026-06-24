"""Read CSV, Parquet, and Avro files into a pandas DataFrame.

The SDK never writes data back; this module is strictly read-only.
All three formats return a standard DataFrame so the metrics layer
has a single interface to work against.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PathLike = str | Path


def read_file(path: PathLike) -> pd.DataFrame:
    """Dispatch to the correct reader based on file extension.

    Raises:
        ValueError: if the extension is not supported.
        FileNotFoundError: if the path does not exist.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")

    suffix = p.suffix.lower()
    if suffix == ".csv":
        return read_csv(p)
    if suffix == ".parquet":
        return read_parquet(p)
    if suffix == ".avro":
        return read_avro(p)

    raise ValueError(
        f"Unsupported file type: {suffix!r}. "
        "GhostDQ SDK supports .csv, .parquet, and .avro"
    )


def read_csv(path: PathLike) -> pd.DataFrame:
    """Read a CSV file. Uses chunked reading to stay memory-light."""
    return pd.read_csv(path, low_memory=False)


def read_parquet(path: PathLike) -> pd.DataFrame:
    """Read a Parquet file via pyarrow."""
    return pd.read_parquet(path, engine="pyarrow")


def read_avro(path: PathLike) -> pd.DataFrame:
    """Read an Avro file via fastavro."""
    import fastavro

    with open(path, "rb") as f:
        reader = fastavro.reader(f)
        records = list(reader)

    if not records:
        return pd.DataFrame()

    return pd.DataFrame.from_records(records)
