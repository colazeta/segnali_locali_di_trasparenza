from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from segnali_locali_di_trasparenza.piao import (
    fetch_public_catalogue,
    normalise_publication,
)


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


def build_publications(
    raw_records: list[dict[str, object]],
    registry: pd.DataFrame,
    *,
    retrieved_at: str,
) -> pd.DataFrame:
    registry = registry.copy()
    registry["ipa_key"] = registry["ipa_code"].astype(str).str.casefold().str.strip()

    duplicated_ipa = registry.loc[
        registry["ipa_key"].ne("") & registry["ipa_key"].duplicated(keep=False),
        "ipa_key",
    ].unique()
    if len(duplicated_ipa):
        raise ValueError(
            "Municipality registry contains duplicate IPA codes: "
            f"{sorted(duplicated_ipa)[:20]}"
        )

    by_ipa = registry.set_index("ipa_key")
    rows: list[dict[str, object]] = []

    for record in raw_records:
        publication = normalise_publication(record, retrieved_at=retrieved_at)
        ipa_key = str(publication["ipa_code"]).casefold().strip()
        if ipa_key not in by_ipa.index:
            continue

        municipality = by_ipa.loc[ipa_key]
        rows.append(
            {
                "istat_code": str(municipality["istat_code"]).zfill(6),
                "municipality_name": municipality["name"],
                **publication,
            }
        )

    if not rows:
        return pd.DataFrame()

    frame = pd.DataFrame(rows)
    duplicated_ids = frame["piao_publication_id"].duplicated(keep=False)
    if duplicated_ids.any():
        frame = frame.drop_duplicates("piao_publication_id", keep="last")

    return frame.sort_values(
        ["istat_code", "reference_start_year", "version", "approval_date"],
        kind="stable",
    ).reset_index(drop=True)


def build_status(
    registry: pd.DataFrame,
    publications: pd.DataFrame,
    *,
    target_start_year: int,
    retrieved_at: str,
) -> pd.DataFrame:
    out = registry[
        ["istat_code", "name", "ipa_code", "region_name", "supra_name"]
    ].copy()
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
    parser.add_argument("--output-dir", default="data/piao-bulk")
    parser.add_argument(
        "--target-start-year",
        type=int,
        default=datetime.now(UTC).year,
    )
    parser.add_argument("--delay", type=float, default=0.15)
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--max-pages", type=int, default=10000)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    registry = pd.read_csv(
        args.registry,
        dtype=str,
        keep_default_na=False,
    )
    registry["istat_code"] = registry["istat_code"].astype(str).str.zfill(6)

    ipa_codes = {
        value.casefold().strip()
        for value in registry["ipa_code"].astype(str)
        if value.strip()
    }
    if len(ipa_codes) != len(registry):
        raise ValueError(
            "Bulk PIAO collection requires one non-empty, unique IPA code per municipality"
        )

    started_at = datetime.now(UTC).isoformat()
    raw_records, catalogue = fetch_public_catalogue(
        timeout=args.timeout,
        delay_seconds=args.delay,
        max_pages=args.max_pages,
        keep_ipa_codes=ipa_codes,
        workers=args.workers,
        retries=args.retries,
    )
    retrieved_at = datetime.now(UTC).isoformat()

    publications = build_publications(
        raw_records,
        registry,
        retrieved_at=retrieved_at,
    )
    status = build_status(
        registry,
        publications,
        target_start_year=args.target_start_year,
        retrieved_at=retrieved_at,
    )

    if len(status) != len(registry):
        raise ValueError(
            f"Municipality status coverage mismatch: {len(status)} != {len(registry)}"
        )
    if status["istat_code"].duplicated().any():
        raise ValueError("Municipality status contains duplicate ISTAT codes")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    status_path = output_dir / "piao_status.csv"
    publications_path = output_dir / "piao_publications.csv"
    publications_jsonl_path = output_dir / "piao_publications.jsonl"
    manifest_path = output_dir / "manifest.json"

    status.to_csv(status_path, index=False)
    if publications.empty:
        publications_path.write_text("", encoding="utf-8")
        publications_jsonl_path.write_text("", encoding="utf-8")
    else:
        publications.to_csv(publications_path, index=False)
        publications.to_json(
            publications_jsonl_path,
            orient="records",
            lines=True,
            force_ascii=False,
        )

    manifest = {
        "started_at": started_at,
        "completed_at": retrieved_at,
        "target_start_year": args.target_start_year,
        "municipality_registry_rows": len(registry),
        "municipality_status_rows": len(status),
        "municipal_publication_rows": len(publications),
        "municipalities_with_any_piao": int(
            status["piao_present_on_portal"].sum()
        ),
        "municipalities_with_period_starting_target_year_piao": int(
            status["period_starting_target_year_present"].sum()
        ),
        "catalogue": catalogue,
        "publication_date_note": (
            "The public Portale PIAO API does not expose a historical portal "
            "publication timestamp. approval_date and retrieved_at remain separate."
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
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
