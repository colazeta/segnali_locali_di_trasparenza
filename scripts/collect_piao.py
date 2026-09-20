from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter
from pathlib import Path

import pandas as pd

from segnali_locali_di_trasparenza.piao import PortalClient, discover_piao_for_ipa


OUTPUT_FIELDS = [
    "istat_code",
    "municipality_name",
    "registry_ipa_code",
    "piao_present",
    "portal_node_id",
    "portal_url",
    "piao_ipa_code",
    "administration_name",
    "reference_period",
    "reference_start_year",
    "reference_end_year",
    "approval_date",
    "portal_published_at",
    "pdf_url",
    "pa_url",
    "observed_at",
    "source",
    "collector_version",
    "methodology_version",
    "evidence_sha256",
]


def write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="data/processed/municipalities.csv")
    parser.add_argument("--output", default="data/observations/piao_publications.csv")
    parser.add_argument("--istat-codes", nargs="*")
    parser.add_argument("--shard-index", type=int)
    parser.add_argument("--shard-count", type=int)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--delay", type=float, default=0.4)
    parser.add_argument("--timeout", type=float, default=12)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--max-pages-per-ipa", type=int, default=20)
    parser.add_argument(
        "--collector-version",
        default=os.environ.get("GITHUB_SHA", "local"),
    )
    args = parser.parse_args()

    registry = pd.read_csv(args.registry, dtype=str, keep_default_na=False)
    registry["istat_code"] = registry["istat_code"].astype(str).str.zfill(6)

    if args.istat_codes:
        wanted = {str(value).zfill(6) for value in args.istat_codes}
        registry = registry[registry["istat_code"].isin(wanted)]

    if args.shard_index is not None or args.shard_count is not None:
        if args.shard_index is None or args.shard_count is None:
            parser.error("--shard-index and --shard-count must be supplied together")
        if args.shard_count <= 0 or not 0 <= args.shard_index < args.shard_count:
            parser.error("invalid shard configuration")
        registry = registry.iloc[
            [index for index in range(len(registry)) if index % args.shard_count == args.shard_index]
        ]

    if args.limit is not None:
        registry = registry.head(args.limit)

    client = PortalClient(
        delay_seconds=args.delay,
        timeout_seconds=args.timeout,
        retry_total=args.retries,
    )
    output = Path(args.output)
    statuses: Counter[str] = Counter()

    for row in registry.itertuples(index=False):
        records = discover_piao_for_ipa(
            row.ipa_code,
            client=client,
            collector_version=args.collector_version,
            max_pages=args.max_pages_per_ipa,
        )

        if records:
            rows = []
            for record in records:
                data = record.to_dict()
                rows.append(
                    {
                        "istat_code": row.istat_code,
                        "municipality_name": row.name,
                        "registry_ipa_code": row.ipa_code,
                        "piao_present": True,
                        "portal_node_id": data["portal_node_id"],
                        "portal_url": data["portal_url"],
                        "piao_ipa_code": data["ipa_code"],
                        "administration_name": data["administration_name"],
                        "reference_period": data["reference_period"],
                        "reference_start_year": data["reference_start_year"],
                        "reference_end_year": data["reference_end_year"],
                        "approval_date": data["approval_date"],
                        "portal_published_at": data["portal_published_at"],
                        "pdf_url": data["pdf_url"],
                        "pa_url": data["pa_url"],
                        "observed_at": data["observed_at"],
                        "source": data["source"],
                        "collector_version": data["collector_version"],
                        "methodology_version": data["methodology_version"],
                        "evidence_sha256": data["evidence_sha256"],
                    }
                )
            write_rows(output, rows)
            statuses["present"] += 1
        else:
            write_rows(
                output,
                [
                    {
                        "istat_code": row.istat_code,
                        "municipality_name": row.name,
                        "registry_ipa_code": row.ipa_code,
                        "piao_present": False,
                        "portal_node_id": "",
                        "portal_url": "",
                        "piao_ipa_code": "",
                        "administration_name": "",
                        "reference_period": "",
                        "reference_start_year": "",
                        "reference_end_year": "",
                        "approval_date": "",
                        "portal_published_at": "",
                        "pdf_url": "",
                        "pa_url": "",
                        "observed_at": "",
                        "source": "Portale PIAO - Dipartimento della Funzione Pubblica",
                        "collector_version": args.collector_version,
                        "methodology_version": "piao001-v1",
                        "evidence_sha256": "",
                    }
                ],
            )
            statuses["not_found_on_portal"] += 1

        print(
            json.dumps(
                {
                    "istat_code": row.istat_code,
                    "name": row.name,
                    "ipa_code": row.ipa_code,
                    "piao_records": len(records),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    print(json.dumps({"summary": dict(statuses)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
