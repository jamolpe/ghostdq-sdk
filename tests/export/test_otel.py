"""Tests for ghostdq.export.otel — OpenTelemetry metrics export."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from ghostdq.evaluation.models import RuleEvaluation
from ghostdq.export.otel import (
    GhostDQOtelExporter,
    OtelNotInstalledError,
    configure_meter_from_env,
    export_evaluations,
    export_metrics,
    export_run,
    is_otel_enabled,
    metric_instrument_kind,
    otel_metric_prefix,
    parse_metric_key,
)

pytest.importorskip("opentelemetry")


def _make_reader_and_meter() -> tuple[Any, Any]:
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import InMemoryMetricReader
    from opentelemetry.sdk.resources import Resource

    reader = InMemoryMetricReader()
    provider = MeterProvider(
        resource=Resource.create({"service.name": "ghostdq-test"}),
        metric_readers=[reader],
    )
    meter = provider.get_meter("ghostdq", version="0.2.0")
    return reader, meter


def _collect_points(reader: Any) -> list[dict[str, Any]]:
    data = reader.get_metrics_data()
    points: list[dict[str, Any]] = []
    if data is None:
        return points

    for resource_metrics in data.resource_metrics:
        for scope_metrics in resource_metrics.scope_metrics:
            for metric in scope_metrics.metrics:
                for data_point in metric.data.data_points:
                    value = getattr(data_point, "value", None)
                    if value is None:
                        value = getattr(data_point, "sum", None)
                    points.append(
                        {
                            "name": metric.name,
                            "value": value,
                            "attributes": dict(data_point.attributes),
                        }
                    )
    return points


def test_parse_metric_key() -> None:
    assert parse_metric_key("row_count") == ("row_count", {})
    assert parse_metric_key("null_rate:email") == ("null_rate", {"column": "email"})


def test_metric_instrument_kind() -> None:
    assert metric_instrument_kind("row_count") == "gauge"
    assert metric_instrument_kind("null_rate") == "gauge"
    assert metric_instrument_kind("duplicate_count") == "counter"
    assert metric_instrument_kind("disallowed_count") == "counter"

    with pytest.raises(ValueError, match="unknown"):
        metric_instrument_kind("not_a_metric")


def test_export_metrics_records_gauges_and_counters() -> None:
    reader, meter = _make_reader_and_meter()

    export_metrics(
        {
            "row_count": 42,
            "null_rate:email": 0.05,
            "duplicate_count:id": 3,
            "value_min:amount": 10.0,
            "value_max:amount": 200.0,
        },
        meter=meter,
        attributes={"dataset": "sales"},
        prefix="ghostdq",
    )

    points = _collect_points(reader)
    by_name = {p["name"]: p for p in points}

    assert by_name["ghostdq.row_count"]["value"] == 42
    assert by_name["ghostdq.row_count"]["attributes"]["dataset"] == "sales"

    assert by_name["ghostdq.null_rate"]["value"] == pytest.approx(0.05)
    assert by_name["ghostdq.null_rate"]["attributes"]["column"] == "email"

    assert by_name["ghostdq.duplicate_count"]["value"] == 3
    assert by_name["ghostdq.duplicate_count"]["attributes"]["column"] == "id"

    assert by_name["ghostdq.value_min"]["attributes"]["column"] == "amount"
    assert by_name["ghostdq.value_max"]["attributes"]["column"] == "amount"


def test_export_metrics_skips_nan() -> None:
    reader, meter = _make_reader_and_meter()

    export_metrics(
        {"value_min:amount": float("nan"), "row_count": 5},
        meter=meter,
        prefix="ghostdq",
    )

    points = _collect_points(reader)
    names = {p["name"] for p in points}
    assert "ghostdq.row_count" in names
    assert "ghostdq.value_min" not in names


def test_export_evaluations_records_rule_passed() -> None:
    reader, meter = _make_reader_and_meter()

    results = [
        RuleEvaluation(
            rule_type="null_rate",
            passed=True,
            value_display="0.01",
            constraint_display="max=0.05",
            column="email",
        ),
        RuleEvaluation(
            rule_type="row_count",
            passed=False,
            value_display="0",
            constraint_display="min=1",
        ),
    ]

    export_evaluations(results, meter=meter, prefix="ghostdq")

    points = _collect_points(reader)
    passed_points = [p for p in points if p["name"] == "ghostdq.rule.passed"]
    assert len(passed_points) == 2

    by_rule = {p["attributes"]["rule_type"]: p for p in passed_points}
    assert by_rule["null_rate"]["value"] == 1
    assert by_rule["null_rate"]["attributes"]["column"] == "email"
    assert by_rule["row_count"]["value"] == 0


def test_export_run_records_metrics_and_evaluations() -> None:
    reader, meter = _make_reader_and_meter()

    export_run(
        {"row_count": 9},
        [
            RuleEvaluation(
                rule_type="row_count",
                passed=True,
                value_display="9",
                constraint_display="",
            )
        ],
        meter=meter,
        prefix="ghostdq",
    )

    points = _collect_points(reader)
    assert any(p["name"] == "ghostdq.row_count" for p in points)
    assert any(p["name"] == "ghostdq.rule.passed" for p in points)


def test_is_otel_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GHOSTDQ_OTEL_ENABLED", raising=False)
    assert is_otel_enabled() is False

    monkeypatch.setenv("GHOSTDQ_OTEL_ENABLED", "1")
    assert is_otel_enabled() is True

    monkeypatch.setenv("GHOSTDQ_OTEL_ENABLED", "yes")
    assert is_otel_enabled() is True


def test_otel_metric_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GHOSTDQ_OTEL_METRIC_PREFIX", raising=False)
    assert otel_metric_prefix() == "ghostdq"

    monkeypatch.setenv("GHOSTDQ_OTEL_METRIC_PREFIX", "data_quality")
    assert otel_metric_prefix() == "data_quality"


def test_configure_meter_from_env_with_reader() -> None:
    from opentelemetry.sdk.metrics.export import InMemoryMetricReader

    reader = InMemoryMetricReader()
    meter = configure_meter_from_env(metric_readers=[reader])
    export_metrics({"row_count": 7}, meter=meter, prefix="ghostdq", flush=True)
    points = _collect_points(reader)
    assert any(p["name"] == "ghostdq.row_count" and p["value"] == 7 for p in points)


def test_otel_not_installed_error() -> None:
    with patch(
        "ghostdq.export.otel._require_otel",
        side_effect=OtelNotInstalledError('pip install "ghostdq[otel]"'),
    ):
        with pytest.raises(OtelNotInstalledError, match="ghostdq\\[otel\\]"):
            GhostDQOtelExporter()
