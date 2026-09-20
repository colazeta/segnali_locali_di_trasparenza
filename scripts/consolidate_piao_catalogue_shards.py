from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


STATUS_COLUMNS = [
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_many(pattern: str) -> pd.DataFrame:
    paths = [Path(path) for path in sorted(glob.glob(pattern))]
    frames = [
        pd.read_csv(path, dtype=str, keep_default_na=False)
        for path in paths
        if path.exists() and path.stat().st_size > 0
    ]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def build_status(
    registry: pd.DataFrame,
    publications: pd.DataFrame,
    *,
    target_start_year: int,
    retrieved_at: str,
) -> pd.DataFrame:
    out = registry[["istat_code", "name", "ipa_code"]].copy()
    out["istat_code"] = out["istat_code"].astype(str).str.zfill(6)
    out = out.rename(columns={"name": "municipality_name"})

    out["lookup_status"] = "not_observed"
    out["piao_present_on_portal"] = False
    out["publication_count"] = 0
    out["target_start_year"] = target_start_year
    out["period_starting_target_year_present"] = False
    out["period_starting_target_year_publication_count"] = 0
    out["latest_reference_period"] = ""
    out["latest_reference_start_year"] = ""
    out["latest_reference_end_year"] = ""
    out["latest_version"] = ""
    out["latest_approval_date"] = ""
    out["latest_piao_document_url"] = ""
    out["portal_publication_date_status"] = ""
    out["retrieved_at"] = retrieved_at
    out["error"] = ""

    if publications.empty:
        return out[STATUS_COLUMNS]

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

    out["publication_count"] = out["istat_code"].map(counts).fillna(0).astype(int)
    out["piao_present_on_portal"] = out["publication_count"].gt(0)
    out["lookup_status"] = out["piao_present_on_portal"].map(
        {True: "found", False: "not_observed"}
    )
    out["period_starting_target_year_publication_count"] = (
        out["istat_code"].map(target_counts).fillna(0).astype(int)
    )
    out["period_starting_target_year_present"] = out[
        "period_starting_target_year_publication_count"
    ].gt(0)

    mapping = {
        "latest_reference_period": "reference_period",
        "latest_reference_start_year": "reference_start_year",
        "latest_reference_end_year": "reference_end_year",
        "latest_version": "version",
        "latest_approval_date": "approval_date",
        "latest_piao_document_url": "piao_document_url",
    }
    for target, source in mapping.items():
        out[target] = out["istat_code"].map(latest[source]).fillna("")

    out.loc[
        out["piao_present_on_portal"], "portal_publication_date_status"
    ] = "not_exposed_by_public_api"

    return out[STATUS_COLUMNS]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="data/processed/municipalities.csv")
    parser.add_argument(
        "--index-glob",
        default="data/piao-bulk-shards/catalogue-index-*.csv",
    )
    parser.add_argument(
        "--publications-glob",
        default="data/piao-bulk-shards/publications-*.csv",
    )
    parser.add_argument(
        "--manifest-glob",
        default="data/piao-bulk-shards/manifest-*.json",
    )
    parser.add_argument("--output-dir", default="data/piao-bulk-national")
    parser.add_argument("--expected-shards", type=int, default=40)
    parser.add_argument("--target-start-year", type=int, default=2026)
    args = parser.parse_args()

    registry = pd.read_csv(args.registry, dtype=str, keep_default_na=False)
    registry["istat_code"] = registry["istat_code"].astype(str).str.zfill(6)

    manifest_paths = [Path(path) for path in sorted(glob.glob(args.manifest_glob))]
    if len(manifest_paths) != args.expected_shards:
        raise RuntimeError(
            f"Expected {args.expected_shards} shard manifests, found {len(manifest_paths)}"
        )
    manifests = [
        json.loads(path.read_text(encoding="utf-8")) for path in manifest_paths
    ]

    shard_indexes = sorted(int(item["shard_index"]) for item in manifests)
    if shard_indexes != list(range(args.expected_shards)):
        raise RuntimeError(f"Shard index coverage mismatch: {shard_indexes}")

    advertised_totals = {
        int(item["advertised_total_at_start"]) for item in manifests
    }
    page_sizes = {int(item["page_size_at_start"]) for item in manifests}
    total_pages_values = {int(item["total_pages"]) for item in manifests}
    observed_totals = {
        int(value)
        for item in manifests
        for value in item.get("observed_totals", [])
    }

    if len(advertised_totals) != 1 or len(page_sizes) != 1 or len(total_pages_values) != 1:
        raise RuntimeError(
            "Catalogue metadata drift across shards: "
            f"totals={sorted(advertised_totals)}, "
            f"page_sizes={sorted(page_sizes)}, pages={sorted(total_pages_values)}"
        )
    if observed_totals != advertised_totals:
        raise RuntimeError(
            "Catalogue total changed while collecting: "
            f"start={sorted(advertised_totals)}, observed={sorted(observed_totals)}"
        )

    advertised_total = next(iter(advertised_totals))
    page_size = next(iter(page_sizes))
    total_pages = next(iter(total_pages_values))
    expected_total_pages = math.ceil(advertised_total / page_size)
    if total_pages != expected_total_pages:
        raise RuntimeError(
            f"Total page calculation mismatch: {total_pages} != {expected_total_pages}"
        )

    index = read_many(args.index_glob)
    if index.empty:
        raise RuntimeError("No catalogue index rows collected")
    index["page"] = pd.to_numeric(index["page"], errors="raise").astype(int)
    index["position"] = pd.to_numeric(index["position"], errors="raise").astype(int)

    pages = sorted(index["page"].unique().tolist())
    expected_pages = list(range(total_pages))
    missing_pages = sorted(set(expected_pages) - set(pages))
    unexpected_pages = sorted(set(pages) - set(expected_pages))
    duplicate_positions = int(index.duplicated(["page", "position"]).sum())
    duplicate_fingerprints = int(index["record_fingerprint"].duplicated().sum())

    if missing_pages or unexpected_pages or duplicate_positions:
        raise RuntimeError(
            "Catalogue page coverage failed: "
            f"missing_pages={len(missing_pages)}, "
            f"unexpected_pages={len(unexpected_pages)}, "
            f"duplicate_positions={duplicate_positions}"
        )
    if len(index) != advertised_total:
        raise RuntimeError(
            f"Catalogue row count mismatch: {len(index)} != {advertised_total}"
        )
    if duplicate_fingerprints:
        raise RuntimeError(
            f"Catalogue contains {duplicate_fingerprints} duplicate record fingerprints; "
            "rerun to rule out pagination drift before accepting the snapshot."
        )

    publications = read_many(args.publications_glob)
    if publications.empty:
        raise RuntimeError("No municipal PIAO publications selected from catalogue")

    publications["istat_code"] = publications["istat_code"].astype(str).str.zfill(6)
    logical_duplicates = int(
        publications["piao_publication_id"].duplicated(keep=False).sum()
    )
    if logical_duplicates:
        publications = publications.drop_duplicates(
            "piao_publication_id", keep="last"
        )

    retrieved_at = max(
        str(item.get("generated_at") or "") for item in manifests
    )
    status = build_status(
        registry,
        publications,
        target_start_year=args.target_start_year,
        retrieved_at=retrieved_at,
    )

    if len(status) != len(registry):
        raise RuntimeError(
            f"Municipality coverage mismatch: {len(status)} != {len(registry)}"
        )
    if status["istat_code"].duplicated().any():
        raise RuntimeError("Municipality status contains duplicate ISTAT codes")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    status_path = output_dir / "piao_status.csv"
    publications_path = output_dir / "piao_publications.csv"
    publications_jsonl_path = output_dir / "piao_publications.jsonl"
    manifest_path = output_dir / "manifest.json"

    status.sort_values("istat_code").to_csv(status_path, index=False)
    publications = publications.sort_values(
        ["istat_code", "reference_start_year", "version", "approval_date"],
        kind="stable",
    ).reset_index(drop=True)
    publications.to_csv(publications_path, index=False)
    publications.to_json(
        publications_jsonl_path,
        orient="records",
        lines=True,
        force_ascii=False,
    )

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "target_start_year": args.target_start_year,
        "catalogue_advertised_total": advertised_total,
        "catalogue_page_size": page_size,
        "catalogue_total_pages": total_pages,
        "catalogue_rows_collected": len(index),
        "catalogue_unique_record_fingerprints": int(index["record_fingerprint"].nunique()),
        "municipality_registry_rows": len(registry),
        "municipality_status_rows": len(status),
        "municipal_publication_rows": len(publications),
        "municipalities_with_any_piao": int(
            status["piao_present_on_portal"].sum()
        ),
        "municipalities_with_period_starting_target_year_piao": int(
            status["period_starting_target_year_present"].sum()
        ),
        "logical_duplicate_publication_rows_removed": logical_duplicates,
        "coverage": {
            "missing_pages": missing_pages,
            "unexpected_pages": unexpected_pages,
            "duplicate_page_positions": duplicate_positions,
            "duplicate_record_fingerprints": duplicate_fingerprints,
        },
        "outputs": {
            "status_csv": str(status_path),
            "status_csv_sha256": sha256_file(status_path),
            "publications_csv": str(publications_path),
            "publications_csv_sha256": sha256_file(publications_path),
            "publications_jsonl": str(publications_jsonl_path),
            "publications_jsonl_sha256": sha256_file(publications_jsonl_path),
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
