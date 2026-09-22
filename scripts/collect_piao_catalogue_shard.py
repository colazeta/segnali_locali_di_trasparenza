from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from segnali_locali_di_trasparenza.piao import (
    fetch_catalogue_page,
    make_session,
    normalise_publication,
    publication_id,
)


INDEX_FIELDS = [
    "page",
    "position",
    "record_fingerprint",
    "piao_publication_id",
    "ipa_code",
    "reference_label",
    "version",
]

PUBLICATION_PREFIX_FIELDS = [
    "istat_code",
    "municipality_name",
]


def record_fingerprint(record: dict[str, Any]) -> str:
    raw = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def append_rows(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        if not path.exists():
            path.write_text(",".join(fieldnames) + "\n", encoding="utf-8")
        return

    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="data/processed/municipalities.csv")
    parser.add_argument("--output-dir", default="data/piao-bulk-shards")
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--shard-count", type=int, required=True)
    parser.add_argument("--delay", type=float, default=1.00)
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--retries", type=int, default=2)
    args = parser.parse_args()

    if args.shard_count <= 0:
        raise ValueError("shard-count must be positive")
    if args.delay < 0:
        raise ValueError("delay must be non-negative")
    if args.shard_index < 0 or args.shard_index >= args.shard_count:
        raise ValueError("shard-index must be in [0, shard-count)")

    registry = pd.read_csv(args.registry, dtype=str, keep_default_na=False)
    registry["istat_code"] = registry["istat_code"].astype(str).str.zfill(6)
    registry["ipa_key"] = registry["ipa_code"].astype(str).str.casefold().str.strip()

    if registry["ipa_key"].eq("").any() or registry["ipa_key"].duplicated().any():
        raise ValueError("Registry must contain one unique non-empty IPA code per municipality")

    municipality_by_ipa = registry.set_index("ipa_key")
    municipality_ipa_codes = set(municipality_by_ipa.index)

    session = make_session(retries=args.retries)
    first_records, advertised_total, page_size = fetch_catalogue_page(
        0,
        session=session,
        timeout=args.timeout,
    )
    if page_size <= 0:
        raise RuntimeError("PIAO catalogue reported a non-positive page size")

    total_pages = math.ceil(advertised_total / page_size)
    pages = list(range(args.shard_index, total_pages, args.shard_count))
    retrieved_at = datetime.now(UTC).isoformat()

    output_dir = Path(args.output_dir)
    index_path = output_dir / f"catalogue-index-{args.shard_index:02d}.csv"
    publications_path = output_dir / f"publications-{args.shard_index:02d}.csv"
    manifest_path = output_dir / f"manifest-{args.shard_index:02d}.json"

    publication_fields: list[str] | None = None
    page_totals: set[int] = set()
    page_sizes: set[int] = set()
    pages_completed: list[int] = []
    catalogue_rows = 0
    selected_rows = 0

    for page in pages:
        if page == 0:
            records = first_records
            total = advertised_total
            count = page_size
        else:
            records, total, count = fetch_catalogue_page(
                page,
                session=session,
                timeout=args.timeout,
            )

        page_totals.add(total)
        page_sizes.add(count)

        index_rows: list[dict[str, object]] = []
        publication_rows: list[dict[str, object]] = []

        for position, record in enumerate(records):
            logical_id = publication_id(record)
            ipa_code = str(record.get("administrationIpaCode") or "").strip()
            index_rows.append(
                {
                    "page": page,
                    "position": position,
                    "record_fingerprint": record_fingerprint(record),
                    "piao_publication_id": logical_id,
                    "ipa_code": ipa_code,
                    "reference_label": str(record.get("years") or ""),
                    "version": record.get("version"),
                }
            )

            ipa_key = ipa_code.casefold()
            if ipa_key not in municipality_ipa_codes:
                continue

            municipality = municipality_by_ipa.loc[ipa_key]
            publication = normalise_publication(record, retrieved_at=retrieved_at)
            publication = {
                "istat_code": str(municipality["istat_code"]).zfill(6),
                "municipality_name": municipality["name"],
                **publication,
            }
            publication_rows.append(publication)

            if publication_fields is None:
                publication_fields = [
                    *PUBLICATION_PREFIX_FIELDS,
                    *[
                        key
                        for key in publication
                        if key not in PUBLICATION_PREFIX_FIELDS
                    ],
                ]

        append_rows(index_path, index_rows, INDEX_FIELDS)
        if publication_fields is not None:
            append_rows(publications_path, publication_rows, publication_fields)

        catalogue_rows += len(index_rows)
        selected_rows += len(publication_rows)
        pages_completed.append(page)

        if args.delay > 0:
            time.sleep(args.delay)

    if publication_fields is None and not publications_path.exists():
        publications_path.write_text("", encoding="utf-8")

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "advertised_total_at_start": advertised_total,
        "page_size_at_start": page_size,
        "total_pages": total_pages,
        "assigned_page_count": len(pages),
        "pages_completed": pages_completed,
        "observed_totals": sorted(page_totals),
        "observed_page_sizes": sorted(page_sizes),
        "catalogue_rows": catalogue_rows,
        "municipal_publication_rows": selected_rows,
        "outputs": {
            "catalogue_index": str(index_path),
            "publications": str(publications_path),
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
