from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests


GATEWAY_URL = "https://situas.istat.it/ShibO2Module/api/Report/ReportByUrl"
PUBLISH_BASE = "https://situas-servizi.istat.it/publish"
DEFAULT_TIMEOUT = 60

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Referer": "https://situas.istat.it/web/",
    "language": "IT",
    "User-Agent": (
        "segnali-locali-di-trasparenza/0.1 "
        "(+https://github.com/colazeta/segnali_locali_di_trasparenza)"
    ),
}


class SituasError(RuntimeError):
    """Application or transport error returned by SITUAS."""


@dataclass(frozen=True)
class ReportRequest:
    report_id: int
    url: str
    title: str
    validity: str


def rows(payload: object) -> list[dict[str, object]]:
    if isinstance(payload, dict):
        for key in ("resultset", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def _check_error(payload: object, context: str) -> None:
    if isinstance(payload, dict):
        status = payload.get("status")
        if isinstance(status, int) and status >= 400:
            raise SituasError(
                f"{payload.get('title', 'SITUAS error')} (status {status}; {context})"
            )
        if (
            "message" in payload
            and "resultset" not in payload
            and "items" not in payload
        ):
            raise SituasError(f"{payload['message']} ({context})")

    records = rows(payload)
    if len(records) == 1 and "ERRCODE" in records[0]:
        raise SituasError(f"{records[0]['ERRCODE']} ({context})")


def _decode_json(response: requests.Response, context: str) -> object:
    try:
        payload = json.loads(response.text, strict=False)
    except (json.JSONDecodeError, ValueError) as exc:
        raise SituasError(f"Non-JSON SITUAS response ({context})") from exc
    _check_error(payload, context)
    return payload


class SituasClient:
    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self.session = session or requests.Session()
        self.session.headers.update(HEADERS)
        self.timeout = timeout

    def gateway(self, service: str) -> object:
        try:
            response = self.session.post(
                GATEWAY_URL,
                data=json.dumps({"url": service}),
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise SituasError(f"SITUAS gateway unreachable ({service})") from exc
        return _decode_json(response, service)

    def publish(self, url: str) -> object:
        if not url.startswith(f"{PUBLISH_BASE}/"):
            raise SituasError(f"Unexpected SITUAS publish URL: {url}")
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise SituasError(f"SITUAS publish endpoint unreachable ({url})") from exc
        return _decode_json(response, url)

    def catalog(self) -> list[dict[str, object]]:
        return rows(self.gateway("get_elenco_microservizi"))

    def report_entry(
        self,
        report_id: int,
        *,
        catalog: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        catalog = self.catalog() if catalog is None else catalog
        for entry in catalog:
            if str(entry.get("Id report", "")) == str(report_id):
                return entry
        raise SituasError(f"Report {report_id} not present in SITUAS catalog")

    def report(
        self,
        report_id: int,
        *,
        date: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        catalog: list[dict[str, object]] | None = None,
    ) -> tuple[ReportRequest, list[dict[str, object]]]:
        entry = self.report_entry(report_id, catalog=catalog)
        link = str(entry.get("SPOOL_LINK", ""))
        if not link:
            raise SituasError(f"Report {report_id} has no SPOOL_LINK")

        final_url = apply_dates(
            link,
            date=date,
            date_from=date_from,
            date_to=date_to,
            default_date=validity_end(entry),
        )
        request = ReportRequest(
            report_id=report_id,
            url=final_url,
            title=str(entry.get("Titolo report", "")),
            validity=str(entry.get("Inizio/fine validità report", "")),
        )
        return request, rows(self.publish(final_url))


def validity_end(entry: dict[str, object]) -> str | None:
    value = str(entry.get("Inizio/fine validità report", ""))
    if " - " not in value:
        return None
    end = value.split(" - ", 1)[1].strip()
    return end or None


def apply_dates(
    link: str,
    *,
    date: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    default_date: str | None = None,
) -> str:
    if date and (date_from or date_to):
        raise SituasError("Use date or date_from/date_to, not both")

    parts = urlsplit(link)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    is_range = "pdatada" in query or "pdataa" in query

    if is_range:
        if date:
            raise SituasError("Range report requires date_from/date_to")
        if date_from:
            query["pdatada"] = date_from
        if date_to:
            query["pdataa"] = date_to
        elif default_date:
            query["pdataa"] = default_date
    else:
        if date_from or date_to:
            raise SituasError("Single-date report requires date")
        if date:
            query["pdata"] = date
        elif default_date:
            query["pdata"] = default_date

    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query, safe="/"),
            parts.fragment,
        )
    )
