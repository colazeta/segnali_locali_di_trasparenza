from __future__ import annotations

import argparse
import glob
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="data/processed/municipalities.csv")
    parser.add_argument("--input-glob", default="data/shards/*.csv")
    parser.add_argument("--output", default="data/observations/piao_publications.csv")
    parser.add_argument("--latest-output", default="data/processed/municipalities_piao_latest.csv")
    parser.add_argument("--manifest", default="data/manifests/piao_snapshot.json")
    args = parser.parse_args()

    paths = [Path(item) for item in sorted(glob.glob(args.input_glob))]
    if not paths:
        raise FileNotFoundError(f"No PIAO shard files matched {args.input_glob!r}")

    observations = pd.concat(
        [pd.read_csv(path, dtype=str, keep_default_na=False) for path in paths],
        ignore_index=True,
    )
    registry = pd.read_csv(args.registry, dtype=str, keep_default_na=False)
    registry["istat_code"] = registry["istat_code"].astype(str).str.zfill(6)
    observations["istat_code"] = observations["istat_code"].astype(str).str.zfill(6)

    expected = set(registry["istat_code"])
    covered = set(observations["istat_code"])
    missing = sorted(expected - covered)
    unexpected = sorted(covered - expected)

    # Multiple rows per municipality are expected when historical PIAOs exist.
    # Node IDs, however, must be unique once blank absence rows are excluded.
    real = observations[observations["portal_node_id"].ne("")].copy()
    duplicate_node_ids = sorted(
        real.loc[real["portal_node_id"].duplicated(keep=False), "portal_node_id"].unique()
    )

    observations = observations.sort_values(
        ["istat_code", "reference_start_year", "portal_node_id"],
        ascending=[True, False, False],
    ).reset_index(drop=True)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    observations.to_csv(output, index=False)
    observations.to_json(
        output.with_suffix(".jsonl"),
        orient="records",
        lines=True,
        force_ascii=False,
    )

    def latest_record(group: pd.DataFrame) -> pd.Series:
        present = group[group["piao_present"].astype(str).str.lower().eq("true")].copy()
        if present.empty:
            row = group.iloc[0].copy()
            row["latest_reference_period"] = ""
            row["latest_approval_date"] = ""
            row["latest_portal_published_at"] = ""
            row["latest_portal_url"] = ""
            row["latest_pdf_url"] = ""
            return row
        present["_start"] = pd.to_numeric(present["reference_start_year"], errors="coerce")
        present = present.sort_values(
            ["_start", "approval_date", "portal_node_id"],
            ascending=[False, False, False],
        )
        row = present.iloc[0].copy()
        row["latest_reference_period"] = row["reference_period"]
        row["latest_approval_date"] = row["approval_date"]
        row["latest_portal_published_at"] = row["portal_published_at"]
        row["latest_portal_url"] = row["portal_url"]
        row["latest_pdf_url"] = row["pdf_url"]
        return row

    latest_rows = (
        observations.groupby("istat_code", sort=True, group_keys=False)
        .apply(latest_record, include_groups=False)
        .reset_index()
    )

    latest_keep = [
        "istat_code",
        "municipality_name",
        "registry_ipa_code",
        "piao_present",
        "latest_reference_period",
        "latest_approval_date",
        "latest_portal_published_at",
        "latest_portal_url",
        "latest_pdf_url",
    ]
    latest_output = Path(args.latest_output)
    latest_output.parent.mkdir(parents=True, exist_ok=True)
    latest_rows[latest_keep].to_csv(latest_output, index=False)

    present_by_municipality = (
        observations.groupby("istat_code")["piao_present"]
        .apply(lambda series: series.astype(str).str.lower().eq("true").any())
    )

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "municipalities_expected": len(expected),
        "municipalities_covered": len(covered),
        "municipalities_with_piao": int(present_by_municipality.sum()),
        "municipalities_without_portal_record": int((~present_by_municipality).sum()),
        "piao_records": len(real),
        "reference_period_counts": dict(Counter(real["reference_period"])),
        "missing_municipalities": missing,
        "unexpected_municipalities": unexpected,
        "duplicate_portal_node_ids": duplicate_node_ids,
        "outputs": {
            "all_publications": str(output),
            "all_publications_sha256": sha256_file(output),
            "latest_by_municipality": str(latest_output),
            "latest_by_municipality_sha256": sha256_file(latest_output),
        },
    }

    manifest_path = Path(args.manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))

    if missing or unexpected or duplicate_node_ids:
        raise SystemExit(
            "PIAO coverage validation failed: "
            f"missing={len(missing)}, unexpected={len(unexpected)}, "
            f"duplicate_nodes={len(duplicate_node_ids)}"
        )


if __name__ == "__main__":
    main()
