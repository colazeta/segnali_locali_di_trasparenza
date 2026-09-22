from __future__ import annotations

import json

import pandas as pd

from segnali_locali_di_trasparenza.public_site import build_site


def test_build_public_site_generates_home_search_and_municipality_pages(tmp_path) -> None:
    registry = pd.DataFrame(
        [
            {
                "istat_code": "079160",
                "name": "Lamezia Terme",
                "region_name": "Calabria",
                "supra_name": "Catanzaro",
                "ipa_code": "c_m208",
            },
            {
                "istat_code": "064010",
                "name": "Bisaccia",
                "region_name": "Campania",
                "supra_name": "Avellino",
                "ipa_code": "c_a881",
            },
        ]
    )
    status = pd.DataFrame(
        [
            {
                "istat_code": "079160",
                "lookup_status": "found",
                "piao_present_on_portal": "True",
                "publication_count": "6",
                "target_start_year": "2026",
                "period_starting_target_year_present": "False",
                "period_starting_target_year_publication_count": "0",
                "latest_reference_period": "2025-2027",
                "latest_reference_start_year": "2025",
                "latest_reference_end_year": "2027",
                "latest_version": "3",
                "latest_approval_date": "2025-06-06",
                "latest_piao_document_url": "https://example.test/lamezia.pdf",
                "portal_publication_date_status": "not_exposed_by_public_api",
                "retrieved_at": "2026-09-20T19:32:50+00:00",
                "error": "",
            },
            {
                "istat_code": "064010",
                "lookup_status": "found",
                "piao_present_on_portal": "True",
                "publication_count": "1",
                "target_start_year": "2026",
                "period_starting_target_year_present": "True",
                "period_starting_target_year_publication_count": "1",
                "latest_reference_period": "2026-2028",
                "latest_reference_start_year": "2026",
                "latest_reference_end_year": "2028",
                "latest_version": "1",
                "latest_approval_date": "2026-03-30",
                "latest_piao_document_url": "https://example.test/bisaccia.pdf",
                "portal_publication_date_status": "not_exposed_by_public_api",
                "retrieved_at": "2026-09-20T19:32:50+00:00",
                "error": "",
            },
        ]
    )
    publications = pd.DataFrame(
        [
            {
                "istat_code": "079160",
                "reference_start_year": "2025",
                "reference_period": "2025-2027",
                "version": "3",
                "approval_date": "2025-06-06",
                "piao_document_url": "https://example.test/lamezia.pdf",
                "approval_act_url": "https://example.test/lamezia-act.pdf",
                "institutional_piao_url": "",
            },
            {
                "istat_code": "064010",
                "reference_start_year": "2026",
                "reference_period": "2026-2028",
                "version": "1",
                "approval_date": "2026-03-30",
                "piao_document_url": "https://example.test/bisaccia.pdf",
                "approval_act_url": "",
                "institutional_piao_url": "https://example.test/bisaccia",
            },
        ]
    )

    registry_path = tmp_path / "registry.csv"
    status_path = tmp_path / "status.csv"
    publications_path = tmp_path / "publications.csv"
    assets = tmp_path / "assets"
    output = tmp_path / "site"

    registry.to_csv(registry_path, index=False)
    status.to_csv(status_path, index=False)
    publications.to_csv(publications_path, index=False)
    assets.mkdir()
    (assets / "style.css").write_text("body{}", encoding="utf-8")
    (assets / "app.js").write_text("void 0;", encoding="utf-8")

    summary = build_site(
        registry_path=registry_path,
        status_path=status_path,
        publications_path=publications_path,
        assets_dir=assets,
        output_dir=output,
        base_path="/segnali_locali_di_trasparenza",
    )

    assert summary["municipalities"] == 2
    assert summary["status_counts"]["target_period_present"] == 1
    assert summary["status_counts"]["prior_period_only"] == 1

    home = (output / "index.html").read_text(encoding="utf-8")
    lamezia = (output / "comune" / "079160" / "index.html").read_text(
        encoding="utf-8"
    )
    bisaccia = (output / "comune" / "064010" / "index.html").read_text(
        encoding="utf-8"
    )

    assert "Dove sono i PIAO 2026–2028?" in home
    assert "Solo PIAO precedenti" in lamezia
    assert "2025-2027" in lamezia
    assert "PIAO 2026–2028 presente" in bisaccia
    assert "0 giorni" in bisaccia
    assert "scadenza 30/03/2026" in bisaccia
    assert "≥ 143 giorni" in lamezia
    assert "scadenza 30/04/2026" in lamezia

    timeliness = (output / "tempi" / "index.html").read_text(encoding="utf-8")
    assert "Tempi di adozione dei PIAO" in timeliness
    assert "Bisaccia" in timeliness
    assert "Lamezia Terme" in timeliness
    assert "30/04/2026" in timeliness

    search = json.loads(
        (output / "data" / "municipalities.json").read_text(encoding="utf-8")
    )
    assert {item["istat_code"] for item in search} == {"079160", "064010"}
    assert (output / "data" / "piao_timeliness_ranking.json").exists()
    assert (output / "tempi" / "index.html").exists()
    assert (output / "metodologia" / "index.html").exists()
    assert (output / ".nojekyll").exists()
