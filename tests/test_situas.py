from __future__ import annotations

import pytest

from segnali_locali_di_trasparenza.situas import SituasError, apply_dates, rows, validity_end


def test_rows_normalises_known_situas_envelopes() -> None:
    assert rows({"resultset": [{"A": 1}]}) == [{"A": 1}]
    assert rows({"items": [{"A": 2}]}) == [{"A": 2}]
    assert rows([{"A": 3}]) == [{"A": 3}]


def test_validity_end_reads_catalog_range() -> None:
    entry = {"Inizio/fine validità report": "01/01/1991 - 20/09/2026"}
    assert validity_end(entry) == "20/09/2026"


def test_apply_dates_updates_single_date_report() -> None:
    url = (
        "https://situas-servizi.istat.it/publish/reportspooljson?"
        "pfun=129&pdata=01/01/1991"
    )
    assert apply_dates(url, default_date="20/09/2026").endswith(
        "pfun=129&pdata=20/09/2026"
    )


def test_apply_dates_updates_range_report() -> None:
    url = (
        "https://situas-servizi.istat.it/publish/reportspooljson?"
        "pfun=99&pdatada=01/01/1991&pdataa=31/05/2026"
    )
    result = apply_dates(
        url,
        date_from="01/01/2001",
        date_to="20/09/2026",
    )
    assert "pdatada=01/01/2001" in result
    assert "pdataa=20/09/2026" in result


def test_apply_dates_rejects_wrong_date_shape() -> None:
    url = (
        "https://situas-servizi.istat.it/publish/reportspooljson?"
        "pfun=99&pdatada=01/01/1991&pdataa=31/05/2026"
    )
    with pytest.raises(SituasError):
        apply_dates(url, date="20/09/2026")
