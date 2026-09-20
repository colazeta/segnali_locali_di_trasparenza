from __future__ import annotations

import pandas as pd

from segnali_locali_di_trasparenza.registry import (
    link_ipa,
    name_aliases,
    normalise_name,
    validate_registry,
)


def _istat_row(
    *,
    code: str,
    name: str,
    cadastral: str,
    name_full: str = "",
    name_other: str = "",
) -> dict[str, str]:
    return {
        "municipality_version_id": f"IT-ISTAT-{code}",
        "istat_code": code,
        "name": name,
        "name_full": name_full,
        "name_other": name_other,
        "region_code": "00",
        "region_name": "Test",
        "supra_code": code[:3],
        "supra_name": "Test",
        "province_abbr": "TT",
        "cadastral_code": cadastral,
        "name_normalised": normalise_name(name),
    }


def _ipa_row(
    *,
    ipa_code: str,
    name: str,
    code: str,
    cadastral: str,
) -> dict[str, str | bool]:
    return {
        "ipa_code": ipa_code,
        "ipa_name": name,
        "fiscal_code": "",
        "ipa_category": "L6",
        "seat_istat_code": code,
        "seat_cadastral_code": cadastral,
        "institutional_url": "",
        "updated_at_ipa": "",
        "ipa_name_normalised": normalise_name(name),
        "looks_like_municipality": bool(
            name.lower().startswith(("comune", "gemeinde", "comun", "municipio"))
        ),
    }


def test_normalise_name_removes_multilingual_municipal_prefixes() -> None:
    assert normalise_name("Comune di Lamezia Terme") == "lamezia terme"
    assert normalise_name("Gemeinde Kuens") == "kuens"
    assert normalise_name("Comun de Sèn Jan") == "sen jan"


def test_name_aliases_splits_multilingual_official_names() -> None:
    aliases = name_aliases("Caines/Kuens", "Caines", "Kuens")
    assert aliases == {"caines", "kuens", "caines kuens"}


def test_link_ipa_prefers_exact_municipality_name() -> None:
    istat = pd.DataFrame(
        [_istat_row(code="079160", name="Lamezia Terme", cadastral="M208")]
    )
    ipa = pd.DataFrame(
        [
            _ipa_row(
                ipa_code="c_m208",
                name="Comune di Lamezia Terme",
                code="079160",
                cadastral="M208",
            ),
            _ipa_row(
                ipa_code="consorzio_test",
                name="Consorzio dei Comuni del Test",
                code="079160",
                cadastral="M208",
            ),
        ]
    )

    result = link_ipa(istat, ipa)

    assert result.loc[0, "ipa_code"] == "c_m208"
    assert result.loc[0, "ipa_match_status"] == "matched_exact"
    assert result.loc[0, "ipa_candidate_count"] == 2


def test_link_ipa_uses_official_other_language_name() -> None:
    istat = pd.DataFrame(
        [
            _istat_row(
                code="021014",
                name="Caines",
                name_full="Caines/Kuens",
                name_other="Kuens",
                cadastral="B364",
            )
        ]
    )
    ipa = pd.DataFrame(
        [
            _ipa_row(
                ipa_code="kuens",
                name="Gemeinde Kuens",
                code="",
                cadastral="",
            )
        ]
    )

    result = link_ipa(istat, ipa)

    assert result.loc[0, "ipa_code"] == "kuens"
    assert result.loc[0, "ipa_match_status"] == "matched_global_exact"
    assert result.loc[0, "ipa_match_basis"] == "unique_official_name_global"


def test_link_ipa_accepts_curated_legal_entity_alias() -> None:
    istat = pd.DataFrame(
        [_istat_row(code="058091", name="Roma", cadastral="H501")]
    )
    ipa = pd.DataFrame(
        [
            _ipa_row(
                ipa_code="c_h501",
                name="Roma Capitale",
                code="058091",
                cadastral="H501",
            ),
            _ipa_row(
                ipa_code="other",
                name="Consorzio dei Comuni Romani",
                code="058091",
                cadastral="H501",
            ),
        ]
    )

    result = link_ipa(
        istat,
        ipa,
        curated_aliases={"058091": ["Roma Capitale"]},
    )

    assert result.loc[0, "ipa_code"] == "c_h501"
    assert result.loc[0, "ipa_match_status"] == "matched_exact"


def test_link_ipa_keeps_ambiguous_candidates_unresolved() -> None:
    istat = pd.DataFrame(
        [_istat_row(code="001001", name="Comune Test", cadastral="A001")]
    )
    ipa = pd.DataFrame(
        [
            _ipa_row(
                ipa_code="a",
                name="Comune Test A",
                code="001001",
                cadastral="A001",
            ),
            _ipa_row(
                ipa_code="b",
                name="Comune Test B",
                code="001001",
                cadastral="A001",
            ),
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


def test_read_istat_preserves_none_as_municipality_name(tmp_path) -> None:
    source = tmp_path / "istat.xlsx"
    frame = pd.DataFrame(
        [
            {
                "Codice Comune formato alfanumerico": "001168",
                "Denominazione in italiano": "None",
                "Denominazione (Italiana e straniera)": "None",
                "Denominazione altra lingua": "",
                "Codice Regione": "01",
                "Denominazione Regione": "Piemonte",
                "Codice dell'Unità territoriale sovracomunale (valida a fini statistici)": "001",
                "Denominazione dell'Unità territoriale sovracomunale (valida a fini statistici)": "Torino",
                "Sigla automobilistica": "TO",
                "Codice Catastale del comune": "F931",
            }
        ]
    )
    frame.to_excel(source, index=False)

    result = read_istat(source)

    assert result.loc[0, "name"] == "None"
    assert result.loc[0, "name_full"] == "None"
    assert result.loc[0, "name_normalised"] == "none"
