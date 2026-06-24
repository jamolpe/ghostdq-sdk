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
    assert "dataset_id" in call_kwargs


def test_run_with_contract_only(contract_file: Path, data_file: Path) -> None:
    with patch("ghostdq.client.GhostDQClient") as MockClient:
        exit_code = main(
            [
                "run",
                "--file", str(data_file),
                "--contract", str(contract_file),
            ]
        )

    assert exit_code == 0
    MockClient.assert_not_called()


def test_run_local_fails_on_rule_violation(contract_file: Path, tmp_path: Path) -> None:
    bad_csv = tmp_path / "empty.csv"
    bad_csv.write_text("id\n")

    contract = tmp_path / "contract.yaml"
    contract.write_text(
        textwrap.dedent(
            """\
            dataset: sales
            version: 1
            rules:
              - row_count: {min: 10}
            """
        )
    )

    exit_code = main(["run", "--file", str(bad_csv), "--contract", str(contract)])
    assert exit_code == 1


def test_run_missing_contract_and_dataset_id(data_file: Path) -> None:
    exit_code = main(
        [
            "run",
            "--file", str(data_file),
        ]
    )
    assert exit_code == 1


def test_run_missing_api_key_for_remote(data_file: Path, contract_file: Path) -> None:
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


def test_run_default_ingest_url(data_file: Path, contract_file: Path) -> None:
    from ghostdq.client import DEFAULT_INGEST_URL

    mock_result = MagicMock()
    mock_result.run_id = str(uuid.uuid4())
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
            ]
        )

    assert exit_code == 0
    MockClient.assert_called_once_with(
        api_key="ghd_test",
        ingest_url=DEFAULT_INGEST_URL,
    )


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
