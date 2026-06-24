"""Tests for ghostdq.client — HTTP client (no real network)."""

from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from ghostdq.client import GhostDQAPIError, GhostDQClient, RunResult


def _make_client() -> GhostDQClient:
    return GhostDQClient(api_key="ghd_test_key", ingest_url="http://localhost:8001")


def _mock_urlopen(response_body: dict[str, Any]) -> MagicMock:
    """Return a context-manager mock that yields a response with JSON body."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(response_body).encode()
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=mock_resp)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def test_create_run_success() -> None:
    run_id = str(uuid.uuid4())
    client = _make_client()

    with patch("ghostdq.client.urlopen", return_value=_mock_urlopen({"run_id": run_id, "status": "pending"})):
        result = client.create_run(dataset_id=uuid.uuid4(), metrics={"row_count": 100})

    assert isinstance(result, RunResult)
    assert result.run_id == run_id
    assert result.status == "pending"


def test_create_run_api_error() -> None:
    from urllib.error import HTTPError

    client = _make_client()
    fp = MagicMock()
    fp.read.return_value = b'{"detail":"invalid key"}'
    err = HTTPError(url="http://x", code=401, msg="Unauthorized", hdrs=MagicMock(), fp=fp)

    with patch("ghostdq.client.urlopen", side_effect=err), pytest.raises(GhostDQAPIError) as exc_info:
        client.create_run(dataset_id=uuid.uuid4(), metrics={})

    assert exc_info.value.status_code == 401


def test_get_contract_yaml_success() -> None:
    dataset_id = str(uuid.uuid4())
    yaml_text = "dataset: sales\nversion: 1\nrules: []\n"
    client = _make_client()

    with patch(
        "ghostdq.client.urlopen",
        return_value=_mock_urlopen(
            {"dataset_id": dataset_id, "version": 1, "yaml_text": yaml_text, "rules_json": {}}
        ),
    ):
        result = client.get_contract_yaml(dataset_id)

    assert result == yaml_text


def test_client_strips_trailing_slash() -> None:
    client = GhostDQClient(api_key="k", ingest_url="http://localhost:8001/")
    assert client._base == "http://localhost:8001"
