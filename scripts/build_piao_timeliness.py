from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from segnali_locali_di_trasparenza.timeliness import (
    build_timeliness_table,
    national_timeliness_statistics,
    summarise_lag_distribution,
    summarise_timeliness_by_region,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="data/processed/municipalities.csv")
    parser.add_argument("--status", required=True)
    parser.add_argument("--publications", required=True)
    parser.add_argument("--output-dir", default="data/analysis")
    args = parser.parse_args()

    registry = pd.read_csv(args.registry, dtype=str, keep_default_na=False)
    status = pd.read_csv(args.status, dtype=str, keep_default_na=False)
    publications = pd.read_csv(args.publications, dtype=str, keep_default_na=False)

    ranking = build_timeliness_table(registry, status, publications)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ranking_path = output_dir / "piao_timeliness_ranking.csv"
    regional_path = output_dir / "piao_timeliness_by_region.csv"
    distribution_path = output_dir / "piao_timeliness_distribution.csv"
    summary_path = output_dir / "piao_timeliness_summary.json"

    regional = summarise_timeliness_by_region(ranking)
    distribution = summarise_lag_distribution(ranking)

    ranking.to_csv(ranking_path, index=False)
    regional.to_csv(regional_path, index=False)
    distribution.to_csv(distribution_path, index=False)

    lag = pd.to_numeric(ranking["approval_lag_days"], errors="coerce")
    valid = lag.notna()
    target_observed = ranking["timeliness_status"].isin(
        {"early", "on_deadline", "late", "target_present_approval_date_missing"}
    )
    missing_target = ranking["timeliness_status"].eq("target_not_observed")
    on_time = valid & lag.le(0)
    late = valid & lag.gt(0)

    summary = {
        "target_start_year": int(ranking["target_start_year"].iloc[0]),
        "snapshot_date": str(ranking["snapshot_date"].iloc[0]),
        "municipalities": len(ranking),
        "target_piao_observed": int(target_observed.sum()),
        "target_piao_with_approval_date": int(valid.sum()),
        "target_piao_on_or_before_deadline": int(on_time.sum()),
        "target_piao_late": int(late.sum()),
        "target_piao_approval_date_missing": int(
            ranking["timeliness_status"].eq(
                "target_present_approval_date_missing"
            ).sum()
        ),
        "target_piao_not_observed": int(missing_target.sum()),
        "approval_lag_days": national_timeliness_statistics(ranking),
        "deadline_rules": sorted(
            ranking[
                [
                    "deadline_scope",
                    "budget_deadline",
                    "expected_piao_deadline",
                    "deadline_legal_basis",
                ]
            ]
            .drop_duplicates()
            .to_dict(orient="records"),
            key=lambda item: item["expected_piao_deadline"],
        ),
        "outputs": {
            "ranking": str(ranking_path),
            "regional": str(regional_path),
            "distribution": str(distribution_path),
        },
    }

    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
