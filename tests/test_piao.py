from __future__ import annotations

import pandas as pd

from segnali_locali_di_trasparenza.piao import (
    build_municipality_piao_view,
    extract_plan_urls,
    link_plans_to_municipalities,
    parse_piao_page,
)


VELLETRI_HTML = """
<html>
  <head>
    <meta property="article:published_time" content="2025-03-28T10:15:00+01:00" />
    <title>Piano Integrato c_l719 2025-2027 | Portale PIAO</title>
  </head>
  <body>
    <h1>Piano Integrato c_l719 2025-2027</h1>
    <div class="field">
      <div class="field__label">Amministrazione</div>
      <div class="field__item">Comune di Velletri</div>
    </div>
    <div class="field">
      <div class="field__label">Link</div>
      <div class="field__item">
        <a href="/data/documents/12345/piao_2025_2027.pdf">PDF del Piano</a>
      </div>
    </div>
    <div class="field">
      <div class="field__label">Anno</div>
      <div class="field__item">2025-2027</div>
    </div>
    <div class="field">
      <div class="field__label">Data Approvazione</div>
      <div class="field__item">28-03-2025</div>
    </div>
    <div class="field">
      <div class="field__label">Link PA</div>
      <div class="field__item">
        <a href="https://www.comune.velletri.rm.it/piao">Link del PIAO pubblicato sul portale istituzionale dell'Ente</a>
      </div>
    </div>
  </body>
</html>
"""


def test_parse_piao_page_extracts_core_metadata() -> None:
    record = parse_piao_page(
        VELLETRI_HTML,
        "https://piao.dfp.gov.it/node/32305",
    )

    assert record.portal_node_id == "32305"
    assert record.portal_entity_code == "c_l719"
    assert record.administration_name == "Comune di Velletri"
    assert record.period_label == "2025-2027"
    assert record.period_start_year == 2025
    assert record.period_end_year == 2027
    assert record.approval_date == "2025-03-28"
    assert record.portal_published_at == "2025-03-28T10:15:00+01:00"
    assert record.pdf_url == "https://piao.dfp.gov.it/data/documents/12345/piao_2025_2027.pdf"
    assert record.pa_url == "https://www.comune.velletri.rm.it/piao"


def test_extract_plan_urls_keeps_only_portal_nodes() -> None:
    html = """
    <a href="/node/32305">Velletri</a>
    <a href="https://piao.dfp.gov.it/node/32611?x=1">Fonte Nuova</a>
    <a href="/data/documents/1/a.pdf">PDF</a>
    <a href="https://example.org/node/99">Other host</a>
    """

    assert extract_plan_urls(html) == [
        "https://piao.dfp.gov.it/node/32305",
        "https://piao.dfp.gov.it/node/32611",
    ]


def test_link_plans_prefers_ipa_code() -> None:
    registry = pd.DataFrame(
        [
            {
                "istat_code": "058111",
                "ipa_code": "c_l719",
                "name": "Velletri",
                "name_full": "Velletri",
                "name_other": "",
                "ipa_name": "Comune di Velletri",
                "region_name": "Lazio",
                "supra_name": "Roma",
            }
        ]
    )
    plans = pd.DataFrame(
        [
            {
                "portal_entity_code": "c_l719",
                "administration_name": "Comune di Velletri",
                "period_start_year": 2025,
                "period_label": "2025-2027",
                "approval_date": "2025-03-28",
                "portal_published_at": "",
                "portal_url": "https://piao.dfp.gov.it/node/32305",
                "pdf_url": "",
                "pa_url": "",
                "portal_node_id": "32305",
            }
        ]
    )

    result = link_plans_to_municipalities(plans, registry)

    assert result.loc[0, "istat_code"] == "058111"
    assert result.loc[0, "municipality_match_basis"] == "ipa_code"


def test_municipality_view_preserves_absence_as_observation_state() -> None:
    registry = pd.DataFrame(
        [
            {
                "istat_code": "058111",
                "ipa_code": "c_l719",
                "name": "Velletri",
                "region_name": "Lazio",
                "supra_name": "Roma",
            },
            {
                "istat_code": "079160",
                "ipa_code": "c_m208",
                "name": "Lamezia Terme",
                "region_name": "Calabria",
                "supra_name": "Catanzaro",
            },
        ]
    )
    linked = pd.DataFrame(
        [
            {
                "istat_code": "058111",
                "period_start_year": 2025,
                "period_label": "2025-2027",
                "approval_date": "2025-03-28",
                "portal_published_at": "",
                "portal_url": "https://piao.dfp.gov.it/node/32305",
                "pdf_url": "https://piao.dfp.gov.it/data/documents/123/piao.pdf",
                "pa_url": "https://www.comune.velletri.rm.it/piao",
                "portal_node_id": "32305",
            }
        ]
    )

    result = build_municipality_piao_view(linked, registry).set_index("istat_code")

    assert bool(result.loc["058111", "piao_present_any"])
    assert result.loc["058111", "piao_latest_period"] == "2025-2027"
    assert not bool(result.loc["079160", "piao_present_any"])
    assert result.loc["079160", "piao_count"] == 0
