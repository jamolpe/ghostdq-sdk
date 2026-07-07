"""GhostDQ — public data-quality SDK.

Quick start
-----------
>>> from ghostdq.reading import read_file
>>> from ghostdq.contract import parse_contract
>>> from ghostdq.metrics import compute_metrics
>>> from ghostdq.export import GhostDQClient

>>> df = read_file("data.csv")
>>> contract = parse_contract(open("contract.yaml").read())
>>> metrics = compute_metrics(df, contract.rules)
>>> client = GhostDQClient(api_key="ghd_...")
>>> result = client.create_run(dataset_id="<uuid>", metrics=metrics)

Or from the terminal (local — no API key):
    ghostdq run --contract contract.yaml --file data.csv
"""

from ghostdq.contract import (
    Contract,
    ContractParser,
    RuleSpec,
    parse_contract,
    required_columns,
)
from ghostdq.evaluation import RuleEvaluator, evaluate_rules
from ghostdq.export import (
    DEFAULT_INGEST_URL,
    GhostDQAPIError,
    GhostDQClient,
    RunResult,
)
from ghostdq.metrics import (
    ArrowMetricsEngine,
    MetricsEngine,
    StreamingCsvMetricsEngine,
    compute_csv_streaming,
    compute_metrics,
    compute_metrics_file,
)
from ghostdq.reading import PandasFileReader, read_file

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_INGEST_URL",
    "Contract",
    "ArrowMetricsEngine",
    "ContractParser",
    "GhostDQAPIError",
    "GhostDQClient",
    "MetricsEngine",
    "PandasFileReader",
    "RuleEvaluator",
    "RuleSpec",
    "RunResult",
    "StreamingCsvMetricsEngine",
    "compute_csv_streaming",
    "compute_metrics",
    "compute_metrics_file",
    "evaluate_rules",
    "parse_contract",
    "read_file",
    "required_columns",
]
