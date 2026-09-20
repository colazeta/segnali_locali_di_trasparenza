from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter
from pathlib import Path

import pandas as pd

from segnali_locali_di_trasparenza.transparency import (
    DiscoveryResult,
    PoliteClient,
    deterministic_region_sample,
    discover_transparency,
)


def existing_codes(path: Path) -> set[str]:
    if not path.exists():
        return set()
    frame = pd.read_csv(path, dtype=str)
    if "istat_code" not in frame.columns:
        return set()
    return set(frame["istat_code"].dropna().astype(str))


def append_result(path: Path, result: DiscoveryResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = result.to_dict()
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        if write_header:
            writer.writeheader()
        writer.writerow(row)



def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--registry",
        default="data/processed/municipalities.csv",
        help="Processed municipality registry",
    )
    parser.add_argument(
        "--output",
        default="data/observations/transparency_entrypoints.csv",
        help="Append-only observation CSV",
    )
    parser.add_argument(
        "--istat-codes",
        nargs="*",
        help="Optional explicit set of ISTAT codes to scan",
    )
    parser.add_argument(
        "--sample-per-region",
        type=int,
        help="Deterministic technical sample of N municipalities per region",
    )
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--delay", type=float, default=0.35)
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument(
        "--collector-version",
        default=os.environ.get("GITHUB_SHA", "local"),
        help="Code revision recorded with every observation",
    )
    parser.add_argument(
        "--methodology-version",
        default="signal001-v1",
        help="Versioned methodology identifier",
    )
    args = parser.parse_args()

    registry = pd.read_csv(args.registry, dtype=str).fillna("")
    registry["istat_code"] = registry["istat_code"].astype(str).str.zfill(6)

    if args.istat_codes and args.sample_per_region:
        parser.error("--istat-codes and --sample-per-region are mutually exclusive")

    if args.istat_codes:
        requested = {str(code).zfill(6) for code in args.istat_codes}
        registry = registry[registry["istat_code"].isin(requested)]
    elif args.sample_per_region:
        registry = deterministic_region_sample(registry, args.sample_per_region)

    registry = registry.iloc[args.offset :]
    if args.limit is not None:
        registry = registry.head(args.limit)

    output_path = Path(args.output)
    seen = existing_codes(output_path) if args.resume else set()
    client = PoliteClient(
        delay_seconds=args.delay,
        timeout_seconds=args.timeout,
    )
    statuses: Counter[str] = Counter()

    for row in registry.itertuples(index=False):
        if row.istat_code in seen:
            statuses["skipped_resume"] += 1
            continue

        result = discover_transparency(
            istat_code=row.istat_code,
            ipa_code=row.ipa_code,
            municipality_name=row.name,
            institutional_url=row.institutional_url,
            collector_version=args.collector_version,
            methodology_version=args.methodology_version,
            client=client,
        )
        append_result(output_path, result)
        statuses[result.status] += 1
        print(
            json.dumps(
                {
                    "istat_code": result.istat_code,
                    "name": result.municipality_name,
                    "status": result.status,
                    "transparency_url": result.transparency_url,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    print(json.dumps({"summary": dict(statuses)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
