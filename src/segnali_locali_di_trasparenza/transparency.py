from __future__ import annotations

import hashlib
import re
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


USER_AGENT = (
    "segnali-locali-di-trasparenza/0.1 "
    "(+https://github.com/colazeta/segnali_locali_di_trasparenza)"
)
ROBOTS_USER_AGENT = "segnali-locali-di-trasparenza"
TRANSPARENCY_RE = re.compile(
    r"amministrazione[\s/_-]*trasparente|trasparenza|transparenz",
    flags=re.IGNORECASE,
)
DEFAULT_FALLBACK_PATHS = (
    "/Amministrazione-Trasparente",
    "/amministrazione-trasparente",
    "/Amministrazione_Trasparente",
)


@dataclass(frozen=True)
class Candidate:
    url: str
    anchor_text: str
    score: int
    discovery_method: str


@dataclass
class DiscoveryResult:
    istat_code: str
    ipa_code: str
    municipality_name: str
    institutional_url: str
    observed_at: str
    status: str
    collector: str = "transparency_entrypoint"
    collector_version: str = ""
    methodology_version: str = "signal001-v2"
    homepage_final_url: str = ""
    homepage_http_status: int | None = None
    homepage_robots_status: str = ""
    transparency_url: str = ""
    transparency_http_status: int | None = None
    transparency_robots_status: str = ""
    discovery_method: str = ""
    anchor_text: str = ""
    evidence_sha256: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def start_url_candidates(value: str) -> list[str]:
    """Return bounded start URLs, preferring HTTPS for scheme-less IPA values."""
    value = (value or "").strip()
    if not value:
        return []
    if re.match(r"^https?://", value, flags=re.IGNORECASE):
        return [value]
    host = value.lstrip("/")
    return [f"https://{host}", f"http://{host}"]


def normalise_start_url(value: str) -> str:
    candidates = start_url_candidates(value)
    return candidates[0] if candidates else ""


def _same_host(url_a: str, url_b: str) -> bool:
    return urlparse(url_a).netloc.lower() == urlparse(url_b).netloc.lower()


def extract_candidates(html: str, base_url: str) -> list[Candidate]:
    soup = BeautifulSoup(html or "", "html.parser")
    seen: dict[str, Candidate] = {}

    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href", "")).strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue

        text = " ".join(anchor.stripped_strings).strip()
        absolute = urljoin(base_url, href)
        signal = f"{text} {href}"

        if not TRANSPARENCY_RE.search(signal):
            continue

        score = 0
        if re.search(r"amministrazione\s*trasparente", text, flags=re.IGNORECASE):
            score += 100
        elif "trasparen" in text.lower() or "transparen" in text.lower():
            score += 60

        if re.search(r"amministrazione[-_/ ]*trasparente", href, flags=re.IGNORECASE):
            score += 80
        elif "trasparen" in href.lower() or "transparen" in href.lower():
            score += 40

        if _same_host(base_url, absolute):
            score += 10

        candidate = Candidate(
            url=absolute,
            anchor_text=text,
            score=score,
            discovery_method="homepage_link",
        )
        previous = seen.get(absolute)
        if previous is None or candidate.score > previous.score:
            seen[absolute] = candidate

    return sorted(seen.values(), key=lambda item: (-item.score, item.url))


def page_looks_like_transparency(html: str, url: str) -> bool:
    soup = BeautifulSoup(html or "", "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    headings = " ".join(
        element.get_text(" ", strip=True)
        for element in soup.find_all(["h1", "h2"], limit=8)
    )
    probe = f"{title} {headings} {url}"
    return bool(TRANSPARENCY_RE.search(probe))


def deterministic_region_sample(frame: pd.DataFrame, per_region: int) -> pd.DataFrame:
    """Stable technical sample by region; not intended for statistical inference."""
    if per_region <= 0:
        raise ValueError("per_region must be greater than zero")

    sampled: list[pd.DataFrame] = []
    working = frame.copy()
    working["_sample_key"] = working["istat_code"].map(
        lambda code: hashlib.sha256(str(code).encode("utf-8")).hexdigest()
    )

    for _, group in working.groupby("region_code", sort=True):
        sampled.append(group.sort_values("_sample_key").head(min(per_region, len(group))))

    return (
        pd.concat(sampled, ignore_index=True)
        .drop(columns=["_sample_key"])
        .sort_values(["region_code", "istat_code"])
        .reset_index(drop=True)
    )


def deterministic_shard(
    frame: pd.DataFrame,
    *,
    shard_index: int,
    shard_count: int,
) -> pd.DataFrame:
    """Partition municipalities deterministically for bounded parallel collection."""
    if shard_count <= 0:
        raise ValueError("shard_count must be greater than zero")
    if shard_index < 0 or shard_index >= shard_count:
        raise ValueError("shard_index must be in [0, shard_count)")

    working = frame.copy()
    working["_shard"] = working["istat_code"].map(
        lambda code: int(
            hashlib.sha256(str(code).encode("utf-8")).hexdigest(),
            16,
        )
        % shard_count
    )
    return (
        working.loc[working["_shard"].eq(shard_index)]
        .drop(columns=["_shard"])
        .sort_values(["region_code", "istat_code"])
        .reset_index(drop=True)
    )


