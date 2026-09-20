from __future__ import annotations

from segnali_locali_di_trasparenza.transparency import (
    extract_candidates,
    normalise_start_url,
    page_looks_like_transparency,
)


def test_normalise_start_url_adds_https() -> None:
    assert normalise_start_url("example.gov.it") == "https://example.gov.it"
    assert normalise_start_url("https://example.gov.it") == "https://example.gov.it"


def test_extract_candidates_prioritises_explicit_transparency_link() -> None:
    html = """
    <html><body>
      <a href="/news/trasparenza-evento">Trasparenza e cittadini</a>
      <a href="/Amministrazione-Trasparente">Amministrazione Trasparente</a>
    </body></html>
    """

    candidates = extract_candidates(html, "https://comune.example.it/")

    assert candidates[0].url == "https://comune.example.it/Amministrazione-Trasparente"
    assert candidates[0].discovery_method == "homepage_link"
    assert candidates[0].score > candidates[1].score


def test_extract_candidates_handles_legacy_transparenz_url() -> None:
    html = """
    <html><body>
      <a href="/system/web/transparenz2014_sgv.aspx?lang=it">
        Amministrazione Trasparente
      </a>
    </body></html>
    """

    candidates = extract_candidates(html, "https://www.comune.example.bz.it/")

    assert len(candidates) == 1
    assert "transparenz2014" in candidates[0].url


def test_page_confirmation_uses_heading_or_url() -> None:
    assert page_looks_like_transparency(
        "<html><h1>Amministrazione Trasparente</h1></html>",
        "https://example.it/section",
    )
    assert page_looks_like_transparency(
        "<html><h1>Portale</h1></html>",
        "https://example.it/amministrazione-trasparente",
    )
    assert not page_looks_like_transparency(
        "<html><h1>Albo pretorio</h1></html>",
        "https://example.it/albo",
    )
