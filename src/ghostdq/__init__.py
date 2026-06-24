"""GhostDQ — public data-quality SDK.

Quick start
-----------
>>> from ghostdq.io_pandas import read_file
>>> from ghostdq.contract import parse_contract
>>> from ghostdq.metrics import compute_metrics
>>> from ghostdq.client import GhostDQClient

>>> df = read_file("data.csv")
>>> contract = parse_contract(open("contract.yaml").read())
>>> metrics = compute_metrics(df, contract.rules)
>>> client = GhostDQClient(api_key="ghd_...")
>>> result = client.create_run(dataset_id="<uuid>", metrics=metrics)

Or from the terminal:
    ghostdq run --dataset-id <uuid> --file data.csv --api-key ghd_...
"""

from ghostdq.client import (
    DEFAULT_INGEST_URL,
    GhostDQAPIError,
    GhostDQClient,
    RunResult,
)
from ghostdq.contract import Contract, RuleSpec, parse_contract
from ghostdq.io_pandas import read_file
from ghostdq.metrics import compute_metrics

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_INGEST_URL",
    "Contract",
    "GhostDQAPIError",
    "GhostDQClient",
    "RuleSpec",
    "RunResult",
    "compute_metrics",
    "parse_contract",
    "read_file",
]
