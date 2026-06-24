"""Tests for ghostdq.cli — command-line interface."""

from __future__ import annotations

import textwrap
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from ghostdq.cli import main

CONTRACT_YAML = textwrap.dedent(
    """\
    dataset: sales
    version: 1
    rules:
      - row_count: {min: 1}
    """
)

CSV_CONTENT = textwrap.dedent(
    """\
    id,country,amount
    1,ES,100
    2,US,200
    """
)


@pytest.fixture()
def contract_file(tmp_path: Path) -> Path:
    p = tmp_path / "contract.yaml"
    p.write_text(CONTRACT_YAML)
    return p


@pytest.fixture()
def data_file(tmp_path: Path) -> Path:
    p = tmp_path / "data.csv"
    p.write_text(CSV_CONTENT)
    return p


def test_run_with_local_contract(contract_file: Path, data_file: Path) -> None:
    run_id = str(uuid.uuid4())

    mock_result = MagicMock()
    mock_result.run_id = run_id
    mock_result.status = "pending"

    with patch("ghostdq.client.GhostDQClient") as MockClient:
        instance = MockClient.return_value
        instance.create_run.return_value = mock_result

        exit_code = main(
            [
                "run",
                "--dataset-id", str(uuid.uuid4()),
                "--file", str(data_file),
                "--contract", str(contract_file),
                "--api-key", "ghd_test",
                "--ingest-url", "http://localhost:8001",
            ]
        )

    assert exit_code == 0
    instance.create_run.assert_called_once()
    call_kwargs = instance.create_run.call_args[1]
    assert "row_count" in call_kwargs["metrics"]


def test_run_missing_api_key(data_file: Path, contract_file: Path) -> None:
    exit_code = main(
        [
            "run",
            "--dataset-id", str(uuid.uuid4()),
            "--file", str(data_file),
            "--contract", str(contract_file),
            "--ingest-url", "http://localhost:8001",
        ]
    )
    assert exit_code == 1


def test_run_missing_ingest_url(data_file: Path, contract_file: Path) -> None:
    exit_code = main(
        [
            "run",
            "--dataset-id", str(uuid.uuid4()),
            "--file", str(data_file),
            "--contract", str(contract_file),
            "--api-key", "ghd_test",
        ]
    )
    assert exit_code == 1


def test_run_file_not_found(tmp_path: Path, contract_file: Path) -> None:
    exit_code = main(
        [
            "run",
            "--dataset-id", str(uuid.uuid4()),
            "--file", str(tmp_path / "nope.csv"),
            "--contract", str(contract_file),
            "--api-key", "ghd_test",
            "--ingest-url", "http://localhost:8001",
        ]
    )
    assert exit_code == 1


def test_run_api_error(data_file: Path, contract_file: Path) -> None:
    from ghostdq.client import GhostDQAPIError

    with patch("ghostdq.client.GhostDQClient") as MockClient:
        instance = MockClient.return_value
        instance.create_run.side_effect = GhostDQAPIError(401, "Unauthorized")

        exit_code = main(
            [
                "run",
                "--dataset-id", str(uuid.uuid4()),
                "--file", str(data_file),
                "--contract", str(contract_file),
                "--api-key", "ghd_test",
                "--ingest-url", "http://localhost:8001",
            ]
        )

    assert exit_code == 1
