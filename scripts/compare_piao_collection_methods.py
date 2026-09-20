from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


STATUS_FIELDS = [
    "piao_present_on_portal",
    "publication_count",
    "period_starting_target_year_present",
    "period_starting_target_year_publication_count",
    "latest_reference_period",
    "latest_version",
    "latest_approval_date",
]


def read_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-status", required=True)
    parser.add_argument("--baseline-publications", required=True)
    parser.add_argument("--bulk-status", required=True)
    parser.add_argument("--bulk-publications", required=True)
    parser.add_argument("--output", default="data/piao-comparison.json")
    args = parser.parse_args()

    baseline_status = read_csv(args.baseline_status)
    bulk_status = read_csv(args.bulk_status)
    baseline_publications = read_csv(args.baseline_publications)
    bulk_publications = read_csv(args.bulk_publications)

    for frame in [baseline_status, bulk_status]:
        frame["istat_code"] = frame["istat_code"].astype(str).str.zfill(6)

    baseline_status = baseline_status.set_index("istat_code").sort_index()
    bulk_status = bulk_status.set_index("istat_code").sort_index()

    status_code_mismatch = sorted(
        set(baseline_status.index).symmetric_difference(set(bulk_status.index))
    )

    field_mismatches: dict[str, list[str]] = {}
    common_codes = baseline_status.index.intersection(bulk_status.index)
    for field in STATUS_FIELDS:
        if field not in baseline_status.columns or field not in bulk_status.columns:
            field_mismatches[field] = ["__missing_column__"]
            continue
        different = (
            baseline_status.loc[common_codes, field].astype(str)
            != bulk_status.loc[common_codes, field].astype(str)
        )
        field_mismatches[field] = common_codes[different].tolist()

    baseline_ids = set(baseline_publications["piao_publication_id"].astype(str))
    bulk_ids = set(bulk_publications["piao_publication_id"].astype(str))

    result = {
        "baseline_status_rows": len(baseline_status),
        "bulk_status_rows": len(bulk_status),
        "baseline_publication_rows": len(baseline_publications),
        "bulk_publication_rows": len(bulk_publications),
        "status_code_mismatch": status_code_mismatch,
        "field_mismatch_counts": {
            field: len(codes) for field, codes in field_mismatches.items()
        },
        "field_mismatch_examples": {
            field: codes[:25] for field, codes in field_mismatches.items() if codes
        },
        "publication_ids_only_in_baseline_count": len(baseline_ids - bulk_ids),
        "publication_ids_only_in_bulk_count": len(bulk_ids - baseline_ids),
        "publication_ids_only_in_baseline_examples": sorted(baseline_ids - bulk_ids)[:25],
        "publication_ids_only_in_bulk_examples": sorted(bulk_ids - baseline_ids)[:25],
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))

    mismatch_count = (
        len(status_code_mismatch)
        + sum(len(codes) for codes in field_mismatches.values())
        + len(baseline_ids - bulk_ids)
        + len(bulk_ids - baseline_ids)
    )
    if mismatch_count:
        raise SystemExit(f"PIAO collection parity check failed: {mismatch_count} mismatches")


if __name__ == "__main__":
    main()
