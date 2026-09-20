from __future__ import annotations

import hashlib
import re
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup


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
    methodology_version: str = "signal001-v1"
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


def normalise_start_url(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if re.match(r"^https?://", value, flags=re.IGNORECASE):
        return value
    return f"https://{value.lstrip('/')}"


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


class PoliteClient:
    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        delay_seconds: float = 0.35,
        timeout_seconds: float = 20,
    ) -> None:
        self.session = session or requests.Session()
        self.delay_seconds = max(delay_seconds, 0)
        self.timeout_seconds = timeout_seconds
        self._last_request_at = 0.0
        self._robots_cache: dict[str, tuple[RobotFileParser | None, str]] = {}
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
    methodology_version: str = "signal001-v1",
    client: PoliteClient | None = None,
    max_link_candidates: int = 4,
) -> DiscoveryResult:
    observed_at = datetime.now(UTC).isoformat()
    start_url = normalise_start_url(institutional_url)

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

    if not start_url:
        result.status = "missing_institutional_url"
        return result

    client = client or PoliteClient()

    allowed, robots_status = client.robots_allowed(start_url)
    result.homepage_robots_status = robots_status
    if not allowed:
        result.status = "robots_disallowed"
        return result

    try:
        home = client.get(start_url)
    except requests.RequestException as exc:
        result.status = "homepage_unreachable"
        result.error = type(exc).__name__
        return result

    result.homepage_final_url = home.url
    result.homepage_http_status = home.status_code

    if home.status_code >= 400:
        result.status = "homepage_http_error"
        return result

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
