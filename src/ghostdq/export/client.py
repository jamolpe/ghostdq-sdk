"""HTTP client for shipping metrics to the GhostDQ Ingest API.

Uses the standard library ``urllib`` only — no ``httpx``, no ``requests``.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from ghostdq.export.constants import DEFAULT_INGEST_URL
from ghostdq.export.exceptions import GhostDQAPIError


@dataclass
class RunResult:
    run_id: str
    status: str


class GhostDQClient:
    """Lightweight client for the GhostDQ Ingest API.

    Args:
        api_key: Secret API key (``ghd_…`` token issued by the control plane).
        ingest_url: Base URL of the Ingest API (default: ``https://ghostdq.com/ingest``).
        timeout: Request timeout in seconds (default 30).
    """

    def __init__(
        self,
        api_key: str,
        ingest_url: str = DEFAULT_INGEST_URL,
        timeout: int = 30,
    ) -> None:
        self._api_key = api_key
        self._base = ingest_url.rstrip("/")
        self._timeout = timeout

    def create_run(
        self,
        dataset_id: str | uuid.UUID | None = None,
        metrics: dict[str, Any] | None = None,
        source: str = "sdk",
        *,
        dataset: str | None = None,
    ) -> RunResult:
        """POST /v1/runs — submit computed metrics."""
        if metrics is None:
            raise TypeError("create_run() missing required argument: 'metrics'")
        if (dataset_id is None) == (dataset is None):
            raise ValueError("exactly one of dataset_id or dataset must be provided")

        payload: dict[str, Any] = {"metrics": metrics, "source": source}
        if dataset_id is not None:
            payload["dataset_id"] = str(dataset_id)
        else:
            payload["dataset"] = dataset

        body = json.dumps(payload).encode()
        data = self._post("/v1/runs", body)
        return RunResult(run_id=data["run_id"], status=data["status"])

    def get_contract_yaml(self, dataset_id: str | uuid.UUID) -> str:
        """GET /v1/datasets/{id}/contract — fetch the latest rule contract."""
        data = self._get(f"/v1/datasets/{dataset_id}/contract")
        return str(data["yaml_text"])

    def _post(self, path: str, body: bytes) -> dict[str, Any]:
        req = Request(
            url=f"{self._base}{path}",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Api-Key": self._api_key,
            },
        )
        return self._send(req)

    def _get(self, path: str) -> dict[str, Any]:
        req = Request(
            url=f"{self._base}{path}",
            method="GET",
            headers={"X-Api-Key": self._api_key},
        )
        return self._send(req)

    def _send(self, req: Request) -> dict[str, Any]:
        try:
            with urlopen(req, timeout=self._timeout) as resp:
                raw = resp.read()
        except HTTPError as exc:
            raw_body = exc.read().decode(errors="replace")
            raise GhostDQAPIError(
                status_code=exc.code,
                message=f"Ingest API returned {exc.code}: {raw_body}",
            ) from exc

        return json.loads(raw)  # type: ignore[no-any-return]
