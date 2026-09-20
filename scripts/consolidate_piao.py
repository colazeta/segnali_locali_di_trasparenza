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


def read_many(pattern: str) -> pd.DataFrame:
    paths = [Path(path) for path in sorted(glob.glob(pattern))]
    if not paths:
        return pd.DataFrame()
    return pd.concat(
        [pd.read_csv(path, dtype=str, keep_default_na=False) for path in paths],
        ignore_index=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="data/processed/municipalities.csv")
    parser.add_argument("--status-glob", default="data/piao-shards/status-*.csv")
    parser.add_argument(
        "--publications-glob",
        default="data/piao-shards/publications-*.csv",
    )
    parser.add_argument("--output-dir", default="data/processed")
    parser.add_argument(
        "--manifest",
        default="data/manifests/piao_snapshot.json",
    )
    args = parser.parse_args()

    registry = pd.read_csv(
        args.registry,
        dtype=str,
        keep_default_na=False,
    )
    registry["istat_code"] = registry["istat_code"].astype(str).str.zfill(6)

    status = read_many(args.status_glob)
    if status.empty:
        raise FileNotFoundError(f"No PIAO status files matched {args.status_glob!r}")
    status["istat_code"] = status["istat_code"].astype(str).str.zfill(6)

    publications = read_many(args.publications_glob)
    if not publications.empty:
        publications["istat_code"] = publications["istat_code"].astype(str).str.zfill(6)

    expected = set(registry["istat_code"])
    observed = set(status["istat_code"])
    duplicate_status = sorted(
        status.loc[status["istat_code"].duplicated(keep=False), "istat_code"].unique()
    )
    missing = sorted(expected - observed)
    unexpected = sorted(observed - expected)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    status_path = output_dir / "piao_status.csv"
    publications_path = output_dir / "piao_publications.csv"
    publications_jsonl_path = output_dir / "piao_publications.jsonl"

    status = status.sort_values(["istat_code"]).reset_index(drop=True)
    status.to_csv(status_path, index=False)

    if publications.empty:
        publications = pd.DataFrame()
        publications_path.write_text("", encoding="utf-8")
        publications_jsonl_path.write_text("", encoding="utf-8")
    else:
        duplicate_publication_ids = int(
            publications["piao_publication_id"].duplicated().sum()
        )
        if duplicate_publication_ids:
            publications = publications.drop_duplicates(
                subset=["piao_publication_id"],
                keep="last",
            )
        publications = publications.sort_values(
            [
                "istat_code",
                "reference_start_year",
                "version",
                "approval_date",
            ],
            kind="stable",
        ).reset_index(drop=True)
        publications.to_csv(publications_path, index=False)
        publications.to_json(
            publications_jsonl_path,
            orient="records",
            lines=True,
            force_ascii=False,
        )

    status_counts = Counter(status["lookup_status"])
    found = status[status["lookup_status"].eq("found")]
    current_present = status[
        status["period_starting_target_year_present"].astype(str).str.lower().eq("true")
    ]

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "municipality_registry_rows": len(registry),
        "municipality_status_rows": len(status),
        "publication_rows": len(publications),
        "municipalities_with_any_piao": len(found),
        "municipalities_with_period_starting_target_year_piao": len(current_present),
        "status_counts": dict(status_counts),
        "coverage": {
            "duplicate_status_codes": duplicate_status,
            "missing_status_codes": missing,
            "unexpected_status_codes": unexpected,
        },
        "publication_date_note": (
            "The public Portale PIAO API does not expose the date on which a "
            "record was published to the portal. approval_date is kept separate "
            "and must not be interpreted as portal publication date."
        ),
        "outputs": {
            "status_csv": str(status_path),
            "status_csv_sha256": sha256_file(status_path),
            "publications_csv": str(publications_path),
            "publications_csv_sha256": sha256_file(publications_path),
            "publications_jsonl": str(publications_jsonl_path),
            "publications_jsonl_sha256": sha256_file(publications_jsonl_path),
        },
    }

    manifest_path = Path(args.manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))

    if duplicate_status or missing or unexpected:
        raise SystemExit(
            "PIAO municipality coverage validation failed: "
            f"duplicates={len(duplicate_status)}, "
            f"missing={len(missing)}, unexpected={len(unexpected)}"
        )


if __name__ == "__main__":
    main()
