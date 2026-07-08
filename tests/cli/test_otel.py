"""CLI tests for OpenTelemetry export."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from ghostdq.cli import main

pytest.importorskip("opentelemetry")


@pytest.fixture(autouse=True)
def _clear_otel_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GHOSTDQ_OTEL_ENABLED", raising=False)
    monkeypatch.delenv("GHOSTDQ_OTEL_METRIC_PREFIX", raising=False)


def test_run_export_otel_flag(contract_file: Path, data_file: Path) -> None:
    with (
        patch("ghostdq.export.otel.configure_meter_from_env") as configure_meter,
        patch("ghostdq.export.otel.export_run") as export_run,
    ):
        configure_meter.return_value = object()
        exit_code = main(
            [
                "run",
                "--file",
                str(data_file),
                "--contract",
                str(contract_file),
                "--export-otel",
            ]
        )

    assert exit_code == 0
    export_run.assert_called_once()
    call_kwargs = export_run.call_args[1]
    assert call_kwargs["attributes"]["ghostdq.source"] == "cli"
    assert call_kwargs["attributes"]["dataset"] == "sales"
    assert "row_count" in export_run.call_args[0][0]


def test_run_export_otel_env_var(contract_file: Path, data_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GHOSTDQ_OTEL_ENABLED", "1")

    with (
        patch("ghostdq.export.otel.configure_meter_from_env") as configure_meter,
        patch("ghostdq.export.otel.export_run") as export_run,
    ):
        configure_meter.return_value = object()
        exit_code = main(
            [
                "run",
                "--file",
                str(data_file),
                "--contract",
                str(contract_file),
            ]
        )

    assert exit_code == 0
    export_run.assert_called_once()
