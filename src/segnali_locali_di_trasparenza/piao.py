from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass
from collections.abc import Iterable
from datetime import UTC, date, datetime
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .registry import normalise_name


PORTAL_BASE_URL = "https://piao.dfp.gov.it"
PORTAL_INDEX_URL = f"{PORTAL_BASE_URL}/piao"
USER_AGENT = (
    "segnali-locali-di-trasparenza/0.2 "
    "(+https://github.com/colazeta/segnali_locali_di_trasparenza)"
)
PERIOD_RE = re.compile(r"(?P<start>20\d{2})\s*[-–—/]\s*(?P<end>20\d{2})")
NODE_RE = re.compile(r"/node/(?P<node_id>\d+)(?:$|[/?#])", flags=re.IGNORECASE)
ENTITY_CODE_RE = re.compile(
    r"^\s*Piano\s+Integrato\s+(?P<code>[A-Za-z0-9_.-]+)\s+20\d{2}",
    flags=re.IGNORECASE,
)


@dataclass
class PiaoRecord:
    portal_node_id: str
    portal_url: str
    portal_entity_code: str
    administration_name: str
    period_label: str
    period_start_year: int | None
    period_end_year: int | None
    approval_date: str
    portal_published_at: str
    pdf_url: str
    pa_url: str
    fetched_at: str
    source_html_sha256: str
    title: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class PortalClient:
    def __init__(
        self,
        *,
        timeout_seconds: float = 15,
        delay_seconds: float = 0.25,
        retry_total: int = 2,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.delay_seconds = max(delay_seconds, 0)
        self._last_request_at = 0.0
        self.session = requests.Session()
        retry = Retry(
            total=retry_total,
            connect=retry_total,
            read=retry_total,
            status=retry_total,
            allowed_methods=frozenset({"GET"}),
            status_forcelist=(429, 500, 502, 503, 504),
            backoff_factor=0.5,
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
            }
        )

    def get(self, url: str) -> requests.Response:
        remaining = self.delay_seconds - (time.monotonic() - self._last_request_at)
        if remaining > 0:
            time.sleep(remaining)
        response = self.session.get(
            url,
            timeout=self.timeout_seconds,
            allow_redirects=True,
        )
        self._last_request_at = time.monotonic()
        return response


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalise_date(value: str) -> str:
    value = _clean_text(value)
    if not value:
        return ""
    iso_match = re.fullmatch(r"(20\\d{2})-(\\d{2})-(\\d{2})", value[:10])
    if iso_match:
        year, month, day = map(int, iso_match.groups())
        return date(year, month, day).isoformat()

    local_match = re.fullmatch(r"(\\d{2})[-/](\\d{2})[-/](20\\d{2})", value[:10])
    if local_match:
        day, month, year = map(int, local_match.groups())
        return date(year, month, day).isoformat()

    return value


def _field_container(soup: BeautifulSoup, label: str):
    wanted = re.compile(rf"^\s*{re.escape(label)}\s*$", flags=re.IGNORECASE)
    label_node = soup.find(
        lambda tag: getattr(tag, "name", None)
        and _clean_text(tag.get_text(" ", strip=True))
        and wanted.match(_clean_text(tag.get_text(" ", strip=True)))
    )
    if label_node is None:
        return None
    for parent in [label_node.parent, getattr(label_node.parent, "parent", None)]:
        if parent is None:
            continue
        text = _clean_text(parent.get_text(" ", strip=True))
        if label.lower() in text.lower() and len(text) <= 1000:
            return parent
    return label_node.parent


def _field_text(soup: BeautifulSoup, label: str) -> str:
    container = _field_container(soup, label)
    if container is not None:
        text = _clean_text(container.get_text(" ", strip=True))
        text = re.sub(rf"^\s*{re.escape(label)}\s*", "", text, flags=re.IGNORECASE)
        if text:
            return text

    full_text = _clean_text(soup.get_text(" ", strip=True))
    match = re.search(
        rf"\b{re.escape(label)}\b\s+(.+?)(?=\s+(?:Amministrazione|Link PA|Link|Anno|Data Approvazione)\b|$)",
        full_text,
        flags=re.IGNORECASE,
    )
    return _clean_text(match.group(1)) if match else ""


