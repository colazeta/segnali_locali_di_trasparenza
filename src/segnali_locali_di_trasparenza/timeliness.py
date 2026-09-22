from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import pandas as pd


@dataclass(frozen=True)
class DeadlineRule:
    budget_deadline: date
    piao_deadline: date
    scope: str
    legal_basis: str


NATIONAL_2026 = DeadlineRule(
    budget_deadline=date(2026, 2, 28),
    piao_deadline=date(2026, 3, 30),
    scope="national",
    legal_basis=(
        "DM Interno 24-12-2025: bilancio 2026-2028 differito al 28-02-2026; "
        "art. 8, c. 2, DM 132/2022: PIAO entro i 30 giorni successivi"
    ),
)

SOUTHERN_2026 = DeadlineRule(
    budget_deadline=date(2026, 3, 31),
    piao_deadline=date(2026, 4, 30),
    scope="regional_override",
    legal_basis=(
        "DM Interno 26-02-2026: ulteriore differimento del bilancio 2026-2028 "
        "al 31-03-2026 per Calabria, Sardegna e Sicilia; "
        "art. 8, c. 2, DM 132/2022: PIAO entro i 30 giorni successivi"
    ),
)

REGIONAL_OVERRIDES_2026 = {"Calabria", "Sardegna", "Sicilia"}


def deadline_rule(target_start_year: int, region_name: str) -> DeadlineRule:
    """Return the statutory PIAO deadline rule used by the monitor."""
    if target_start_year != 2026:
        raise ValueError(
            f"No reviewed PIAO deadline rule configured for target year {target_start_year}"
        )
    if str(region_name).strip() in REGIONAL_OVERRIDES_2026:
        return SOUTHERN_2026
    return NATIONAL_2026


def _truthy(value: object) -> bool:
    if value is None or pd.isna(value):
        return False
    return str(value).strip().casefold() in {"true", "1", "yes", "si", "sì"}


def _target_year(status: pd.DataFrame) -> int:
    values = sorted(
        {
            int(value)
            for value in status["target_start_year"]
            if str(value).strip().isdigit()
        }
    )
    if len(values) != 1:
        raise ValueError(f"Expected one target start year, found {values}")
    return values[0]


def _snapshot_date(status: pd.DataFrame) -> date:
    parsed = pd.to_datetime(status["retrieved_at"], errors="coerce", utc=True).dropna()
    if parsed.empty:
        raise ValueError("No valid retrieved_at value available for timeliness analysis")
    return parsed.max().date()