class PoliteClient:
    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        delay_seconds: float = 0.35,
        timeout_seconds: float = 20,
        retry_total: int = 2,
        retry_backoff_factor: float = 0.75,
    ) -> None:
        self.session = session or requests.Session()
        self.delay_seconds = max(delay_seconds, 0)
        self.timeout_seconds = timeout_seconds
        self._last_request_at = 0.0
        self._robots_cache: dict[str, tuple[RobotFileParser | None, str]] = {}

        retry = Retry(
            total=retry_total,
            connect=retry_total,
            read=retry_total,
            status=retry_total,
            allowed_methods=frozenset({"GET"}),
            status_forcelist=(429, 500, 502, 503, 504),
            backoff_factor=retry_backoff_factor,
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
        elapsed = time.monotonic() - self._last_request_at
        remaining = self.delay_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)

        response = self.session.get(
            url,
            timeout=self.timeout_seconds,
            allow_redirects=True,
        )
        self._last_request_at = time.monotonic()
        return response

    def robots_allowed(self, target_url: str) -> tuple[bool, str]:
        parsed = urlparse(target_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        cached = self._robots_cache.get(origin)

        if cached is None:
            robots_url = f"{origin}/robots.txt"
            try:
                response = self.get(robots_url)
            except requests.RequestException:
                cached = (None, "robots_unavailable")
            else:
                if response.status_code >= 400:
                    cached = (None, f"robots_http_{response.status_code}")
                else:
                    parser = RobotFileParser()
                    parser.set_url(robots_url)
                    parser.parse(response.text.splitlines())
                    cached = (parser, "loaded")
            self._robots_cache[origin] = cached

        parser, status = cached
        if parser is None:
            return True, status

        allowed = parser.can_fetch(ROBOTS_USER_AGENT, target_url)
        return allowed, "allowed" if allowed else "disallowed"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def discover_transparency(
    *,
    istat_code: str,
    ipa_code: str,
    municipality_name: str,
    institutional_url: str,
    collector_version: str = "",
    methodology_version: str = "signal001-v2",
    client: PoliteClient | None = None,
    max_link_candidates: int = 4,
) -> DiscoveryResult:
    observed_at = datetime.now(UTC).isoformat()
    start_urls = start_url_candidates(institutional_url)

    result = DiscoveryResult(
        istat_code=istat_code,
        ipa_code=ipa_code,
        municipality_name=municipality_name,
        institutional_url=institutional_url,
        observed_at=observed_at,
        status="not_started",
        collector_version=collector_version,
        methodology_version=methodology_version,
    )

    if not start_urls:
        result.status = "missing_institutional_url"
        return result

    client = client or PoliteClient()
    home = None
    last_error = ""
    last_http_status = None

    for start_url in start_urls:
        allowed, robots_status = client.robots_allowed(start_url)
        result.homepage_robots_status = robots_status
        if not allowed:
            result.status = "robots_disallowed"
            return result

        try:
            candidate_home = client.get(start_url)
        except requests.RequestException as exc:
            last_error = type(exc).__name__
            continue

        last_http_status = candidate_home.status_code
        if candidate_home.status_code >= 400:
            continue

        home = candidate_home
        break

    if home is None:
        result.error = last_error
        result.homepage_http_status = last_http_status
        result.status = (
            "homepage_http_error" if last_http_status is not None else "homepage_unreachable"
        )
        return result

    result.homepage_final_url = home.url
    result.homepage_http_status = home.status_code

    candidates = extract_candidates(home.text, home.url)[:max_link_candidates]

    if not candidates:
        candidates = [
            Candidate(
                url=urljoin(home.url, path),
                anchor_text="",
                score=0,
                discovery_method="fallback_path",
            )
            for path in DEFAULT_FALLBACK_PATHS
        ]

    any_candidate_reachable = False
    any_candidate_disallowed = False

    for candidate in candidates:
        allowed, candidate_robots = client.robots_allowed(candidate.url)
        if not allowed:
            any_candidate_disallowed = True
            continue

        try:
            response = client.get(candidate.url)
        except requests.RequestException:
            continue

        if response.status_code >= 400:
            continue

        any_candidate_reachable = True
        if not page_looks_like_transparency(response.text, response.url):
            continue

        result.status = "found"
        result.transparency_url = response.url
        result.discovery_method = candidate.discovery_method
        result.anchor_text = candidate.anchor_text
        result.transparency_http_status = response.status_code
        result.evidence_sha256 = _sha256_text(response.text)
        result.transparency_robots_status = candidate_robots
        return result

    if any_candidate_reachable:
        result.status = "candidate_not_confirmed"
    elif any_candidate_disallowed:
        result.status = "candidate_robots_disallowed"
    else:
        result.status = "not_found"

    return result
