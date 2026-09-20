from __future__ import annotations

from typing import Any

from segnali_locali_di_trasparenza.piao import (
    fetch_publications_for_ipa,
    normalise_publication,
    parse_reference_period,
)


def sample_record(*, version: int = 3) -> dict[str, Any]:
    return {
        "administrationIpaCode": "c_m208",
        "administrationName": "Comune di Lamezia Terme",
        "version": version,
        "years": "Anno 2025-2027",
        "content": {
            "approvalDate": {"name": "approvalDate", "value": "2025-06-06"},
            "estremiAtto": {"name": "estremiAtto", "value": "deliberazione n. 197"},
            "autorita": {"name": "autorita", "value": "Giunta Comunale"},
            "nDipendenti": {
                "name": "nDipendenti",
                "value": {"value": "No", "label": "No"},
            },
            "piaoPDF": {
                "name": "piaoPDF",
                "files": [
                    {
                        "mimeType": "application/pdf",
                        "url": "https://portale-piao.dfp.gov.it/api/piao/document?f=x.pdf",
                        "fileName": "PIAO_2025_2027.pdf",
                        "alias": "PIAO_2025_2027.pdf",
                    }
                ],
            },
            "atto": {
                "name": "atto",
                "files": [
                    {
                        "mimeType": "application/pdf",
                        "url": "https://portale-piao.dfp.gov.it/api/piao/document?f=atto.pdf",
                        "fileName": "delibera.pdf",
                        "alias": "delibera.pdf",
                    }
                ],
            },
            "attachments": {
                "name": "attachments",
                "files": [
                    {
                        "mimeType": "application/pdf",
                        "url": "https://portale-piao.dfp.gov.it/api/piao/document?f=all.pdf",
                        "fileName": "allegato.pdf",
                        "alias": "allegato",
                    }
                ],
            },
            "linkPiaoPA": {
                "name": "linkPiaoPA",
                "value": "https://example.it/amministrazione-trasparente/piao",
            },
        },
    }


def test_parse_reference_period() -> None:
    assert parse_reference_period("Anno 2025-2027") == (2025, 2027, "2025-2027")
    assert parse_reference_period("PIAO 2026–2028") == (2026, 2028, "2026-2028")
    assert parse_reference_period("") == (None, None, "")


def test_normalise_publication_keeps_approval_separate_from_publication_date() -> None:
    result = normalise_publication(
        sample_record(),
        retrieved_at="2026-09-20T14:00:00+00:00",
    )

    assert result["ipa_code"] == "c_m208"
    assert result["reference_start_year"] == 2025
    assert result["reference_end_year"] == 2027
    assert result["approval_date"] == "2025-06-06"
    assert result["piao_document_file_name"] == "PIAO_2025_2027.pdf"
    assert result["attachment_count"] == 1
    assert result["portal_publication_date"] == ""
    assert result["portal_publication_date_status"] == "not_exposed_by_public_api"


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeSession:
    def __init__(self) -> None:
        self.pages = {
            0: {
                "success": True,
                "result": [{"list": [sample_record(version=1)], "count": 1, "total": 2}],
            },
            1: {
                "success": True,
                "result": [{"list": [sample_record(version=2)], "count": 1, "total": 2}],
            },
        }
        self.requested_pages: list[int] = []

    def get(self, url: str, *, params: dict[str, Any], timeout: float) -> FakeResponse:
        del url, timeout
        page = int(params["page"])
        self.requested_pages.append(page)
        return FakeResponse(self.pages[page])


def test_fetch_publications_paginates_until_total() -> None:
    session = FakeSession()

    records, total = fetch_publications_for_ipa(
        "c_m208",
        session=session,  # type: ignore[arg-type]
        delay_seconds=0,
    )

    assert total == 2
    assert [record["version"] for record in records] == [1, 2]
    assert session.requested_pages == [0, 1]
