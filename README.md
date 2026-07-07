# ghostdq — Python SDK

[![PyPI](https://img.shields.io/pypi/v/ghostdq)](https://pypi.org/project/ghostdq/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

The **GhostDQ SDK** computes data-quality metrics **locally** and ships only aggregated numbers to the GhostDQ Ingest API. Your raw data never leaves your infrastructure.

The main integration point is **`compute_metrics(df, rules)`** — pass a pandas DataFrame (or use a high-performance backend when reading from disk). File I/O is optional convenience.

---

## Install

```bash
pip install ghostdq
```

Optional extras:

```bash
pip install "ghostdq[polars]"   # Polars lazy-scan backend
pip install "ghostdq[duckdb]"   # DuckDB SQL backend
pip install "ghostdq[fast]"     # both Polars and DuckDB
pip install "ghostdq[dev]"      # pytest, ruff, mypy, stubs
```

Core dependencies: pandas, pyarrow, fastavro, pyyaml. The HTTP client uses stdlib `urllib` only.

---

## Quick start

```python
from ghostdq import (
    GhostDQClient,
    compute_metrics,
    parse_contract,
    read_file,
)

# 1. Parse the contract (or fetch from the API — see below)
contract = parse_contract(open("sales_contract.yaml").read())

# 2. Load data (optional if you already have a DataFrame)
df = read_file("sales_2024.parquet", columns=contract.required_columns())

# 3. Compute metrics locally
metrics = compute_metrics(df, contract.rules)
# → {"row_count": 120000, "null_rate:country": 0.02, ...}

# 4. Ship metrics to GhostDQ
client = GhostDQClient(api_key="ghd_your_key")
result = client.create_run(dataset_id="<dataset-uuid>", metrics=metrics)
print(result.run_id, result.status)  # ⇒ <uuid>  pending
```

If your pipeline already produces a DataFrame (Spark, SQL, Polars, etc.), skip `read_file` and call `compute_metrics` directly.

---

## Package layout

```
ghostdq/
├── contract/       Contract, RuleSpec, ContractParser, parse_contract
├── reading/        PandasFileReader, read_file (CSV / Parquet / Avro)
├── metrics/        MetricsEngine and performance backends
├── evaluation/     RuleEvaluator — local pass/fail without network
├── export/         GhostDQClient — POST metrics to the Ingest API
└── cli/            ghostdq run
```

Backward-compatible shims remain at `ghostdq.client`, `ghostdq.io_pandas`, and `ghostdq.evaluate`.

### Main classes

| Class | Purpose |
|-------|---------|
| `ContractParser` | Parse YAML contracts |
| `PandasFileReader` | Read files into a DataFrame |
| `MetricsEngine` | Compute metrics from a pandas DataFrame |
| `ArrowMetricsEngine` | Compute metrics from a PyArrow table (no pandas) |
| `StreamingCsvMetricsEngine` | Chunked CSV scan (constant memory) |
| `PolarsMetricsEngine` | Lazy Polars scans (optional extra) |
| `DuckDBMetricsEngine` | SQL over files (optional extra) |
| `RuleEvaluator` | Evaluate rules locally |
| `GhostDQClient` | Submit metrics to the Ingest API |

Functional shortcuts (`compute_metrics`, `parse_contract`, `read_file`, …) delegate to default instances of the classes above.

---

## Computing metrics

### Pandas DataFrame (default)

The primary API. Only columns referenced by the contract are scanned; extra columns in a wide DataFrame are ignored.

```python
from ghostdq import compute_metrics, required_columns

# Optional: pre-narrow before compute
cols = contract.required_columns()
metrics = compute_metrics(df[cols], contract.rules)

# Or pass the full frame — compute_metrics narrows internally
metrics = compute_metrics(df, contract.rules)
```

`MetricsEngine` batches work per column (single `to_numeric` pass for min/max, single duplicate scan when both count and rate are needed).

### From a file (auto backend)

`compute_metrics_file` picks a backend based on format when `engine="auto"`:

| Format | Auto backend | Why |
|--------|--------------|-----|
| `.csv` | `streaming` | Chunked read, constant memory |
| `.parquet` | `arrow` | Native PyArrow, no pandas conversion |
| other | `pandas` | Avro and fallback |

```python
from ghostdq import compute_metrics_file

metrics = compute_metrics_file("huge.csv", contract.rules)
metrics = compute_metrics_file("wide.parquet", contract.rules, engine="arrow")
metrics = compute_metrics_file("data.csv", contract.rules, engine="pandas")
```

### Streaming CSV

For very large CSV files without loading into memory:

```python
from ghostdq import compute_csv_streaming

metrics = compute_csv_streaming(
    "huge.csv",
    contract.rules,
    chunksize=50_000,
    columns=contract.required_columns(),
)
```

### Arrow (Parquet)

Skip pandas when the source is already Arrow or Parquet:

```python
import pyarrow.parquet as pq
from ghostdq import ArrowMetricsEngine, compute_arrow_metrics

table = pq.read_table("data.parquet", columns=contract.required_columns())
metrics = compute_arrow_metrics(table, contract.rules)

# Or read + compute in one step:
metrics = ArrowMetricsEngine().compute_parquet("data.parquet", contract.rules)
```

### Polars (optional)

```bash
pip install "ghostdq[polars]"
```

```python
import polars as pl
from ghostdq.metrics import PolarsMetricsEngine

engine = PolarsMetricsEngine()
metrics = engine.compute_parquet("data.parquet", contract.rules)
metrics = engine.compute(pl.scan_csv("data.csv"), contract.rules)
```

### DuckDB (optional)

```bash
pip install "ghostdq[duckdb]"
```

```python
import duckdb
from ghostdq.metrics import DuckDBMetricsEngine

conn = duckdb.connect()
metrics = DuckDBMetricsEngine().compute_path(conn, "data.parquet", contract.rules)
```

---

## Contracts

Contracts are YAML files that define dataset rules. Parse them with `parse_contract` or `ContractParser`:

```python
from ghostdq import ContractParser, parse_contract, required_columns

contract = parse_contract(yaml_text)
contract = ContractParser().parse(yaml_text)

contract.required_columns()   # columns referenced by rules
contract.all_metric_keys()    # metric keys the server expects
required_columns(contract.rules)
```

Example contract:

```yaml
dataset: sales
version: 1
rules:
  - row_count: {min: 1, max: 1000000}
  - null_rate: {column: country, max: 0.05}
  - unique: {column: order_id}
  - duplicate_rate: {column: order_id, max: 0.01}
  - value_range: {column: amount, min: 0, max: 10000}
  - allowed_values: {column: country, values: [ES, US, MX]}
  - out_of_range_rate: {column: amount, min: 0, max: 10000, max_rate: 0.001}
  - regex_match: {column: order_id, pattern: '^ORD-[0-9]+$', min_rate: 1.0}
```

See also the ready-to-run samples in [`examples/`](examples/).

### Supported rule types

| Rule | Metric key(s) |
|------|----------------|
| `row_count` | `row_count` |
| `null_rate` | `null_rate:{column}` |
| `unique` | `duplicate_count:{column}` |
| `duplicate_rate` | `duplicate_rate:{column}` |
| `value_range` | `value_min:{column}`, `value_max:{column}` |
| `allowed_values` | `disallowed_count:{column}` |
| `out_of_range_rate` | `out_of_range_rate:{column}` |
| `regex_match` | `regex_match_rate:{column}` |

### Rule examples

**`out_of_range_rate`** — row-level bounds (like Great Expectations `expect_column_values_to_be_between`). Fails when more than `max_rate` of rows are null, non-numeric, below `min`, or above `max`:

```yaml
- out_of_range_rate: {column: amount, min: 0, max: 10000, max_rate: 0}
```

**`value_range`** — dataset-level bounds. Checks that the column’s observed min/max fall within the limits (a single outlier row does not fail if the aggregate min/max are still in range):

```yaml
- value_range: {column: amount, min: 0, max: 10000}
```

**`regex_match`** — whole-string regex match (like `expect_column_values_to_match_regex`). Nulls count as mismatches. Use `[0-9]` in YAML patterns instead of `\d` (backslashes are not escaped in single-quoted YAML):

```yaml
- regex_match: {column: order_id, pattern: '^ORD-[0-9]+$', min_rate: 1.0}
- regex_match: {column: email, pattern: '^[^@]+@[^@]+\\.[^@]+$', min_rate: 0.99}
```

---

## Local evaluation

Check pass/fail without calling the API:

```python
from ghostdq import RuleEvaluator, evaluate_rules

results = evaluate_rules(contract.rules, metrics)
for r in results:
    print("✓" if r.passed else "✗", r.rule_type, r.value_display)

evaluator = RuleEvaluator()
results = evaluator.evaluate(contract.rules, metrics)
print(evaluator.format_line(results[0]))
```

---

## Reading files

File reading is optional — use it when you don't already have a DataFrame.

```python
from ghostdq import PandasFileReader, read_file

df = read_file("data.parquet", columns=contract.required_columns())
df = PandasFileReader().read_csv("data.csv", columns=["id", "amount"])
```

| Format | Extension | Reader |
|--------|-----------|--------|
| CSV | `.csv` | pandas |
| Parquet | `.parquet` | pyarrow (column pruning supported) |
| Avro | `.avro` | fastavro |

---

## CLI

```bash
# Local validation (no API key)
ghostdq run --contract contract.yaml --file sales.csv

# Remote run: fetch contract + submit metrics
ghostdq run --dataset-id <uuid> --file sales.parquet --api-key ghd_xxx

# Pick a metrics backend
ghostdq run --contract contract.yaml --file huge.csv --engine streaming --chunk-size 50000
ghostdq run --contract contract.yaml --file data.parquet --engine arrow
```

| Flag | Description |
|------|-------------|
| `--contract` | Local contract YAML (required for offline runs) |
| `--dataset-id` | Dataset UUID (enables remote contract fetch + submit) |
| `--file` | Data file (`.csv`, `.parquet`, `.avro`) |
| `--api-key` | API key (`GHOSTDQ_API_KEY`) |
| `--ingest-url` | Ingest API base URL (`GHOSTDQ_INGEST_URL`, default `https://ghostdq.com/ingest`) |
| `--engine` | `auto`, `pandas`, `arrow`, `streaming`, `polars`, `duckdb` |
| `--chunk-size` | CSV chunk size for streaming engine (default `100000`) |

Environment shortcuts:

```bash
export GHOSTDQ_API_KEY=ghd_xxx
export GHOSTDQ_DATASET_ID=<uuid>
ghostdq run --file sales.csv --contract contract.yaml
```

---

## Exporting metrics

```python
from ghostdq import GhostDQClient

client = GhostDQClient(api_key="ghd_xxx", ingest_url="https://ghostdq.com/ingest")

# By dataset UUID (dashboard)
result = client.create_run(dataset_id="<uuid>", metrics=metrics)

# By dataset name (contract YAML)
result = client.create_run(dataset="sales", metrics=metrics)

# Fetch contract from the API
yaml_text = client.get_contract_yaml("<uuid>")
```

---

## Choosing a backend

| Situation | Recommendation |
|-----------|----------------|
| You already have a pandas DataFrame | `compute_metrics(df, rules)` |
| Large CSV on disk | `compute_csv_streaming` or `compute_metrics_file(..., engine="streaming")` |
| Large Parquet on disk | `ArrowMetricsEngine` or `compute_metrics_file(..., engine="arrow")` |
| Polars pipeline | `PolarsMetricsEngine` |
| SQL / analytics stack with DuckDB | `DuckDBMetricsEngine` |
| Avro files | `read_file` + `compute_metrics` (pandas path) |
| CLI one-shot | `ghostdq run` with `--engine auto` (default) |

All backends produce the same metric key format expected by the GhostDQ Ingest API.

---

## Local development

Requires Python **3.10+**. From the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,fast]"
pytest tests
ruff check src tests
mypy src tests --ignore-missing-imports
```

Test layout mirrors the package:

```
tests/
├── contract/
├── reading/
├── metrics/
├── evaluation/
├── export/
└── cli/
```

---

## License & disclaimer

Licensed under [Apache License 2.0](LICENSE).

This software is provided **“as is”**, without warranty of any kind. You are responsible for evaluating whether it fits your use case and for any outcomes from using it. See the [LICENSE](LICENSE) for the full terms, including limitations of liability.
