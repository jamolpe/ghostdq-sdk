"""Command-line interface for GhostDQ.

Usage
-----
Local validation (no API key, nothing sent to the server):

    ghostdq run --contract contract.yaml --file data.csv

Remote run (fetch contract and/or submit metrics to the Ingest API):

    ghostdq run --dataset-id <uuid> --file data.csv --api-key ghd_xxx

Environment variables (override with flags):
  GHOSTDQ_API_KEY     — API key (only required for remote runs)
  GHOSTDQ_DATASET_ID  — dataset UUID (enables remote submit)
  GHOSTDQ_INGEST_URL  — Ingest API base URL (default: https://ghostdq.com/ingest)
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
    run_cmd.add_argument(
        "--dataset-id",
        default=None,
        help="Dataset UUID — fetches contract and submits metrics to the Ingest API",
    )
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
        help="Path to a local contract YAML (local validation; no API key needed)",
    )
    run_cmd.add_argument(
        "--api-key",
        default=None,
        help="API key for remote runs (default: $GHOSTDQ_API_KEY)",
    )
    run_cmd.add_argument(
        "--ingest-url",
        default=None,
        help="Ingest API base URL (default: $GHOSTDQ_INGEST_URL or https://ghostdq.com/ingest)",
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
    from ghostdq.contract import parse_contract
    from ghostdq.evaluate import evaluate_rules, format_evaluation_line
    from ghostdq.io_pandas import read_file
    from ghostdq.metrics import compute_metrics

    dataset_id = args.dataset_id or os.environ.get("GHOSTDQ_DATASET_ID")
    remote = bool(dataset_id)

    if not args.contract and not remote:
        print(
            "Error: --contract is required for local runs, "
            "or pass --dataset-id (or $GHOSTDQ_DATASET_ID) for a remote run",
            file=sys.stderr,
        )
        return 1

    api_key = args.api_key or os.environ.get("GHOSTDQ_API_KEY", "")
    if remote and not api_key:
        print(
            "Error: --api-key or $GHOSTDQ_API_KEY is required when using --dataset-id",
            file=sys.stderr,
        )
        return 1

    # 1. Load contract.
    if args.contract:
        contract_yaml = Path(args.contract).read_text()
    else:
        from ghostdq.client import DEFAULT_INGEST_URL, GhostDQAPIError, GhostDQClient

        ingest_url = (
            args.ingest_url
            or os.environ.get("GHOSTDQ_INGEST_URL")
            or DEFAULT_INGEST_URL
        )
        client = GhostDQClient(api_key=api_key, ingest_url=ingest_url)
        try:
            contract_yaml = client.get_contract_yaml(dataset_id)
        except GhostDQAPIError as exc:
            print(f"Error fetching contract: {exc}", file=sys.stderr)
            return 1

    try:
        contract = parse_contract(contract_yaml)
    except ValueError as exc:
        print(f"Error parsing contract: {exc}", file=sys.stderr)
        return 1

    # 2. Read file.
    try:
        df = read_file(args.file)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error reading file: {exc}", file=sys.stderr)
        return 1

    # 3. Compute and evaluate metrics locally.
    try:
        metrics = compute_metrics(df, contract.rules)
        results = evaluate_rules(contract.rules, metrics)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    for result in results:
        print(format_evaluation_line(result))

    all_passed = all(r.passed for r in results)

    if not remote:
        return 0 if all_passed else 1

    # 4. POST to Ingest API (remote run only).
    from ghostdq.client import DEFAULT_INGEST_URL, GhostDQAPIError, GhostDQClient

    ingest_url = (
        args.ingest_url
        or os.environ.get("GHOSTDQ_INGEST_URL")
        or DEFAULT_INGEST_URL
    )
    client = GhostDQClient(api_key=api_key, ingest_url=ingest_url)
    try:
        result = client.create_run(
            dataset_id=dataset_id,
            metrics=metrics,
            source="sdk",
        )
    except GhostDQAPIError as exc:
        print(f"Error submitting run: {exc}", file=sys.stderr)
        return 1

    print(f"run_id={result.run_id}  status={result.status}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