def _field_link(soup: BeautifulSoup, label: str) -> str:
    container = _field_container(soup, label)
    if container is None:
        return ""
    anchor = container.find("a", href=True)
    if anchor is None:
        return ""
    return urljoin(PORTAL_BASE_URL, str(anchor.get("href", "")).strip())


def _published_at(soup: BeautifulSoup) -> str:
    selectors = [
        ("meta", {"property": "article:published_time"}),
        ("meta", {"name": "date"}),
        ("meta", {"itemprop": "datePublished"}),
    ]
    for name, attrs in selectors:
        node = soup.find(name, attrs=attrs)
        if node and node.get("content"):
            return _clean_text(node.get("content"))

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text()
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if isinstance(item, dict) and item.get("datePublished"):
                return _clean_text(item["datePublished"])
    return ""


def parse_piao_page(html: str, page_url: str) -> PiaoRecord:
    soup = BeautifulSoup(html or "", "html.parser")
    heading = soup.find("h1")
    title = _clean_text(
        heading.get_text(" ", strip=True) if heading else (soup.title.string if soup.title else "")
    )

    node_match = NODE_RE.search(page_url)
    node_id = node_match.group("node_id") if node_match else ""

    period_text = _field_text(soup, "Anno")
    period_match = PERIOD_RE.search(period_text) or PERIOD_RE.search(title)
    start_year = int(period_match.group("start")) if period_match else None
    end_year = int(period_match.group("end")) if period_match else None
    period_label = (
        f"{start_year}-{end_year}" if start_year is not None and end_year is not None else period_text
    )

    entity_match = ENTITY_CODE_RE.search(title)
    entity_code = entity_match.group("code") if entity_match else ""

    pdf_url = _field_link(soup, "Link")
    if not pdf_url:
        document_link = soup.find("a", href=re.compile(r"/data/documents/", re.IGNORECASE))
        if document_link:
            pdf_url = urljoin(PORTAL_BASE_URL, str(document_link.get("href", "")).strip())

    pa_url = _field_link(soup, "Link PA")

    return PiaoRecord(
        portal_node_id=node_id,
        portal_url=page_url,
        portal_entity_code=entity_code,
        administration_name=_field_text(soup, "Amministrazione"),
        period_label=period_label,
        period_start_year=start_year,
        period_end_year=end_year,
        approval_date=_normalise_date(_field_text(soup, "Data Approvazione")),
        portal_published_at=_published_at(soup),
        pdf_url=pdf_url,
        pa_url=pa_url,
        fetched_at=datetime.now(UTC).isoformat(),
        source_html_sha256=_sha256_text(html or ""),
        title=title,
    )