def build_timeliness_table(
    registry: pd.DataFrame,
    status: pd.DataFrame,
    publications: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build one timeliness row per municipality.

    The ranking is based on the first approval date observed for the target PIAO
    cycle. It must not be described as a portal-publication ranking: the current
    public API does not expose an authoritative historical publication timestamp.
    """
    registry = registry.copy()
    status = status.copy()
    publications = publications.copy()

    for frame in (registry, status, publications):
        frame["istat_code"] = frame["istat_code"].astype(str).str.zfill(6)

    target_start_year = _target_year(status)
    snapshot_date = _snapshot_date(status)

    joined = registry[
        ["istat_code", "name", "region_name", "supra_name", "ipa_code"]
    ].merge(
        status[
            [
                "istat_code",
                "lookup_status",
                "period_starting_target_year_present",
                "retrieved_at",
            ]
        ],
        on="istat_code",
        how="left",
        validate="one_to_one",
    )
    if len(joined) != len(registry):
        raise ValueError("Timeliness join changed municipality registry row count")

    working = publications.copy()
    working["_start_year"] = pd.to_numeric(
        working["reference_start_year"], errors="coerce"
    )
    target = working.loc[working["_start_year"].eq(target_start_year)].copy()
    target["_approval_dt"] = pd.to_datetime(
        target["approval_date"], errors="coerce"
    )

    target_counts = target.groupby("istat_code").size()
    valid_approvals = target.dropna(subset=["_approval_dt"]).copy()
    first_approvals = valid_approvals.groupby("istat_code")["_approval_dt"].min()

    joined["target_publication_count"] = (
        joined["istat_code"].map(target_counts).fillna(0).astype(int)
    )
    joined["target_first_approval_date"] = joined["istat_code"].map(first_approvals)
    joined["target_first_approval_date"] = pd.to_datetime(
        joined["target_first_approval_date"], errors="coerce"
    )

    rules = [
        deadline_rule(target_start_year, region_name)
        for region_name in joined["region_name"]
    ]
    joined["budget_deadline"] = [rule.budget_deadline.isoformat() for rule in rules]
    joined["expected_piao_deadline"] = [
        rule.piao_deadline.isoformat() for rule in rules
    ]
    joined["deadline_scope"] = [rule.scope for rule in rules]
    joined["deadline_legal_basis"] = [rule.legal_basis for rule in rules]
    deadline_dt = pd.to_datetime(joined["expected_piao_deadline"])

    joined["approval_lag_days"] = (
        joined["target_first_approval_date"] - deadline_dt
    ).dt.days.astype("Int64")

    joined["timeliness_status"] = "target_not_observed"
    target_present = joined["period_starting_target_year_present"].map(_truthy)
    lookup_error = joined["lookup_status"].astype(str).str.casefold().eq("error")
    valid_date = joined["target_first_approval_date"].notna()

    joined.loc[target_present & ~valid_date, "timeliness_status"] = (
        "target_present_approval_date_missing"
    )
    joined.loc[
        target_present & valid_date & joined["approval_lag_days"].lt(0),
        "timeliness_status",
    ] = "early"
    joined.loc[
        target_present & valid_date & joined["approval_lag_days"].eq(0),
        "timeliness_status",
    ] = "on_deadline"
    joined.loc[
        target_present & valid_date & joined["approval_lag_days"].gt(0),
        "timeliness_status",
    ] = "late"
    joined.loc[lookup_error, "timeliness_status"] = "lookup_error"

    joined["days_overdue_at_snapshot"] = pd.Series(pd.NA, index=joined.index, dtype="Int64")
    missing_target = ~target_present & ~lookup_error
    snapshot_ts = pd.Timestamp(snapshot_date)
    overdue = (snapshot_ts - deadline_dt).dt.days.clip(lower=0).astype("Int64")
    joined.loc[missing_target, "days_overdue_at_snapshot"] = overdue.loc[missing_target]

    rankable = target_present & valid_date & ~lookup_error
    joined["approval_lag_rank_national"] = pd.Series(
        pd.NA, index=joined.index, dtype="Int64"
    )
    joined.loc[rankable, "approval_lag_rank_national"] = (
        joined.loc[rankable, "approval_lag_days"]
        .rank(method="dense", ascending=True)
        .astype("Int64")
    )

    joined["approval_lag_rank_region"] = pd.Series(
        pd.NA, index=joined.index, dtype="Int64"
    )
    for indexes in joined.loc[rankable].groupby("region_name").groups.values():
        joined.loc[indexes, "approval_lag_rank_region"] = (
            joined.loc[indexes, "approval_lag_days"]
            .rank(method="dense", ascending=True)
            .astype("Int64")
        )

    joined["target_first_approval_date"] = joined[
        "target_first_approval_date"
    ].dt.strftime("%Y-%m-%d").fillna("")
    joined["target_start_year"] = target_start_year
    joined["snapshot_date"] = snapshot_date.isoformat()
    joined["publication_lag_days"] = pd.Series(pd.NA, index=joined.index, dtype="Int64")
    joined["publication_lag_status"] = "not_historically_exposed_by_public_api"

    sort_group = pd.Series(3, index=joined.index)
    sort_group.loc[rankable] = 0
    sort_group.loc[target_present & ~valid_date & ~lookup_error] = 1
    sort_group.loc[missing_target] = 2
    joined["_sort_group"] = sort_group

    joined = joined.sort_values(
        [
            "_sort_group",
            "approval_lag_days",
            "days_overdue_at_snapshot",
            "region_name",
            "name",
            "istat_code",
        ],
        ascending=[True, True, False, True, True, True],
        na_position="last",
        kind="stable",
    ).drop(columns=["_sort_group"])

    columns = [
        "istat_code",
        "name",
        "ipa_code",
        "region_name",
        "supra_name",
        "target_start_year",
        "target_publication_count",
        "target_first_approval_date",
        "budget_deadline",
        "expected_piao_deadline",
        "deadline_scope",
        "deadline_legal_basis",
        "approval_lag_days",
        "timeliness_status",
        "approval_lag_rank_national",
        "approval_lag_rank_region",
        "days_overdue_at_snapshot",
        "publication_lag_days",
        "publication_lag_status",
        "snapshot_date",
    ]
    return joined[columns].reset_index(drop=True)


LAG_BINS = [
    ("30+ days early", None, -30),
    ("1-29 days early", -29, -1),
    ("on deadline", 0, 0),
    ("1-30 days late", 1, 30),
    ("31-60 days late", 31, 60),
    ("61-90 days late", 61, 90),
    ("91+ days late", 91, None),
]


def summarise_lag_distribution(timeliness: pd.DataFrame) -> pd.DataFrame:
    """Summarise the observed approval-lag distribution for rankable municipalities."""
    lag = pd.to_numeric(timeliness["approval_lag_days"], errors="coerce")
    rows: list[dict[str, object]] = []
    denominator = int(lag.notna().sum())

    for label, lower, upper in LAG_BINS:
        mask = lag.notna()
        if lower is not None:
            mask &= lag.ge(lower)
        if upper is not None:
            mask &= lag.le(upper)
        count = int(mask.sum())
        rows.append(
            {
                "lag_band": label,
                "lower_days": "" if lower is None else lower,
                "upper_days": "" if upper is None else upper,
                "municipalities": count,
                "share_pct": round(count / denominator * 100, 2) if denominator else 0.0,
            }
        )

    return pd.DataFrame(rows)


def summarise_timeliness_by_region(timeliness: pd.DataFrame) -> pd.DataFrame:
    """
    Produce descriptive regional comparisons of approval timeliness.

    These are descriptive statistics, not causal estimates. Lag is already
    normalised to each municipality's applicable statutory deadline.
    """
    rows: list[dict[str, object]] = []

    for region_name, group in timeliness.groupby("region_name", sort=True):
        lag = pd.to_numeric(group["approval_lag_days"], errors="coerce")
        valid = lag.notna()
        observed = group["timeliness_status"].isin(
            {"early", "on_deadline", "late", "target_present_approval_date_missing"}
        )
        missing_target = group["timeliness_status"].eq("target_not_observed")
        overdue = pd.to_numeric(
            group.loc[missing_target, "days_overdue_at_snapshot"],
            errors="coerce",
        ).dropna()

        valid_lag = lag.loc[valid]
        on_time = valid_lag.le(0)

        rows.append(
            {
                "region_name": region_name,
                "municipalities": len(group),
                "target_piao_observed": int(observed.sum()),
                "target_piao_observed_pct": round(observed.mean() * 100, 2),
                "target_piao_with_approval_date": int(valid.sum()),
                "on_or_before_deadline": int(on_time.sum()),
                "on_or_before_deadline_pct": (
                    round(on_time.mean() * 100, 2) if len(valid_lag) else None
                ),
                "late": int(valid_lag.gt(0).sum()),
                "lag_median_days": (
                    float(valid_lag.median()) if len(valid_lag) else None
                ),
                "lag_mean_days": (
                    float(valid_lag.mean()) if len(valid_lag) else None
                ),
                "lag_p25_days": (
                    float(valid_lag.quantile(0.25)) if len(valid_lag) else None
                ),
                "lag_p75_days": (
                    float(valid_lag.quantile(0.75)) if len(valid_lag) else None
                ),
                "lag_p90_days": (
                    float(valid_lag.quantile(0.90)) if len(valid_lag) else None
                ),
                "target_piao_not_observed": int(missing_target.sum()),
                "target_piao_not_observed_pct": round(missing_target.mean() * 100, 2),
                "missing_target_overdue_median_days": (
                    float(overdue.median()) if len(overdue) else None
                ),
            }
        )

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(
        ["lag_median_days", "on_or_before_deadline_pct", "region_name"],
        ascending=[True, False, True],
        na_position="last",
        kind="stable",
    ).reset_index(drop=True)


def national_timeliness_statistics(timeliness: pd.DataFrame) -> dict[str, object]:
    """Return compact national descriptive statistics for the approval-lag layer."""
    lag = pd.to_numeric(timeliness["approval_lag_days"], errors="coerce").dropna()
    if lag.empty:
        return {
            "n": 0,
            "mean": None,
            "median": None,
            "p10": None,
            "p25": None,
            "p75": None,
            "p90": None,
            "min": None,
            "max": None,
            "on_or_before_deadline_pct": None,
        }

    return {
        "n": len(lag),
        "mean": float(lag.mean()),
        "median": float(lag.median()),
        "p10": float(lag.quantile(0.10)),
        "p25": float(lag.quantile(0.25)),
        "p75": float(lag.quantile(0.75)),
        "p90": float(lag.quantile(0.90)),
        "min": int(lag.min()),
        "max": int(lag.max()),
        "on_or_before_deadline_pct": round(float(lag.le(0).mean() * 100), 2),
    }
