from __future__ import annotations

from typing import Any

from segnali_locali_di_trasparenza.piao import (
    expected_catalogue_pages,
    fetch_public_catalogue,
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



class FakeCatalogueSession:
    def __init__(self) -> None:
        municipal_1 = sample_record(version=1)
        municipal_2 = sample_record(version=2)
        other = sample_record(version=1)
        other["administrationIpaCode"] = "other_pa"
        other["administrationName"] = "Other Public Administration"
        other["years"] = "Anno 2026-2028"
        other["content"]["piaoPDF"]["files"][0]["url"] = (
            "https://portale-piao.dfp.gov.it/api/piao/document?f=other.pdf"
        )
        self.pages = {
            0: {
                "success": True,
                "result": [
                    {
                        "list": [municipal_1, other],
                        "count": 2,
                        "total": 3,
                    }
                ],
            },
            1: {
                "success": True,
                "result": [
                    {
                        "list": [municipal_2],
                        "count": 1,
                        "total": 3,
                    }
                ],
            },
        }
        self.params: list[dict[str, Any]] = []

    def get(self, url: str, *, params: dict[str, Any], timeout: float) -> FakeResponse:
        del url, timeout
        self.params.append(dict(params))
        return FakeResponse(self.pages[int(params["page"])])


def test_fetch_public_catalogue_filters_after_full_completeness_check() -> None:
    session = FakeCatalogueSession()

    records, metadata = fetch_public_catalogue(
        session=session,  # type: ignore[arg-type]
        delay_seconds=0,
        keep_ipa_codes={"c_m208"},
    )

    assert len(records) == 2
    assert {record["administrationIpaCode"] for record in records} == {"c_m208"}
    assert metadata == {
        "pages_fetched": 2,
        "expected_pages": 2,
        "page_size": 2,
        "workers": 1,
        "first_total": 3,
        "last_total": 3,
        "unique_catalogue_records_seen": 3,
        "selected_records": 2,
        "filtered_out_records": 1,
    }
    assert session.params == [{"page": 0}, {"page": 1}]



def test_expected_catalogue_pages() -> None:
    assert expected_catalogue_pages(0, 0) == 1
    assert expected_catalogue_pages(6, 6) == 1
    assert expected_catalogue_pages(7, 6) == 2
    assert expected_catalogue_pages(31_147, 6) == 5_192



class PrefixSearchSession:
    def __init__(self) -> None:
        exact = sample_record(version=1)
        exact["administrationIpaCode"] = "c_b9"
        exact["administrationName"] = "Comune Exact"

        prefixed = sample_record(version=1)
        prefixed["administrationIpaCode"] = "c_b900"
        prefixed["administrationName"] = "Comune Prefix"
        prefixed["content"]["piaoPDF"]["files"][0]["url"] = (
            "https://portale-piao.dfp.gov.it/api/piao/document?f=prefix.pdf"
        )

        self.pages = {
            0: {
                "success": True,
                "result": [
                    {
                        "list": [exact, prefixed],
                        "count": 2,
                        "total": 2,
                    }
                ],
            }
        }

    def get(self, url: str, *, params: dict[str, Any], timeout: float) -> FakeResponse:
        del url, timeout
        return FakeResponse(self.pages[int(params["page"])])


def test_per_ipa_lookup_rejects_prefix_matches() -> None:
    records, total = fetch_publications_for_ipa(
        "c_b9",
        session=PrefixSearchSession(),  # type: ignore[arg-type]
        delay_seconds=0,
    )

    assert total == 2
    assert len(records) == 1
    assert records[0]["administrationIpaCode"] == "c_b9"
