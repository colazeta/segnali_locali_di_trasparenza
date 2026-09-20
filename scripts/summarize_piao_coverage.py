from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def as_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.casefold().isin({"true", "1", "yes", "sì", "si"})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="data/processed/municipalities.csv")
    parser.add_argument("--status", required=True)
    parser.add_argument("--output-dir", default="data/analysis")
    args = parser.parse_args()

    registry = pd.read_csv(args.registry, dtype=str, keep_default_na=False)
    status = pd.read_csv(args.status, dtype=str, keep_default_na=False)

    registry["istat_code"] = registry["istat_code"].astype(str).str.zfill(6)
    status["istat_code"] = status["istat_code"].astype(str).str.zfill(6)

    legacy = {
        "current_reference_year": "target_start_year",
        "current_period_present": "period_starting_target_year_present",
        "current_period_publication_count": (
            "period_starting_target_year_publication_count"
        ),
    }
    status = status.rename(
        columns={
            old: new
            for old, new in legacy.items()
            if old in status.columns and new not in status.columns
        }
    )

    required = {
        "istat_code",
        "piao_present_on_portal",
        "period_starting_target_year_present",
        "lookup_status",
        "target_start_year",
    }
    missing = required - set(status.columns)
    if missing:
        raise ValueError(f"Status dataset missing required fields: {sorted(missing)}")

    data = registry[
        ["istat_code", "name", "region_name", "supra_name", "ipa_code"]
    ].merge(
        status,
        on="istat_code",
        how="left",
        validate="one_to_one",
        suffixes=("", "_status"),
    )

    if len(data) != len(registry):
        raise ValueError("Status join changed municipality registry row count")

    data["has_any_piao"] = as_bool(data["piao_present_on_portal"])
    data["has_target_piao"] = as_bool(
        data["period_starting_target_year_present"]
    )
    data["is_error"] = data["lookup_status"].eq("error")

    data["cycle_status"] = "no_piao_observed"
    data.loc[data["has_any_piao"], "cycle_status"] = "prior_period_only"
    data.loc[data["has_target_piao"], "cycle_status"] = "target_period_present"
    data.loc[data["is_error"], "cycle_status"] = "lookup_error"

    target_years = sorted(
        {
            int(value)
            for value in data["target_start_year"]
            if str(value).strip().isdigit()
        }
    )
    if len(target_years) != 1:
        raise ValueError(f"Expected one target start year, found {target_years}")
    target_start_year = target_years[0]
    target_period = f"{target_start_year}-{target_start_year + 2}"

    categories = [
        "target_period_present",
        "prior_period_only",
        "no_piao_observed",
        "lookup_error",
    ]

    def summarise(group: pd.DataFrame) -> dict[str, object]:
        total = len(group)
        counts = group["cycle_status"].value_counts().to_dict()
        result: dict[str, object] = {"municipalities": total}
        for category in categories:
            count = int(counts.get(category, 0))
            result[category] = count
            result[f"{category}_pct"] = round(count / total * 100, 2) if total else 0
        return result

    national = summarise(data)

    regional_rows: list[dict[str, object]] = []
    for region_name, group in data.groupby("region_name", sort=True):
        regional_rows.append(
            {
                "region_name": region_name,
                **summarise(group),
            }
        )
    regional = pd.DataFrame(regional_rows)

    supra_rows: list[dict[str, object]] = []
    for (region_name, supra_name), group in data.groupby(
        ["region_name", "supra_name"],
        sort=True,
    ):
        supra_rows.append(
            {
                "region_name": region_name,
                "supra_name": supra_name,
                **summarise(group),
            }
        )
    supra = pd.DataFrame(supra_rows)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    municipality_path = output_dir / "municipality_piao_cycle_status.csv"
    regional_path = output_dir / "piao_coverage_by_region.csv"
    supra_path = output_dir / "piao_coverage_by_supra_area.csv"
    summary_path = output_dir / "piao_coverage_summary.json"

    municipality_columns = [
        "istat_code",
        "name",
        "ipa_code",
        "region_name",
        "supra_name",
        "cycle_status",
        "latest_reference_period",
        "latest_version",
        "latest_approval_date",
        "publication_count",
    ]
    data[municipality_columns].sort_values("istat_code").to_csv(
        municipality_path,
        index=False,
    )
    regional.to_csv(regional_path, index=False)
    supra.to_csv(supra_path, index=False)

    summary = {
        "target_start_year": target_start_year,
        "target_reference_period": target_period,
        "national": national,
        "outputs": {
            "municipality_status": str(municipality_path),
            "regional": str(regional_path),
            "supra_area": str(supra_path),
        },
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
