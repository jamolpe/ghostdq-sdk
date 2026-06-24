"""Command-line interface for GhostDQ.

Usage
-----
ghostdq run --dataset-id <uuid> --file data.csv \\
            --api-key ghd_xxx --ingest-url https://ingest.ghostdq.io

The command:
  1. Reads the file into a DataFrame.
  2. Fetches the active contract from the Ingest API (unless --contract is given).
  3. Computes all required metrics locally — raw data never leaves your machine.
  4. POSTs the metrics to the Ingest API.
  5. Prints the run_id and status.

Environment variables (override with flags):
  GHOSTDQ_API_KEY    — API key
  GHOSTDQ_INGEST_URL — Ingest API base URL
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ghostdq",
        description="GhostDQ data-quality CLI",
    )
    sub = p.add_subparsers(dest="command", required=True)

    run_cmd = sub.add_parser("run", help="Validate a file against a contract")
    run_cmd.add_argument("--dataset-id", required=True, help="Dataset UUID from the dashboard")
    run_cmd.add_argument(
        "--file",
        required=True,
        type=Path,
        help="Path to the data file (.csv, .parquet, .avro)",
    )
    run_cmd.add_argument(
        "--contract",
        type=Path,
        default=None,
        help="Path to a local contract YAML (skips fetching from the API)",
    )
    run_cmd.add_argument(
        "--api-key",
        default=None,
        help="API key (default: $GHOSTDQ_API_KEY)",
    )
    run_cmd.add_argument(
        "--ingest-url",
        default=None,
        help="Ingest API base URL (default: $GHOSTDQ_INGEST_URL)",
    )

    return p


def main(argv: list[str] | None = None) -> int:
    """Entry point; returns an exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        return _cmd_run(args)

    parser.print_help()
    return 1


def _cmd_run(args: argparse.Namespace) -> int:
    # Resolve credentials — CLI flags > env vars.
    api_key = args.api_key or os.environ.get("GHOSTDQ_API_KEY", "")
    ingest_url = args.ingest_url or os.environ.get("GHOSTDQ_INGEST_URL", "")

    if not api_key:
        print(
            "Error: --api-key or $GHOSTDQ_API_KEY is required",
            file=sys.stderr,
        )
        return 1
    if not ingest_url:
        print(
            "Error: --ingest-url or $GHOSTDQ_INGEST_URL is required",
            file=sys.stderr,
        )
        return 1

    # Lazy imports keep startup fast for `ghostdq --help`.
    from ghostdq.client import GhostDQAPIError, GhostDQClient
    from ghostdq.contract import parse_contract
    from ghostdq.io_pandas import read_file
    from ghostdq.metrics import compute_metrics

    client = GhostDQClient(api_key=api_key, ingest_url=ingest_url)

    # 1. Load contract.
    if args.contract:
        print(f"[ghostdq] Loading local contract: {args.contract}")
        contract_yaml = Path(args.contract).read_text()
    else:
        print("[ghostdq] Fetching contract from Ingest API…")
        try:
            contract_yaml = client.get_contract_yaml(args.dataset_id)
        except GhostDQAPIError as exc:
            print(f"Error fetching contract: {exc}", file=sys.stderr)
            return 1

    try:
        contract = parse_contract(contract_yaml)
    except ValueError as exc:
        print(f"Error parsing contract: {exc}", file=sys.stderr)
        return 1

    # 2. Read file.
    print(f"[ghostdq] Reading file: {args.file}")
    try:
        df = read_file(args.file)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error reading file: {exc}", file=sys.stderr)
        return 1

    print(f"[ghostdq] Loaded {len(df):,} rows x {len(df.columns)} columns")

    # 3. Compute metrics locally.
    print("[ghostdq] Computing metrics…")
    try:
        metrics = compute_metrics(df, contract.rules)
    except ValueError as exc:
        print(f"Error computing metrics: {exc}", file=sys.stderr)
        return 1

    print(f"[ghostdq] {len(metrics)} metric(s) computed")
    for k, v in sorted(metrics.items()):
        print(f"          {k} = {v}")

    # 4. POST to Ingest API.
    print("[ghostdq] Submitting run…")
    try:
        result = client.create_run(
            dataset_id=args.dataset_id,
            metrics=metrics,
            source="sdk",
        )
    except GhostDQAPIError as exc:
        print(f"Error submitting run: {exc}", file=sys.stderr)
        return 1

    print(f"[ghostdq] ✓  run_id={result.run_id}  status={result.status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
