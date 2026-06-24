# ghostdq — Python SDK

[![PyPI](https://img.shields.io/pypi/v/ghostdq)](https://pypi.org/project/ghostdq/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

The **GhostDQ SDK** lets you compute data-quality metrics **locally** and ship only the aggregated numbers to the GhostDQ cloud — your raw data never leaves your infrastructure.

---

## Install

```bash
pip install ghostdq
```

Optional extras (Avro support requires `fastavro`, Parquet requires `pyarrow` — both are included in the core install):

```bash
pip install "ghostdq[dev]"   # adds pytest, ruff, mypy, stubs
```

---

## Quick start

```python
from ghostdq import read_file, parse_contract, compute_metrics, GhostDQClient

# 1. Load your data
df = read_file("sales_2024.parquet")   # .csv / .parquet / .avro

# 2. Parse the contract (or fetch it from the API — see below)
contract = parse_contract(open("sales_contract.yaml").read())

# 3. Compute metrics *locally* — no raw data leaves your machine
metrics = compute_metrics(df, contract.rules)
# → {"row_count": 120000, "null_rate:country": 0.02, ...}

# 4. Ship the metrics to GhostDQ
client = GhostDQClient(api_key="ghd_your_key")
result = client.create_run(dataset_id="<dataset-uuid>", metrics=metrics)
print(result.run_id, result.status)  # ⇒ <uuid>  pending
```

---

## CLI

```bash
# Validate a file against a local contract
ghostdq run \
  --dataset-id <uuid> \
  --file sales.csv \
  --contract contract.yaml \
  --api-key ghd_xxx

# Fetch the contract automatically from the API
ghostdq run \
  --dataset-id <uuid> \
  --file sales.parquet \
  --api-key ghd_xxx
```

Environment variable shortcuts:
```bash
export GHOSTDQ_API_KEY=ghd_xxx
ghostdq run --dataset-id <uuid> --file sales.csv
```

The Ingest API defaults to `https://ghostdq.com/ingest`. Override with `--ingest-url` or `GHOSTDQ_INGEST_URL` (e.g. `http://localhost:8000` for local dev).

---

## Supported file formats

| Format  | Extension   | Engine       |
|---------|-------------|--------------|
| CSV     | `.csv`      | pandas       |
| Parquet | `.parquet`  | pyarrow      |
| Avro    | `.avro`     | fastavro     |

---

## Supported rule types

| Rule             | Metric key(s)                                     |
|------------------|---------------------------------------------------|
| `row_count`      | `row_count`                                       |
| `null_rate`      | `null_rate:{column}`                              |
| `unique`         | `duplicate_count:{column}`                        |
| `value_range`    | `value_min:{column}`, `value_max:{column}`        |
| `allowed_values` | `disallowed_count:{column}`                       |

---

## Local development

Requires Python **3.10+** (3.13 recommended). From the repo root:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests
ruff check src tests
mypy src tests --ignore-missing-imports
```

---

## License & disclaimer

Licensed under [Apache License 2.0](LICENSE).

This software is provided **“as is”**, without warranty of any kind. You are responsible for evaluating whether it fits your use case and for any outcomes from using it. See the [LICENSE](LICENSE) for the full terms, including limitations of liability.
