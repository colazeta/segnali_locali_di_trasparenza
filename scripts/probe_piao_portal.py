from __future__ import annotations

import json
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://portale-piao.dfp.gov.it/"
LOOSE_API_RE = re.compile(r"/api/piao/[A-Za-z0-9_?&=./{}:$-]+")


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
        if contexts:
            item["contexts"] = contexts
        bundles.append(item)

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

    result = {
        "base_url": BASE_URL,
        "html_status_code": response.status_code,
        "script_count": len(script_urls),
        "bundles": bundles,
        "api_endpoints": sorted(endpoints),
        "probes": probes,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
