from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from segnali_locali_di_trasparenza.piao import (
    PORTAL_INDEX_URL,
    PortalClient,
    build_municipality_piao_view,
    discover_plan_urls,
    fetch_records,
    link_plans_to_municipalities,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="data/processed/municipalities.csv")
    parser.add_argument("--output-dir", default="data/piao")
    parser.add_argument("--node-url", action="append", default=[])
    parser.add_argument("--max-pages", type=int, default=2000)
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument("--delay", type=float, default=0.25)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument(
        "--require-index-discovery",
        action="store_true",
        help="Fail if the public PIAO index yields no plan-node URLs.",
    )
    args = parser.parse_args()

    registry = pd.read_csv(args.registry, dtype=str, keep_default_na=False)
    registry["istat_code"] = registry["istat_code"].astype(str).str.zfill(6)

    client = PortalClient(
        timeout_seconds=args.timeout,
        delay_seconds=args.delay,
        retry_total=args.retries,
    )

    explicit_urls = list(dict.fromkeys(args.node_url))
    discovered_urls: list[str] = []
    if not explicit_urls or args.require_index_discovery:
        discovered_urls = discover_plan_urls(client, max_pages=args.max_pages)
        if args.require_index_discovery and not discovered_urls:
            raise RuntimeError(
                f"No PIAO nodes discovered from public index {PORTAL_INDEX_URL}"
            )

    urls = list(dict.fromkeys([*explicit_urls, *discovered_urls]))
    if not urls:
        raise RuntimeError("No PIAO node URLs available for collection")

    records = fetch_records(client, urls)
    records_frame = pd.DataFrame([record.to_dict() for record in records])
    if records_frame.empty:
        raise RuntimeError("No PIAO records parsed from the selected URLs")

    linked = link_plans_to_municipalities(records_frame, registry)
    municipalities = build_municipality_piao_view(linked, registry)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    plans_csv = output_dir / "piao_plans.csv"
    plans_jsonl = output_dir / "piao_plans.jsonl"
    municipalities_csv = output_dir / "municipalities_piao.csv"
    unmatched_csv = output_dir / "piao_unmatched.csv"
    manifest_path = output_dir / "manifest.json"

    linked.sort_values(
        ["istat_code", "period_start_year", "approval_date", "portal_node_id"],
        na_position="last",
    ).to_csv(plans_csv, index=False)
    linked.to_json(
        plans_jsonl,
        orient="records",
        lines=True,
        force_ascii=False,
    )
    municipalities.sort_values("istat_code").to_csv(municipalities_csv, index=False)

    unmatched = linked[linked["istat_code"].astype(str).eq("")].copy()
    unmatched.to_csv(unmatched_csv, index=False)

    matched_plans = int(linked["istat_code"].astype(str).ne("").sum())
    municipalities_with_any = int(municipalities["piao_present_any"].sum())

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source": PORTAL_INDEX_URL,
        "registry_municipalities": len(registry),
        "node_urls_requested": len(urls),
        "plan_records_parsed": len(linked),
        "plan_records_matched_to_municipalities": matched_plans,
        "plan_records_unmatched": len(unmatched),
        "municipalities_with_any_piao": municipalities_with_any,
        "municipalities_without_observed_piao": len(registry) - municipalities_with_any,
        "periods": sorted(
            {
                str(value)
                for value in linked["period_label"].dropna().astype(str)
                if str(value).strip()
            }
        ),
        "outputs": {
            "plans_csv": str(plans_csv),
            "plans_csv_sha256": sha256_file(plans_csv),
            "plans_jsonl": str(plans_jsonl),
            "plans_jsonl_sha256": sha256_file(plans_jsonl),
            "municipalities_csv": str(municipalities_csv),
            "municipalities_csv_sha256": sha256_file(municipalities_csv),
            "unmatched_csv": str(unmatched_csv),
            "unmatched_csv_sha256": sha256_file(unmatched_csv),
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
