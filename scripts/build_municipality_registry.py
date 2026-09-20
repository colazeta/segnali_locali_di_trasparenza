from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from segnali_locali_di_trasparenza.registry import (
    IPA_URL,
    ISTAT_URL,
    download,
    link_ipa,
    read_ipa,
    read_istat,
    validate_registry,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data", help="Root data directory")
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Use already-downloaded source files in data/raw",
    )
    args = parser.parse_args()

    root = Path(args.data_dir)
    raw_dir = root / "raw"
    processed_dir = root / "processed"
    manifest_dir = root / "manifests"

    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)

    istat_path = raw_dir / "istat_comuni.xlsx"
    ipa_path = raw_dir / "ipa_enti.xlsx"

    source_hashes: dict[str, str] = {}
    if not args.no_download:
        source_hashes["istat_sha256"] = download(ISTAT_URL, istat_path)
        source_hashes["ipa_sha256"] = download(IPA_URL, ipa_path)

    if not istat_path.exists() or not ipa_path.exists():
        raise FileNotFoundError(
            "Missing source files. Run without --no-download or provide both files in data/raw."
        )

    istat = read_istat(istat_path)
    ipa = read_ipa(ipa_path)
    registry = link_ipa(istat, ipa)
    metrics = validate_registry(registry)

    registry = registry.sort_values(["region_code", "supra_code", "istat_code"]).reset_index(
        drop=True
    )

    csv_path = processed_dir / "municipalities.csv"
    jsonl_path = processed_dir / "municipalities.jsonl"
    registry.to_csv(csv_path, index=False)
    registry.to_json(jsonl_path, orient="records", lines=True, force_ascii=False)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "istat": ISTAT_URL,
            "ipa": IPA_URL,
        },
        "source_hashes": source_hashes,
        "metrics": metrics,
        "outputs": {
            "csv": str(csv_path),
            "jsonl": str(jsonl_path),
        },
    }
    (manifest_dir / "municipality_registry.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
