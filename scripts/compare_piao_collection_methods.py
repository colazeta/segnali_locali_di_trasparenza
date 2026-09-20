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


def canonicalise_publications(
    publications: pd.DataFrame,
    registry: pd.DataFrame,
) -> tuple[pd.DataFrame, int, int]:
    """Filter and remap publications using the record's exact returned IPA code."""
    registry = registry.copy()
    registry["istat_code"] = registry["istat_code"].astype(str).str.zfill(6)
    registry["ipa_key"] = registry["ipa_code"].astype(str).str.casefold().str.strip()

    if registry["ipa_key"].eq("").any() or registry["ipa_key"].duplicated().any():
        raise ValueError("Registry must contain one unique non-empty IPA code per municipality")

    mapping = registry.set_index("ipa_key")[["istat_code", "name"]]
    publications = publications.copy()
    publications["ipa_key"] = publications["ipa_code"].astype(str).str.casefold().str.strip()

    municipal = publications[publications["ipa_key"].isin(mapping.index)].copy()
    filtered_out = len(publications) - len(municipal)

    municipal["istat_code"] = municipal["ipa_key"].map(mapping["istat_code"])
    municipal["municipality_name"] = municipal["ipa_key"].map(mapping["name"])

    before = len(municipal)
    municipal = municipal.drop_duplicates("piao_publication_id", keep="last")
    logical_duplicates_removed = before - len(municipal)

    return (
        municipal.drop(columns=["ipa_key"]).reset_index(drop=True),
        filtered_out,
        logical_duplicates_removed,
    )


def status_from_publications(
    registry: pd.DataFrame,
    publications: pd.DataFrame,
    *,
    target_start_year: int,
) -> pd.DataFrame:
    registry = registry.copy()
    registry["istat_code"] = registry["istat_code"].astype(str).str.zfill(6)

    out = registry[["istat_code"]].copy()
    out["piao_present_on_portal"] = "False"
    out["publication_count"] = "0"
    out["period_starting_target_year_present"] = "False"
    out["period_starting_target_year_publication_count"] = "0"
    out["latest_reference_period"] = ""
    out["latest_version"] = ""
    out["latest_approval_date"] = ""

    if publications.empty:
        return out.set_index("istat_code").sort_index()

    working = publications.copy()
    working["istat_code"] = working["istat_code"].astype(str).str.zfill(6)
    working["_start"] = pd.to_numeric(
        working["reference_start_year"], errors="coerce"
    ).fillna(-1)
    working["_version"] = pd.to_numeric(working["version"], errors="coerce").fillna(-1)
    working["_approval"] = pd.to_datetime(working["approval_date"], errors="coerce")

    counts = working.groupby("istat_code").size()
    target_counts = (
        working.loc[working["_start"].eq(target_start_year)]
        .groupby("istat_code")
        .size()
    )
    latest = (
        working.sort_values(
            ["istat_code", "_start", "_version", "_approval"],
            ascending=[True, False, False, False],
            kind="stable",
        )
        .drop_duplicates("istat_code", keep="first")
        .set_index("istat_code")
    )

    out["publication_count"] = out["istat_code"].map(counts).fillna(0).astype(int).astype(str)
    out["piao_present_on_portal"] = (
        out["publication_count"].astype(int).gt(0).astype(str)
    )
    target_count = out["istat_code"].map(target_counts).fillna(0).astype(int)
    out["period_starting_target_year_publication_count"] = target_count.astype(str)
    out["period_starting_target_year_present"] = target_count.gt(0).astype(str)
    out["latest_reference_period"] = out["istat_code"].map(
        latest["reference_period"]
    ).fillna("")
    out["latest_version"] = out["istat_code"].map(latest["version"]).fillna("")
    out["latest_approval_date"] = out["istat_code"].map(
        latest["approval_date"]
    ).fillna("")

    return out.set_index("istat_code").sort_index()


def normalise_bulk_status(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["istat_code"] = frame["istat_code"].astype(str).str.zfill(6)

    legacy_names = {
        "current_reference_year": "target_start_year",
        "current_period_present": "period_starting_target_year_present",
        "current_period_publication_count": (
            "period_starting_target_year_publication_count"
        ),
    }
    frame = frame.rename(
        columns={
            old: new
            for old, new in legacy_names.items()
            if old in frame.columns and new not in frame.columns
        }
    )

    for field in [
        "piao_present_on_portal",
        "period_starting_target_year_present",
    ]:
        if field in frame.columns:
            frame[field] = frame[field].astype(str).str.capitalize()

    return frame.set_index("istat_code").sort_index()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True)
    parser.add_argument("--baseline-publications", required=True)
    parser.add_argument("--bulk-status", required=True)
    parser.add_argument("--bulk-publications", required=True)
    parser.add_argument("--target-start-year", type=int, default=2026)
    parser.add_argument("--output", default="data/piao-comparison.json")
    args = parser.parse_args()

    registry = read_csv(args.registry)
    baseline_publications_raw = read_csv(args.baseline_publications)
    bulk_publications_raw = read_csv(args.bulk_publications)
    bulk_status = normalise_bulk_status(read_csv(args.bulk_status))

    baseline_publications, baseline_filtered_out, baseline_duplicates = (
        canonicalise_publications(baseline_publications_raw, registry)
    )
    bulk_publications, bulk_filtered_out, bulk_duplicates = canonicalise_publications(
        bulk_publications_raw,
        registry,
    )

    expected_status = status_from_publications(
        registry,
        baseline_publications,
        target_start_year=args.target_start_year,
    )

    status_code_mismatch = sorted(
        set(expected_status.index).symmetric_difference(set(bulk_status.index))
    )

    field_mismatches: dict[str, list[str]] = {}
    common_codes = expected_status.index.intersection(bulk_status.index)
    for field in STATUS_FIELDS:
        if field not in bulk_status.columns:
            field_mismatches[field] = ["__missing_column__"]
            continue

        left = expected_status.loc[common_codes, field].astype(str)
        right = bulk_status.loc[common_codes, field].astype(str)
        different = left != right
        field_mismatches[field] = common_codes[different].tolist()

    baseline_ids = set(baseline_publications["piao_publication_id"].astype(str))
    bulk_ids = set(bulk_publications["piao_publication_id"].astype(str))

    result = {
        "target_start_year": args.target_start_year,
        "registry_rows": len(registry),
        "baseline_raw_publication_rows": len(baseline_publications_raw),
        "baseline_canonical_publication_rows": len(baseline_publications),
        "baseline_nonmunicipal_prefix_matches_removed": baseline_filtered_out,
        "baseline_logical_duplicates_removed": baseline_duplicates,
        "bulk_raw_publication_rows": len(bulk_publications_raw),
        "bulk_canonical_publication_rows": len(bulk_publications),
        "bulk_nonmunicipal_rows_removed": bulk_filtered_out,
        "bulk_logical_duplicates_removed": bulk_duplicates,
        "bulk_status_rows": len(bulk_status),
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
