from __future__ import annotations

import pandas as pd

from segnali_locali_di_trasparenza.registry import link_ipa, normalise_name, validate_registry


def test_normalise_name_removes_comune_prefix() -> None:
    assert normalise_name("Comune di Lamezia Terme") == "lamezia terme"
    assert normalise_name("COMUNE DI  Milano") == "milano"


def test_link_ipa_prefers_exact_municipality_name() -> None:
    istat = pd.DataFrame(
        [
            {
                "municipality_version_id": "IT-ISTAT-079160",
                "istat_code": "079160",
                "name": "Lamezia Terme",
                "region_code": "18",
                "region_name": "Calabria",
                "supra_code": "079",
                "supra_name": "Catanzaro",
                "province_abbr": "CZ",
                "cadastral_code": "M208",
                "name_normalised": "lamezia terme",
            }
        ]
    )

    ipa = pd.DataFrame(
        [
            {
                "ipa_code": "c_m208",
                "ipa_name": "Comune di Lamezia Terme",
                "fiscal_code": "00301390795",
                "ipa_category": "L6",
                "seat_istat_code": "079160",
                "seat_cadastral_code": "M208",
                "institutional_url": "https://www.comune.lamezia-terme.cz.it/",
                "updated_at_ipa": "2026-09-20",
                "ipa_name_normalised": "lamezia terme",
            },
            {
                "ipa_code": "consorzio_test",
                "ipa_name": "Consorzio dei Comuni del Test",
                "fiscal_code": "",
                "ipa_category": "L6",
                "seat_istat_code": "079160",
                "seat_cadastral_code": "M208",
                "institutional_url": "",
                "updated_at_ipa": "",
                "ipa_name_normalised": "consorzio dei comuni del test",
            },
        ]
    )

    result = link_ipa(istat, ipa)

    assert result.loc[0, "ipa_code"] == "c_m208"
    assert result.loc[0, "ipa_match_status"] == "matched_exact"
    assert result.loc[0, "ipa_candidate_count"] == 2


def test_link_ipa_keeps_ambiguous_candidates_unresolved() -> None:
    istat = pd.DataFrame(
        [
            {
                "municipality_version_id": "IT-ISTAT-001001",
                "istat_code": "001001",
                "name": "Comune Test",
                "region_code": "01",
                "region_name": "Piemonte",
                "supra_code": "001",
                "supra_name": "Torino",
                "province_abbr": "TO",
                "cadastral_code": "A001",
                "name_normalised": "test",
            }
        ]
    )

    ipa = pd.DataFrame(
        [
            {
                "ipa_code": "a",
                "ipa_name": "Comune Test A",
                "fiscal_code": "",
                "ipa_category": "L6",
                "seat_istat_code": "001001",
                "seat_cadastral_code": "A001",
                "institutional_url": "",
                "updated_at_ipa": "",
                "ipa_name_normalised": "test a",
            },
            {
                "ipa_code": "b",
                "ipa_name": "Comune Test B",
                "fiscal_code": "",
                "ipa_category": "L6",
                "seat_istat_code": "001001",
                "seat_cadastral_code": "A001",
                "institutional_url": "",
                "updated_at_ipa": "",
                "ipa_name_normalised": "test b",
            },
        ]
    )

    result = link_ipa(istat, ipa)

    assert result.loc[0, "ipa_match_status"] == "ambiguous"
    assert result.loc[0, "ipa_code"] == ""


def test_validate_registry_counts_link_states() -> None:
    registry = pd.DataFrame(
        [
            {
                "municipality_version_id": "IT-ISTAT-001001",
                "istat_code": "001001",
                "ipa_code": "x",
                "ipa_match_status": "matched_exact",
            },
            {
                "municipality_version_id": "IT-ISTAT-001002",
                "istat_code": "001002",
                "ipa_code": "",
                "ipa_match_status": "unmatched",
            },
        ]
    )

    assert validate_registry(registry) == {
        "municipalities": 2,
        "ipa_matched": 1,
        "ipa_ambiguous": 0,
        "ipa_unmatched": 1,
    }
