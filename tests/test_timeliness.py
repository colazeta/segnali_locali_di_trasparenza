from __future__ import annotations

import pandas as pd

from segnali_locali_di_trasparenza.timeliness import (
    build_timeliness_table,
    deadline_rule,
)


def test_deadline_rule_2026_uses_regional_override() -> None:
    assert deadline_rule(2026, "Campania").piao_deadline.isoformat() == "2026-03-30"
    assert deadline_rule(2026, "Calabria").piao_deadline.isoformat() == "2026-04-30"
    assert deadline_rule(2026, "Sardegna").piao_deadline.isoformat() == "2026-04-30"
    assert deadline_rule(2026, "Sicilia").piao_deadline.isoformat() == "2026-04-30"


def test_timeliness_uses_first_target_approval_and_censors_missing_target() -> None:
    registry = pd.DataFrame(
        [
            {
                "istat_code": "064010",
                "name": "Bisaccia",
                "region_name": "Campania",
                "supra_name": "Avellino",
                "ipa_code": "c_a881",
            },
            {
                "istat_code": "079160",
                "name": "Lamezia Terme",
                "region_name": "Calabria",
                "supra_name": "Catanzaro",
                "ipa_code": "c_m208",
            },
            {
                "istat_code": "082001",
                "name": "Comune Sicilia",
                "region_name": "Sicilia",
                "supra_name": "Palermo",
                "ipa_code": "c_sic",
            },
            {
                "istat_code": "015146",
                "name": "Milano",
                "region_name": "Lombardia",
                "supra_name": "Milano",
                "ipa_code": "c_f205",
            },
        ]
    )
    status = pd.DataFrame(
        [
            {
                "istat_code": "064010",
                "lookup_status": "found",
                "target_start_year": "2026",
                "period_starting_target_year_present": "True",
                "retrieved_at": "2026-09-20T19:32:50+00:00",
            },
            {
                "istat_code": "079160",
                "lookup_status": "found",
                "target_start_year": "2026",
                "period_starting_target_year_present": "False",
                "retrieved_at": "2026-09-20T19:32:50+00:00",
            },
            {
                "istat_code": "082001",
                "lookup_status": "found",
                "target_start_year": "2026",
                "period_starting_target_year_present": "True",
                "retrieved_at": "2026-09-20T19:32:50+00:00",
            },
            {
                "istat_code": "015146",
                "lookup_status": "found",
                "target_start_year": "2026",
                "period_starting_target_year_present": "True",
                "retrieved_at": "2026-09-20T19:32:50+00:00",
            },
        ]
    )
    publications = pd.DataFrame(
        [
            {
                "istat_code": "064010",
                "reference_start_year": "2026",
                "approval_date": "2026-03-30",
            },
            {
                "istat_code": "064010",
                "reference_start_year": "2026",
                "approval_date": "2026-05-10",
            },
            {
                "istat_code": "079160",
                "reference_start_year": "2025",
                "approval_date": "2025-06-06",
            },
            {
                "istat_code": "082001",
                "reference_start_year": "2026",
                "approval_date": "2026-05-10",
            },
            {
                "istat_code": "015146",
                "reference_start_year": "2026",
                "approval_date": "2026-03-15",
            },
        ]
    )

    result = build_timeliness_table(registry, status, publications).set_index("istat_code")

    assert result.loc["064010", "target_first_approval_date"] == "2026-03-30"
    assert result.loc["064010", "approval_lag_days"] == 0
    assert result.loc["064010", "timeliness_status"] == "on_deadline"

    assert result.loc["015146", "approval_lag_days"] == -15
    assert result.loc["015146", "approval_lag_rank_national"] == 1

    assert result.loc["082001", "expected_piao_deadline"] == "2026-04-30"
    assert result.loc["082001", "approval_lag_days"] == 10

    assert result.loc["079160", "expected_piao_deadline"] == "2026-04-30"
    assert result.loc["079160", "timeliness_status"] == "target_not_observed"
    assert result.loc["079160", "days_overdue_at_snapshot"] == 143
    assert pd.isna(result.loc["079160", "approval_lag_days"])

    assert result.loc["064010", "publication_lag_status"] == (
        "not_historically_exposed_by_public_api"
    )
