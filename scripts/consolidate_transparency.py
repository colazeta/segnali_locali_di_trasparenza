from __future__ import annotations

import argparse
import glob
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = {
    "istat_code",
    "ipa_code",
    "status",
    "observed_at",
    "collector",
    "collector_version",
    "methodology_version",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="data/processed/municipalities.csv")
    parser.add_argument(
        "--input-glob",
        default="data/shards/*.csv",
        help="Glob matching completed shard observation CSV files",
    )
    parser.add_argument(
        "--output",
        default="data/observations/transparency_snapshot.csv",
    )
    parser.add_argument(
        "--manifest",
        default="data/manifests/transparency_snapshot.json",
    )
    args = parser.parse_args()

    shard_paths = [Path(path) for path in sorted(glob.glob(args.input_glob))]
    if not shard_paths:
        raise FileNotFoundError(f"No shard files matched: {args.input_glob}")

    frames = [pd.read_csv(path, dtype=str).fillna("") for path in shard_paths]
    observations = pd.concat(frames, ignore_index=True)

    missing_columns = REQUIRED_COLUMNS - set(observations.columns)
    if missing_columns:
        raise ValueError(f"Observation shards missing columns: {sorted(missing_columns)}")

    registry = pd.read_csv(args.registry, dtype=str).fillna("")
    registry["istat_code"] = registry["istat_code"].astype(str).str.zfill(6)
    observations["istat_code"] = observations["istat_code"].astype(str).str.zfill(6)

    expected = set(registry["istat_code"])
    observed = set(observations["istat_code"])
    duplicate_codes = sorted(
        observations.loc[
            observations["istat_code"].duplicated(keep=False),
            "istat_code",
        ].unique()
    )
    missing_codes = sorted(expected - observed)
    unexpected_codes = sorted(observed - expected)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    observations = observations.sort_values("istat_code").reset_index(drop=True)
    observations.to_csv(output_path, index=False)

    jsonl_path = output_path.with_suffix(".jsonl")
    observations.to_json(
        jsonl_path,
        orient="records",
        lines=True,
        force_ascii=False,
    )

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "registry_rows": len(registry),
        "observation_rows": len(observations),
        "unique_observed_municipalities": len(observed),
        "shard_files": [str(path) for path in shard_paths],
        "status_counts": dict(Counter(observations["status"])),
        "collector_versions": sorted(set(observations["collector_version"])),
        "methodology_versions": sorted(set(observations["methodology_version"])),
        "duplicate_codes": duplicate_codes,
        "missing_codes": missing_codes,
        "unexpected_codes": unexpected_codes,
        "outputs": {
            "csv": str(output_path),
            "csv_sha256": sha256_file(output_path),
            "jsonl": str(jsonl_path),
            "jsonl_sha256": sha256_file(jsonl_path),
        },
    }

    manifest_path = Path(args.manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(manifest, ensure_ascii=False, indent=2))

    if duplicate_codes or missing_codes or unexpected_codes:
        raise SystemExit(
            "Coverage validation failed: "
            f"duplicates={len(duplicate_codes)}, "
            f"missing={len(missing_codes)}, "
            f"unexpected={len(unexpected_codes)}"
        )


if __name__ == "__main__":
    main()
