"""Shared row-level checks for metric computation.

These helpers keep semantics consistent across pandas, streaming, Arrow,
Polars, and DuckDB backends (null handling, numeric coercion, regex fullmatch).
"""

from __future__ import annotations

import math
import re
from typing import Any


def is_null(value: Any) -> bool:
    """Return ``True`` for ``None``, empty strings, and float NaN."""
    if value is None:
        return True
    if isinstance(value, str) and value == "":
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return False


def to_float(value: Any) -> float | None:
    """Coerce a cell value to float; return ``None`` for nulls and NaN on failure."""
    if is_null(value):
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except ValueError:
        return float("nan")


def is_out_of_range(
    value: Any,
    *,
    min_val: float | None,
    max_val: float | None,
) -> bool:
    """Return ``True`` if *value* is null, non-numeric, or outside ``[min_val, max_val]``.

    Bounds are inclusive on the valid side: values equal to ``min_val`` or ``max_val``
    are considered in range. Omitted bounds (``None``) are not checked.
    """
    if is_null(value):
        return True
    numeric = to_float(value)
    if numeric is None or math.isnan(numeric):
        return True
    if min_val is not None and numeric < min_val:
        return True
    if max_val is not None and numeric > max_val:
        return True
    return False


def regex_matches(value: Any, pattern: re.Pattern[str]) -> bool:
    """Return ``True`` if *value* fully matches *pattern* (``Pattern.fullmatch``).

    Null and empty values never match.
    """
    if is_null(value):
        return False
    return pattern.fullmatch(str(value)) is not None
