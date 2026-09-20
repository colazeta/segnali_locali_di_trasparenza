from __future__ import annotations

import json
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://portale-piao.dfp.gov.it/"
LOOSE_API_RE = re.compile(r"/api/[A-Za-z0-9_?&=./{}:$-]+")


def main() -> None:
    session = requests.Session()
    session.headers.update({"User-Agent": "segnali-locali-di-trasparenza/0.1"})

    response = session.get(BASE_URL, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    script_urls = [
        urljoin(BASE_URL, tag["src"])
        for tag in soup.find_all("script", src=True)
        if str(tag["src"]).strip()
    ]

    endpoints: set[str] = set()
    bundles: list[dict[str, object]] = []

    for script_url in script_urls:
        item: dict[str, object] = {"url": script_url}
        try:
            bundle = session.get(script_url, timeout=60)
            item["status_code"] = bundle.status_code
            bundle.raise_for_status()
        except requests.RequestException as exc:
            item["error"] = type(exc).__name__
            bundles.append(item)
            continue

        text = bundle.text
        item["bytes"] = len(bundle.content)
        matches = sorted(set(LOOSE_API_RE.findall(text)))
        endpoints.update(matches)
        contexts = []
        for endpoint in matches:
            start = 0
            while True:
                index = text.find(endpoint, start)
                if index < 0:
                    break
                contexts.append(
                    {
                        "endpoint": endpoint,
                        "context": text[max(0, index - 800) : index + 1400],
                    }
                )
                start = index + len(endpoint)
        for needle in [
            "Access token missing in cookies",
            "accessToken",
            "access_token",
            "GUEST",
            "getBackendInfo",
            "piaos:{path",
            "document.cookie",
            "credentials",
        ]:
            start = 0
            while True:
                index = text.find(needle, start)
                if index < 0:
                    break
                contexts.append(
                    {
                        "needle": needle,
                        "context": text[max(0, index - 1200) : index + 2200],
                    }
                )
                start = index + len(needle)
        if contexts:
            item["contexts"] = contexts
        bundles.append(item)

    init_sequence = []
    for path in [
        "/api/getBackendInfo",
        "/api/user",
        "/api/administrations/details?search=Lamezia&limit=5",
        "/api/administration?search=Lamezia&limit=5",
        "/api/piaos?search=Lamezia&limit=5",
    ]:
        url = "https://portale-piao.dfp.gov.it" + path
        step = {"url": url, "cookies_before": sorted(session.cookies.get_dict())}
        try:
            step_response = session.get(url, timeout=60)
            step["status_code"] = step_response.status_code
            step["content_type"] = step_response.headers.get("content-type", "")
            step["sample"] = step_response.text[:3000]
            step["cookies_after"] = sorted(session.cookies.get_dict())
        except requests.RequestException as exc:
            step["error"] = type(exc).__name__
        init_sequence.append(step)

    probes = []
    for host in ["https://portale-piao.dfp.gov.it", "https://piao.dfp.gov.it"]:
        for path in [
            "/api/piaos?limit=3",
            "/api/piao/schema?limit=3",
            "/api/piao/export?years=2026-2028",
        ]:
            url = host + path
            probe = {"url": url}
            try:
                probe_response = session.get(url, timeout=60)
                probe["status_code"] = probe_response.status_code
                probe["content_type"] = probe_response.headers.get("content-type", "")
                probe["content_disposition"] = probe_response.headers.get("content-disposition", "")
                probe["sample"] = probe_response.text[:2000]
            except requests.RequestException as exc:
                probe["error"] = type(exc).__name__
            probes.append(probe)

    public_catalog = {}
    try:
        public_response = session.get("https://piao.dfp.gov.it/piao", timeout=60)
        public_catalog["status_code"] = public_response.status_code
        public_catalog["final_url"] = public_response.url
        public_catalog["content_type"] = public_response.headers.get("content-type", "")
        public_soup = BeautifulSoup(public_response.text, "html.parser")
        public_catalog["iframes"] = [
            {"src": tag.get("src", ""), "title": tag.get("title", "")}
            for tag in public_soup.find_all("iframe")
        ]
        public_catalog["scripts"] = [
            tag.get("src", "")
            for tag in public_soup.find_all("script", src=True)
        ]
        public_catalog["links"] = [
            tag.get("href", "")
            for tag in public_soup.find_all("a", href=True)
            if "piao" in str(tag.get("href", "")).lower()
            or "portale" in str(tag.get("href", "")).lower()
        ][:50]
        public_catalog["html_sample"] = public_response.text[:10000]
    except requests.RequestException as exc:
        public_catalog["error"] = type(exc).__name__

    result = {
        "base_url": BASE_URL,
        "html_status_code": response.status_code,
        "script_count": len(script_urls),
        "bundles": bundles,
        "api_endpoints": sorted(endpoints),
        "root_cookie_names": sorted(session.cookies.get_dict()),
        "init_sequence": init_sequence,
        "probes": probes,
        "public_catalog": public_catalog,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
