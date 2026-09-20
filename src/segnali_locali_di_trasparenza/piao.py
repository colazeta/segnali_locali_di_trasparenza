from __future__ import annotations

import hashlib
import re
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from urllib.parse import urlencode, urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


PORTAL_BASE = "https://piao.dfp.gov.it"
PIAO_LIST_PATH = "/piao"
USER_AGENT = (
    "segnali-locali-di-trasparenza/0.2 "
    "(+https://github.com/colazeta/segnali_locali_di_trasparenza)"
)
NODE_RE = re.compile(r"^/node/(\d+)(?:$|[/?#])", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(20\d{2})\s*[-–/]\s*(20\d{2})\b")
IPA_FROM_TITLE_RE = re.compile(
    r"^\s*Piano\s+Integrato\s+([^\s]+)\s+(20\d{2}\s*[-–/]\s*20\d{2})",
    re.IGNORECASE,
)


@dataclass
class PiaoRecord:
    portal_node_id: str
    portal_url: str
    ipa_code: str
    administration_name: str
    reference_period: str
    reference_start_year: int | None
    reference_end_year: int | None
    approval_date: str
    portal_published_at: str
    pdf_url: str
    pa_url: str
    observed_at: str
    source: str = "Portale PIAO - Dipartimento della Funzione Pubblica"
    collector_version: str = ""
    methodology_version: str = "piao001-v1"
    evidence_sha256: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class PortalClient:
    def __init__(
        self,
        *,
        delay_seconds: float = 0.4,
        timeout_seconds: float = 12,
        retry_total: int = 1,
        session: requests.Session | None = None,
    ) -> None:
        self.delay_seconds = max(0.0, delay_seconds)
        self.timeout_seconds = timeout_seconds
        self._last_request_at = 0.0
        self.session = session or requests.Session()
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
        response = self.session.get(url, timeout=self.timeout_seconds, allow_redirects=True)
        self._last_request_at = time.monotonic()
        return response


def piao_search_url(ipa_code: str, page: int = 0) -> str:
    query = urlencode(
        {
            "field_administration_ipa_value": ipa_code,
            "name": "",
            "page": page,
        }
    )
    return f"{PORTAL_BASE}{PIAO_LIST_PATH}?{query}"


def extract_node_urls(html: str, base_url: str = PORTAL_BASE) -> list[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    urls: dict[str, str] = {}
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href", "")).strip()
        match = NODE_RE.match(href)
        if not match:
            continue
        node_id = match.group(1)
        urls[node_id] = urljoin(base_url, href)
    return [urls[key] for key in sorted(urls, key=int)]


def _normalise_period(value: str) -> tuple[str, int | None, int | None]:
    match = YEAR_RE.search(value or "")
    if not match:
        return (value.strip(), None, None)
    start, end = int(match.group(1)), int(match.group(2))
    return (f"{start}-{end}", start, end)


def _meta_publication_date(soup: BeautifulSoup) -> str:
    selectors = (
        ('meta[property="article:published_time"]', "content"),
        ('meta[name="date"]', "content"),
        ('meta[name="dcterms.date"]', "content"),
        ('meta[property="og:published_time"]', "content"),
    )
    for selector, attr in selectors:
        node = soup.select_one(selector)
        if node and node.get(attr):
            return str(node.get(attr)).strip()
    time_node = soup.find("time", attrs={"datetime": True})
    if time_node:
        return str(time_node.get("datetime", "")).strip()
    return ""


def _label_value(lines: list[str], label: str) -> str:
    wanted = label.casefold()
    for index, line in enumerate(lines[:-1]):
        if line.casefold() == wanted:
            return lines[index + 1].strip()
    return ""


def parse_piao_detail(
    html: str,
    url: str,
    *,
    observed_at: str | None = None,
    collector_version: str = "",
) -> PiaoRecord:
    soup = BeautifulSoup(html or "", "html.parser")
    title_node = soup.find("h1")
    title = title_node.get_text(" ", strip=True) if title_node else ""
    lines = [line.strip() for line in soup.stripped_strings if line.strip()]

    node_match = re.search(r"/node/(\d+)", url)
    node_id = node_match.group(1) if node_match else ""

    administration = _label_value(lines, "Amministrazione")
    period_raw = _label_value(lines, "Anno")
    approval_date = _label_value(lines, "Data Approvazione")
    period, start_year, end_year = _normalise_period(period_raw or title)

    ipa_code = ""
    title_match = IPA_FROM_TITLE_RE.search(title)
    if title_match:
        ipa_code = title_match.group(1).strip()

    pdf_url = ""
    pa_url = ""
    for anchor in soup.find_all("a", href=True):
        text = " ".join(anchor.stripped_strings).strip().casefold()
        href = urljoin(url, str(anchor.get("href", "")).strip())
        if "pdf del piano" in text and not pdf_url:
            pdf_url = href
        elif "link del piao" in text and not pa_url:
            pa_url = href

    evidence = hashlib.sha256((html or "").encode("utf-8", errors="replace")).hexdigest()
    return PiaoRecord(
        portal_node_id=node_id,
        portal_url=url,
        ipa_code=ipa_code,
        administration_name=administration,
        reference_period=period,
        reference_start_year=start_year,
        reference_end_year=end_year,
        approval_date=approval_date,
        portal_published_at=_meta_publication_date(soup),
        pdf_url=pdf_url,
        pa_url=pa_url,
        observed_at=observed_at or datetime.now(UTC).isoformat(),
        collector_version=collector_version,
        evidence_sha256=evidence,
    )


def discover_piao_for_ipa(
    ipa_code: str,
    *,
    client: PortalClient,
    collector_version: str = "",
    max_pages: int = 20,
) -> list[PiaoRecord]:
    """Discover all PIAO detail records returned by the official portal for one IPA code."""
    node_urls: list[str] = []
    seen_nodes: set[str] = set()

    for page in range(max_pages):
        response = client.get(piao_search_url(ipa_code, page=page))
        if response.status_code >= 400:
            break
        page_urls = extract_node_urls(response.text, response.url)
        new_urls = [
            item
            for item in page_urls
            if (match := re.search(r"/node/(\d+)", item))
            and match.group(1) not in seen_nodes
        ]
        if not new_urls:
            break
        for item in new_urls:
            match = re.search(r"/node/(\d+)", item)
            if match:
                seen_nodes.add(match.group(1))
                node_urls.append(item)

    records: list[PiaoRecord] = []
    for node_url in node_urls:
        response = client.get(node_url)
        if response.status_code >= 400:
            continue
        record = parse_piao_detail(
            response.text,
            response.url,
            collector_version=collector_version,
        )
        # The portal filter is authoritative for the searched IPA. Some historical
        # page titles are inconsistent, so fill only when the title did not expose it.
        if not record.ipa_code:
            record.ipa_code = ipa_code
        records.append(record)

    return records