def extract_plan_urls(html: str, base_url: str = PORTAL_INDEX_URL) -> list[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    urls: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        absolute = urljoin(base_url, str(anchor.get("href", "")).strip())
        parsed = urlparse(absolute)
        if parsed.netloc.lower() != urlparse(PORTAL_BASE_URL).netloc.lower():
            continue
        if NODE_RE.search(parsed.path):
            urls.add(f"{parsed.scheme}://{parsed.netloc}{parsed.path}")
    return sorted(urls)


def discover_plan_urls(
    client: PortalClient,
    *,
    max_pages: int = 2000,
    empty_page_limit: int = 2,
) -> list[str]:
    urls: set[str] = set()
    consecutive_empty = 0

    for page in range(max_pages):
        url = PORTAL_INDEX_URL if page == 0 else f"{PORTAL_INDEX_URL}?page={page}"
        response = client.get(url)
        if response.status_code >= 400:
            raise RuntimeError(f"PIAO index returned HTTP {response.status_code}: {url}")

        discovered = set(extract_plan_urls(response.text, response.url))
        new_urls = discovered - urls
        urls.update(discovered)

        if new_urls:
            consecutive_empty = 0
        else:
            consecutive_empty += 1

        if consecutive_empty >= empty_page_limit:
            break

    return sorted(urls)


def fetch_records(
    client: PortalClient,
    urls: Iterable[str],
) -> list[PiaoRecord]:
    records: list[PiaoRecord] = []
    for url in urls:
        response = client.get(url)
        if response.status_code >= 400:
            continue
        record = parse_piao_page(response.text, response.url)
        if record.period_start_year is None and not record.administration_name:
            continue
        records.append(record)
    return records


def _municipality_aliases(row: pd.Series) -> set[str]:
    aliases = {
        normalise_name(row.get("name", "")),
        normalise_name(row.get("name_full", "")),
        normalise_name(row.get("name_other", "")),
        normalise_name(row.get("ipa_name", "")),
    }
    return {alias for alias in aliases if alias}


def link_plans_to_municipalities(
    records: pd.DataFrame,
    registry: pd.DataFrame,
) -> pd.DataFrame:
    registry = registry.copy().fillna("")
    records = records.copy().fillna("")
    registry["ipa_code_key"] = registry["ipa_code"].astype(str).str.lower().str.strip()

    code_to_istat = (
        registry.loc[registry["ipa_code_key"].ne(""), ["ipa_code_key", "istat_code"]]
        .drop_duplicates("ipa_code_key")
        .set_index("ipa_code_key")["istat_code"]
        .to_dict()
    )

    alias_to_codes: dict[str, list[str]] = {}
    for _, row in registry.iterrows():
        for alias in _municipality_aliases(row):
            alias_to_codes.setdefault(alias, []).append(str(row["istat_code"]))

    linked_codes: list[str] = []
    bases: list[str] = []
    for _, plan in records.iterrows():
        entity_code = str(plan.get("portal_entity_code", "")).lower().strip()
        if entity_code and entity_code in code_to_istat:
            linked_codes.append(str(code_to_istat[entity_code]))
            bases.append("ipa_code")
            continue

        admin_alias = normalise_name(plan.get("administration_name", ""))
        candidates = sorted(set(alias_to_codes.get(admin_alias, [])))
        if len(candidates) == 1:
            linked_codes.append(candidates[0])
            bases.append("administration_name")
        else:
            linked_codes.append("")
            bases.append("unmatched" if not candidates else "ambiguous_name")

    records["istat_code"] = linked_codes
    records["municipality_match_basis"] = bases
    return records


def build_municipality_piao_view(
    linked_records: pd.DataFrame,
    registry: pd.DataFrame,
) -> pd.DataFrame:
    registry = registry.copy().fillna("")
    plans = linked_records[linked_records["istat_code"].astype(str).ne("")].copy()

    if plans.empty:
        out = registry[["istat_code", "ipa_code", "name", "region_name", "supra_name"]].copy()
        out["piao_present_any"] = False
        out["piao_count"] = 0
        out["piao_latest_period"] = ""
        out["piao_latest_approval_date"] = ""
        out["piao_latest_portal_published_at"] = ""
        out["piao_latest_portal_url"] = ""
        out["piao_latest_pdf_url"] = ""
        out["piao_latest_pa_url"] = ""
        return out

    plans["_start"] = pd.to_numeric(plans["period_start_year"], errors="coerce").fillna(-1)
    plans["_approval"] = pd.to_datetime(plans["approval_date"], errors="coerce")
    plans = plans.sort_values(
        ["istat_code", "_start", "_approval", "portal_node_id"],
        ascending=[True, False, False, False],
    )
    latest = plans.drop_duplicates("istat_code", keep="first").set_index("istat_code")
    counts = plans.groupby("istat_code").size().rename("piao_count")

    out = registry[["istat_code", "ipa_code", "name", "region_name", "supra_name"]].copy()
    out = out.merge(counts, how="left", left_on="istat_code", right_index=True)
    out["piao_count"] = out["piao_count"].fillna(0).astype(int)
    out["piao_present_any"] = out["piao_count"].gt(0)

    mapping = {
        "piao_latest_period": "period_label",
        "piao_latest_approval_date": "approval_date",
        "piao_latest_portal_published_at": "portal_published_at",
        "piao_latest_portal_url": "portal_url",
        "piao_latest_pdf_url": "pdf_url",
        "piao_latest_pa_url": "pa_url",
    }
    for target, source in mapping.items():
        out[target] = out["istat_code"].map(latest[source]).fillna("")

    return out
