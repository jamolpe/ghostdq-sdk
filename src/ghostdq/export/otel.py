"""Optional OpenTelemetry metrics export for GhostDQ.

Install the extra: ``pip install "ghostdq[otel]"``.

OTel packages are lazy-imported so ``import ghostdq`` stays fast without the extra.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from typing import Any, Literal

from ghostdq.evaluation.models import RuleEvaluation

InstrumentKind = Literal["gauge", "counter"]

_GAUGE_METRICS = frozenset(
    {
        "row_count",
        "null_rate",
        "duplicate_rate",
        "value_min",
        "value_max",
        "out_of_range_rate",
        "regex_match_rate",
    }
)
_COUNTER_METRICS = frozenset({"duplicate_count", "disallowed_count"})

_DEFAULT_PREFIX = "ghostdq"
_DEFAULT_SERVICE_NAME = "ghostdq-sdk"


class OtelNotInstalledError(ImportError):
    """Raised when OTel export is requested but optional deps are missing."""


def _require_otel() -> Any:
    try:
        from opentelemetry import metrics as otel_metrics
    except ImportError as exc:
        raise OtelNotInstalledError(
            'OpenTelemetry is not installed. Install with: pip install "ghostdq[otel]"'
        ) from exc
    return otel_metrics


def parse_metric_key(key: str) -> tuple[str, dict[str, str]]:
    """Parse a flat GhostDQ metric key into type and attributes.

    Examples:
        >>> parse_metric_key("row_count")
        ('row_count', {})
        >>> parse_metric_key("null_rate:email")
        ('null_rate', {'column': 'email'})
    """
    if ":" in key:
        metric_type, column = key.split(":", 1)
        return metric_type, {"column": column}
    return key, {}


def metric_instrument_kind(metric_type: str) -> InstrumentKind:
    """Return whether a metric type maps to an OTel gauge or counter."""
    if metric_type in _COUNTER_METRICS:
        return "counter"
    if metric_type in _GAUGE_METRICS:
        return "gauge"
    raise ValueError(f"unknown GhostDQ metric type {metric_type!r}")


def is_otel_enabled() -> bool:
    """Return True when GhostDQ OTel export is enabled via env var."""
    return os.environ.get("GHOSTDQ_OTEL_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def otel_metric_prefix() -> str:
    """Configured metric name prefix (default ``ghostdq``)."""
    return os.environ.get("GHOSTDQ_OTEL_METRIC_PREFIX", _DEFAULT_PREFIX).strip() or _DEFAULT_PREFIX


def _coerce_number(value: Any) -> float | int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    return None


def _merge_attributes(
    base: dict[str, str] | None,
    extra: dict[str, str] | None,
) -> dict[str, str]:
    merged: dict[str, str] = {}
    if base:
        merged.update({k: str(v) for k, v in base.items()})
    if extra:
        merged.update({k: str(v) for k, v in extra.items()})
    return merged


def _parse_resource_attributes(raw: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for part in raw.split(","):
        piece = part.strip()
        if not piece or "=" not in piece:
            continue
        key, value = piece.split("=", 1)
        attrs[key.strip()] = value.strip()
    return attrs


def configure_meter_from_env(
    *,
    service_name: str | None = None,
    metric_readers: list[Any] | None = None,
) -> Any:
    """Create a :class:`Meter` using standard ``OTEL_*`` environment variables.

    When ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set and no readers are passed, an OTLP
    HTTP exporter is attached. Otherwise callers should pass an in-memory reader
    (tests) or configure export separately.

    Returns:
        An OpenTelemetry ``Meter`` instance.
    """
    otel_metrics = _require_otel()
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.resources import Resource

    name = (
        service_name
        or os.environ.get("OTEL_SERVICE_NAME")
        or _DEFAULT_SERVICE_NAME
    )
    resource_attrs = {**_parse_resource_attributes(os.environ.get("OTEL_RESOURCE_ATTRIBUTES", ""))}
    resource = Resource.create({"service.name": name, **resource_attrs})

    readers = list(metric_readers or [])
    if not readers and os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
            OTLPMetricExporter,
        )
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

        exporter = OTLPMetricExporter()
        readers.append(PeriodicExportingMetricReader(exporter))

    provider = MeterProvider(resource=resource, metric_readers=readers)
    otel_metrics.set_meter_provider(provider)
    return provider.get_meter("ghostdq", version="0.2.0")


@dataclass
class GhostDQOtelExporter:
    """Emit GhostDQ metrics and rule evaluations to OpenTelemetry.

    Args:
        meter: OpenTelemetry meter (defaults to ``get_meter("ghostdq")``).
        prefix: Metric name prefix (e.g. ``ghostdq`` → ``ghostdq.null_rate``).
        attributes: Default attributes attached to every recorded point.
    """

    meter: Any = None
    prefix: str = _DEFAULT_PREFIX
    attributes: dict[str, str] = field(default_factory=dict)
    _gauges: dict[str, Any] = field(default_factory=dict, init=False, repr=False)
    _counters: dict[str, Any] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.meter is None:
            otel_metrics = _require_otel()
            self.meter = otel_metrics.get_meter("ghostdq", version="0.2.0")

    def export_metrics(self, metrics: dict[str, Any]) -> None:
        """Record computed GhostDQ metrics as OTel gauges and counters."""
        for key, raw_value in metrics.items():
            metric_type, key_attrs = parse_metric_key(key)
            value = _coerce_number(raw_value)
            if value is None:
                continue

            attrs = _merge_attributes(self.attributes, key_attrs)
            kind = metric_instrument_kind(metric_type)
            name = f"{self.prefix}.{metric_type}"

            if kind == "counter":
                counter = self._counters.get(name)
                if counter is None:
                    counter = self.meter.create_counter(name)
                    self._counters[name] = counter
                counter.add(value, attrs)
            else:
                gauge = self._gauges.get(name)
                if gauge is None:
                    gauge = self._create_gauge(name)
                    self._gauges[name] = gauge
                self._record_gauge(gauge, value, attrs)

    def export_evaluations(self, results: list[RuleEvaluation]) -> None:
        """Record per-rule pass/fail as ``{prefix}.rule.passed`` gauges."""
        name = f"{self.prefix}.rule.passed"
        gauge = self._gauges.get(name)
        if gauge is None:
            gauge = self._create_gauge(name)
            self._gauges[name] = gauge

        for result in results:
            attrs = _merge_attributes(
                self.attributes,
                {"rule_type": result.rule_type},
            )
            if result.column:
                attrs["column"] = result.column
            self._record_gauge(gauge, 1 if result.passed else 0, attrs)

    def flush(self, timeout_millis: int = 30_000) -> bool:
        """Force-flush the active meter provider (important for short-lived jobs)."""
        otel_metrics = _require_otel()
        provider = otel_metrics.get_meter_provider()
        if hasattr(provider, "force_flush"):
            return bool(provider.force_flush(timeout_millis=timeout_millis))
        return True

    def _create_gauge(self, name: str) -> Any:
        if hasattr(self.meter, "create_gauge"):
            return self.meter.create_gauge(name)
        return self.meter.create_histogram(name)

    def _record_gauge(self, instrument: Any, value: float | int, attributes: dict[str, str]) -> None:
        if hasattr(instrument, "set"):
            instrument.set(value, attributes)
        else:
            instrument.record(value, attributes)


def export_metrics(
    metrics: dict[str, Any],
    *,
    meter: Any | None = None,
    attributes: dict[str, str] | None = None,
    prefix: str | None = None,
    flush: bool = True,
) -> None:
    """Emit computed metrics to OpenTelemetry and optionally flush."""
    exporter = GhostDQOtelExporter(
        meter=meter,
        prefix=prefix or otel_metric_prefix(),
        attributes=attributes or {},
    )
    exporter.export_metrics(metrics)
    if flush:
        exporter.flush()


def export_evaluations(
    results: list[RuleEvaluation],
    *,
    meter: Any | None = None,
    attributes: dict[str, str] | None = None,
    prefix: str | None = None,
    flush: bool = True,
) -> None:
    """Emit rule evaluation pass/fail to OpenTelemetry and optionally flush."""
    exporter = GhostDQOtelExporter(
        meter=meter,
        prefix=prefix or otel_metric_prefix(),
        attributes=attributes or {},
    )
    exporter.export_evaluations(results)
    if flush:
        exporter.flush()


def export_run(
    metrics: dict[str, Any],
    results: list[RuleEvaluation] | None = None,
    *,
    meter: Any | None = None,
    attributes: dict[str, str] | None = None,
    prefix: str | None = None,
) -> None:
    """Emit metrics and optional evaluations in one batch with a single flush."""
    exporter = GhostDQOtelExporter(
        meter=meter,
        prefix=prefix or otel_metric_prefix(),
        attributes=attributes or {},
    )
    exporter.export_metrics(metrics)
    if results is not None:
        exporter.export_evaluations(results)
    exporter.flush()
