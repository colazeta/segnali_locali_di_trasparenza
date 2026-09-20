from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests

from segnali_locali_di_trasparenza.piao import (
    PiaoApiError,
    deterministic_shard,
    fetch_publications_for_ipa,
    make_session,
    normalise_publication,
)


STATUS_FIELDS = [
    "istat_code",
    "municipality_name",
    "ipa_code",
    "lookup_status",
    "piao_present_on_portal",
    "publication_count",
    "target_start_year",
    "period_starting_target_year_present",
    "period_starting_target_year_publication_count",
    "latest_reference_period",
    "latest_reference_start_year",
    "latest_reference_end_year",
    "latest_version",
    "latest_approval_date",
    "latest_piao_document_url",
    "portal_publication_date_status",
    "retrieved_at",
    "error",
]

PUBLICATION_PREFIX_FIELDS = [
    "istat_code",
    "municipality_name",
]


def append_row(path: Path, row: dict[str, object], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def latest_publication(publications: list[dict[str, object]]) -> dict[str, object] | None:
    if not publications:
        return None

    def key(item: dict[str, object]) -> tuple[int, int, str]:
        start = item.get("reference_start_year")
        version = item.get("version")
        return (
            int(start) if start not in (None, "") else -1,
            int(version) if version not in (None, "") else -1,
            str(item.get("approval_date") or ""),
        )

    return max(publications, key=key)


def status_row(
    *,
    registry_row: object,
    publications: list[dict[str, object]],
    target_start_year: int,
    retrieved_at: str,
    lookup_status: str,
    error: str = "",
) -> dict[str, object]:
    current = [
        item
        for item in publications
        if item.get("reference_start_year") == target_start_year
    ]
    latest = latest_publication(publications) or {}

    return {
        "istat_code": registry_row.istat_code,
        "municipality_name": registry_row.name,
        "ipa_code": registry_row.ipa_code,
        "lookup_status": lookup_status,
        "piao_present_on_portal": bool(publications),
        "publication_count": len(publications),
        "target_start_year": target_start_year,
        "period_starting_target_year_present": bool(current),
        "period_starting_target_year_publication_count": len(current),
        "latest_reference_period": latest.get("reference_period", ""),
        "latest_reference_start_year": latest.get("reference_start_year", ""),
        "latest_reference_end_year": latest.get("reference_end_year", ""),
        "latest_version": latest.get("version", ""),
        "latest_approval_date": latest.get("approval_date", ""),
        "latest_piao_document_url": latest.get("piao_document_url", ""),
        "portal_publication_date_status": (
            "not_exposed_by_public_api" if publications else ""
        ),
        "retrieved_at": retrieved_at,
        "error": error,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="data/processed/municipalities.csv")
    parser.add_argument(
        "--status-output",
        default="data/piao/piao_status.csv",
    )
    parser.add_argument(
        "--publications-output",
        default="data/piao/piao_publications.csv",
    )
    parser.add_argument("--istat-codes", nargs="*")
    parser.add_argument("--shard-index", type=int)
    parser.add_argument("--shard-count", type=int)
    parser.add_argument("--delay", type=float, default=0.35)
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument(
        "--target-start-year",
        type=int,
        default=datetime.now(UTC).year,
    )
    args = parser.parse_args()

    registry = pd.read_csv(
        args.registry,
        dtype=str,
        keep_default_na=False,
    )
    registry["istat_code"] = registry["istat_code"].astype(str).str.zfill(6)

    shard_requested = args.shard_index is not None or args.shard_count is not None
    if shard_requested and (args.shard_index is None or args.shard_count is None):
        parser.error("--shard-index and --shard-count must be supplied together")
    if args.istat_codes and shard_requested:
        parser.error("--istat-codes and sharding are mutually exclusive")

    if args.istat_codes:
        requested = {str(value).zfill(6) for value in args.istat_codes}
        registry = registry[registry["istat_code"].isin(requested)].copy()
    elif shard_requested:
        registry = deterministic_shard(
            registry,
            shard_index=args.shard_index,
            shard_count=args.shard_count,
        )

    status_path = Path(args.status_output)
    publications_path = Path(args.publications_output)
    session = make_session(retries=args.retries)

    publication_fields: list[str] | None = None
    counters = {
        "municipalities": 0,
        "found": 0,
        "not_observed": 0,
        "errors": 0,
        "publications": 0,
    }

    for municipality in registry.itertuples(index=False):
        counters["municipalities"] += 1
        retrieved_at = datetime.now(UTC).isoformat()

        if not municipality.ipa_code:
            append_row(
                status_path,
                status_row(
                    registry_row=municipality,
                    publications=[],
                    target_start_year=args.target_start_year,
                    retrieved_at=retrieved_at,
                    lookup_status="missing_ipa_code",
                    error="registry_has_no_ipa_code",
                ),
                STATUS_FIELDS,
            )
            counters["errors"] += 1
            continue

        try:
            raw_records, _ = fetch_publications_for_ipa(
                municipality.ipa_code,
                session=session,
                timeout=args.timeout,
                delay_seconds=args.delay,
            )
        except (PiaoApiError, requests.RequestException, OSError, ValueError) as exc:
            append_row(
                status_path,
                status_row(
                    registry_row=municipality,
                    publications=[],
                    target_start_year=args.target_start_year,
                    retrieved_at=retrieved_at,
                    lookup_status="error",
                    error=f"{type(exc).__name__}: {exc}",
                ),
                STATUS_FIELDS,
            )
            counters["errors"] += 1
            continue

        publications: list[dict[str, object]] = []
        for record in raw_records:
            publication = normalise_publication(record, retrieved_at=retrieved_at)
            publication = {
                "istat_code": municipality.istat_code,
                "municipality_name": municipality.name,
                **publication,
            }
            publications.append(publication)

            if publication_fields is None:
                publication_fields = [
                    *PUBLICATION_PREFIX_FIELDS,
                    *[
                        key
                        for key in publication
                        if key not in PUBLICATION_PREFIX_FIELDS
                    ],
                ]
            append_row(publications_path, publication, publication_fields)

        lookup_status = "found" if publications else "not_observed"
        counters[lookup_status] += 1
        counters["publications"] += len(publications)

        append_row(
            status_path,
            status_row(
                registry_row=municipality,
                publications=publications,
                target_start_year=args.target_start_year,
                retrieved_at=retrieved_at,
                lookup_status=lookup_status,
            ),
            STATUS_FIELDS,
        )

        print(
            json.dumps(
                {
                    "istat_code": municipality.istat_code,
                    "ipa_code": municipality.ipa_code,
                    "name": municipality.name,
                    "status": lookup_status,
                    "publications": len(publications),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

        if args.delay > 0:
            time.sleep(args.delay)

    print(json.dumps({"summary": counters}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
