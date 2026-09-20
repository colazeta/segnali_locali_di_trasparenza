from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


PUBLIC_PIAO_API = "https://piao.dfp.gov.it/api/piao"
PUBLIC_ADMIN_API = "https://piao.dfp.gov.it/api/administrations"
PORTAL_CATALOGUE_URL = "https://piao.dfp.gov.it/piao"
USER_AGENT = (
    "segnali-locali-di-trasparenza/0.1 "
    "(+https://github.com/colazeta/segnali_locali_di_trasparenza)"
)
REFERENCE_PERIOD_RE = re.compile(r"(?P<start>20\d{2})\s*[-–]\s*(?P<end>20\d{2})")


class PiaoApiError(RuntimeError):
    pass


def make_session(*, retries: int = 2, backoff_factor: float = 0.5) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        allowed_methods=frozenset({"GET"}),
        status_forcelist=(429, 500, 502, 503, 504),
        backoff_factor=backoff_factor,
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/plain;q=0.9,*/*;q=0.5",
        }
    )
    return session


def parse_reference_period(value: object) -> tuple[int | None, int | None, str]:
    text = "" if value is None else str(value).strip()
    match = REFERENCE_PERIOD_RE.search(text)
    if not match:
        return None, None, text
    start = int(match.group("start"))
    end = int(match.group("end"))
    return start, end, f"{start}-{end}"


def _content_value(content: dict[str, Any], key: str) -> Any:
    item = content.get(key)
    if not isinstance(item, dict):
        return ""
    return item.get("value", "")


def _content_files(content: dict[str, Any], key: str) -> list[dict[str, str]]:
    item = content.get(key)
    if not isinstance(item, dict):
        return []
    files = item.get("files")
    if not isinstance(files, list):
        return []

    normalised: list[dict[str, str]] = []
    for file in files:
        if not isinstance(file, dict):
            continue
        normalised.append(
            {
                "url": str(file.get("url") or ""),
                "file_name": str(file.get("fileName") or ""),
                "alias": str(file.get("alias") or ""),
                "mime_type": str(file.get("mimeType") or ""),
            }
        )
    return normalised


def normalise_employee_flag(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("value") or value.get("label") or "").strip()
    return str(value or "").strip()


def publication_id(record: dict[str, Any]) -> str:
    content = record.get("content") if isinstance(record.get("content"), dict) else {}
    piao_files = _content_files(content, "piaoPDF")
    primary_url = piao_files[0]["url"] if piao_files else ""
    raw = "|".join(
        [
            str(record.get("administrationIpaCode") or ""),
            str(record.get("years") or ""),
            str(record.get("version") or ""),
            primary_url,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def normalise_publication(record: dict[str, Any], *, retrieved_at: str) -> dict[str, Any]:
    content = record.get("content") if isinstance(record.get("content"), dict) else {}
    start_year, end_year, reference_period = parse_reference_period(record.get("years"))

    piao_files = _content_files(content, "piaoPDF")
    approval_files = _content_files(content, "atto")
    attachments = _content_files(content, "attachments")

    piao = piao_files[0] if piao_files else {}
    approval_act = approval_files[0] if approval_files else {}

    return {
        "piao_publication_id": publication_id(record),
        "ipa_code": str(record.get("administrationIpaCode") or ""),
        "portal_administration_name": str(record.get("administrationName") or ""),
        "version": record.get("version"),
        "reference_label": str(record.get("years") or ""),
        "reference_period": reference_period,
        "reference_start_year": start_year,
        "reference_end_year": end_year,
        "approval_date": str(_content_value(content, "approvalDate") or ""),
        "approval_act_reference": str(_content_value(content, "estremiAtto") or ""),
        "approval_authority": str(_content_value(content, "autorita") or ""),
        "employees_under_50": normalise_employee_flag(
            _content_value(content, "nDipendenti")
        ),
        "piao_document_url": str(piao.get("url") or ""),
        "piao_document_file_name": str(piao.get("file_name") or ""),
        "piao_document_mime_type": str(piao.get("mime_type") or ""),
        "approval_act_url": str(approval_act.get("url") or ""),
        "approval_act_file_name": str(approval_act.get("file_name") or ""),
        "institutional_piao_url": str(_content_value(content, "linkPiaoPA") or ""),
        "attachment_count": len(attachments),
        "attachments_json": json.dumps(attachments, ensure_ascii=False, sort_keys=True),
        # The current public API does not expose a portal publication timestamp.
        "portal_publication_date": "",
        "portal_publication_date_status": "not_exposed_by_public_api",
        "retrieved_at": retrieved_at,
        "source_catalogue_url": PORTAL_CATALOGUE_URL,
    }


def _request_page(
    session: requests.Session,
    *,
    ipa_code: str,
    page: int,
    timeout: float,
) -> tuple[list[dict[str, Any]], int, int]:
    response = session.get(
        PUBLIC_PIAO_API,
        params={"ipaCode": ipa_code, "page": page},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()

    if not isinstance(payload, dict) or not payload.get("success"):
        message = payload.get("message") if isinstance(payload, dict) else None
        raise PiaoApiError(f"PIAO public API returned an unsuccessful payload: {message}")

    result = payload.get("result")
    if not isinstance(result, list) or not result or not isinstance(result[0], dict):
        raise PiaoApiError("PIAO public API returned an unexpected result container")

    container = result[0]
    records = container.get("list")
    if not isinstance(records, list):
        raise PiaoApiError("PIAO public API result does not contain a list")

    total = int(container.get("total") or 0)
    count = int(container.get("count") or len(records))
    clean_records = [record for record in records if isinstance(record, dict)]
    return clean_records, total, count


def fetch_publications_for_ipa(
    ipa_code: str,
    *,
    session: requests.Session | None = None,
    timeout: float = 20,
    delay_seconds: float = 0.15,
    max_pages: int = 100,
) -> tuple[list[dict[str, Any]], int]:
    ipa_code = str(ipa_code or "").strip()
    if not ipa_code:
        return [], 0

    session = session or make_session()
    records: list[dict[str, Any]] = []
    total = 0

    for page in range(max_pages):
        page_records, total, _ = _request_page(
            session,
            ipa_code=ipa_code,
            page=page,
            timeout=timeout,
        )
        records.extend(page_records)

        if not page_records or len(records) >= total:
            break

        if delay_seconds > 0:
            time.sleep(delay_seconds)
    else:
        raise PiaoApiError(
            f"PIAO pagination exceeded max_pages={max_pages} for IPA code {ipa_code}"
        )

    # Defensive de-duplication in case a changing public page overlaps while paginating.
    deduplicated: dict[str, dict[str, Any]] = {}
    for record in records:
        deduplicated[publication_id(record)] = record

    return list(deduplicated.values()), total


def deterministic_shard(
    frame: pd.DataFrame,
    *,
    shard_index: int,
    shard_count: int,
) -> pd.DataFrame:
    if shard_count <= 0:
        raise ValueError("shard_count must be greater than zero")
    if shard_index < 0 or shard_index >= shard_count:
        raise ValueError("shard_index must be in [0, shard_count)")

    working = frame.copy()
    working["_shard"] = working["istat_code"].map(
        lambda code: int(hashlib.sha256(str(code).encode("utf-8")).hexdigest(), 16)
        % shard_count
    )
    return (
        working.loc[working["_shard"].eq(shard_index)]
        .drop(columns=["_shard"])
        .sort_values(["region_code", "istat_code"])
        .reset_index(drop=True)
    )


def api_query_url(*, ipa_code: str, page: int = 0) -> str:
    return f"{PUBLIC_PIAO_API}?{urlencode({'ipaCode': ipa_code, 'page': page})}"


def collected_at() -> str:
    return datetime.now(UTC).isoformat()
