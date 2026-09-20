from __future__ import annotations

from segnali_locali_di_trasparenza.piao import (
    extract_node_urls,
    parse_piao_detail,
    piao_search_url,
)


def test_piao_search_url_uses_ipa_filter() -> None:
    url = piao_search_url("c_l719")
    assert "field_administration_ipa_value=c_l719" in url
    assert "name=" in url
    assert "page=0" in url


def test_extract_node_urls_deduplicates_portal_nodes() -> None:
    html = """
    <a href="/node/32305">Piano 1</a>
    <a href="/node/32305/printable/print">Stampa</a>
    <a href="/news">News</a>
    <a href="/node/34227">Piano 2</a>
    """
    assert extract_node_urls(html) == [
        "https://piao.dfp.gov.it/node/32305",
        "https://piao.dfp.gov.it/node/34227",
    ]


def test_parse_piao_detail_extracts_official_metadata() -> None:
    html = """
    <html>
      <head>
        <meta property="article:published_time" content="2025-04-02T09:31:12+02:00">
      </head>
      <body>
        <h1>Piano Integrato c_l719 2025-2027</h1>
        <div>Amministrazione</div>
        <div><a href="/administration/123">Comune di Velletri</a></div>
        <div>Link</div>
        <div><a href="/data/documents/170000/piao.pdf">PDF del Piano</a></div>
        <div>Anno</div>
        <div>2025-2027</div>
        <div>Data Approvazione</div>
        <div>28-03-2025</div>
        <div>Link PA</div>
        <div><a href="https://comune.example.it/piao">Link del PIAO pubblicato sul portale istituzionale dell'Ente</a></div>
      </body>
    </html>
    """

    record = parse_piao_detail(
        html,
        "https://piao.dfp.gov.it/node/32305",
        observed_at="2026-09-20T15:00:00+00:00",
        collector_version="abc123",
    )

    assert record.portal_node_id == "32305"
    assert record.ipa_code == "c_l719"
    assert record.administration_name == "Comune di Velletri"
    assert record.reference_period == "2025-2027"
    assert record.reference_start_year == 2025
    assert record.reference_end_year == 2027
    assert record.approval_date == "28-03-2025"
    assert record.portal_published_at == "2025-04-02T09:31:12+02:00"
    assert record.pdf_url == "https://piao.dfp.gov.it/data/documents/170000/piao.pdf"
    assert record.pa_url == "https://comune.example.it/piao"
    assert record.collector_version == "abc123"
    assert record.methodology_version == "piao001-v1"


def test_parse_piao_detail_keeps_publication_date_empty_when_not_exposed() -> None:
    html = """
    <html><body>
      <h1>Piano Integrato c_c118 2025-2027</h1>
      <div>Amministrazione</div><div>Comune di Castel Goffredo</div>
      <div>Anno</div><div>2025-2027</div>
      <div>Data Approvazione</div><div>31-01-2025</div>
    </body></html>
    """
    record = parse_piao_detail(html, "https://piao.dfp.gov.it/node/34227")
    assert record.portal_published_at == ""
    assert record.approval_date == "31-01-2025"
