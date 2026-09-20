from __future__ import annotations

import re
from urllib.parse import urljoin

import requests


ROOT = "https://portale-piao.dfp.gov.it/"
API_RE = re.compile(r"""(?P<q>["'`])(?P<path>/api/[A-Za-z0-9_?&=./{}:\\-]+)(?P=q)""")
SCRIPT_RE = re.compile(r"""<script[^>]+src=["']([^"']+)["']""", re.IGNORECASE)


def main() -> None:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (compatible; SegnaliLocaliDiTrasparenza/0.2; "
                "+https://github.com/colazeta/segnali_locali_di_trasparenza)"
            )
        }
    )

    response = session.get(ROOT, timeout=20)
    print(f"ROOT status={response.status_code} type={response.headers.get('content-type')}")
    response.raise_for_status()

    scripts = [urljoin(response.url, value) for value in SCRIPT_RE.findall(response.text)]
    print(f"scripts={len(scripts)}")
    for url in scripts:
        print(f"SCRIPT {url}")
        bundle = session.get(url, timeout=30)
        print(
            f"  status={bundle.status_code} type={bundle.headers.get('content-type')} "
            f"bytes={len(bundle.content)}"
        )
        if bundle.status_code >= 400:
            continue

        text = bundle.text
        endpoints = sorted({match.group("path") for match in API_RE.finditer(text)})
        for endpoint in endpoints:
            print(f"  API {endpoint}")

        for keyword in ["piao/document", "piaoExport", "piao", "amministr", "annualita", "anno"]:
            if keyword.lower() in text.lower():
                print(f"  CONTAINS {keyword}")

        for keyword in ["piaoExport", "/api/piao/export", "/api/piaos"]:
            for match in list(re.finditer(re.escape(keyword), text))[:10]:
                pos = match.start()
                snippet = text[max(0, pos - 500) : min(len(text), pos + 1000)]
                snippet = re.sub(r"\\s+", " ", snippet)
                print(f"  KEYWORD_SNIPPET {keyword} {snippet}")

        # Also surface short string literals around '/api/' even if minification
        # prevents the stricter regex from capturing them.
        positions = [match.start() for match in re.finditer(r"/api/", text)]
        for pos in positions[:100]:
            snippet = text[max(0, pos - 120) : min(len(text), pos + 240)]
            snippet = re.sub(r"\s+", " ", snippet)
            print(f"  SNIPPET {snippet}")


if __name__ == "__main__":
    main()


def probe_api() -> None:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (compatible; SegnaliLocaliDiTrasparenza/0.2; "
                "+https://github.com/colazeta/segnali_locali_di_trasparenza)"
            )
        }
    )
    probes = [
        ("https://portale-piao.dfp.gov.it/api/piaos", {"search": "", "limit": "5"}),
        ("https://portale-piao.dfp.gov.it/api/piao/export", {}),
        ("https://portale-piao.dfp.gov.it/api/piao/export", {"years": "2026"}),
        ("https://portale-piao.dfp.gov.it/api/piao/export", {"years": "2025"}),
        ("https://portale-piao.dfp.gov.it/api/piao/export", {"years": "2026-2028"}),
        ("https://portale-piao.dfp.gov.it/api/piao/export", [("years", "2025"), ("years", "2026")]),
    ]
    for url, params in probes:
        try:
            response = session.get(url, params=params, timeout=60)
        except requests.RequestException as exc:
            print(f"PROBE error={type(exc).__name__} url={url} params={params}")
            continue
        print(
            "PROBE "
            f"status={response.status_code} "
            f"type={response.headers.get('content-type')} "
            f"disposition={response.headers.get('content-disposition')} "
            f"bytes={len(response.content)} "
            f"url={response.url}"
        )
        prefix = response.content[:500]
        try:
            print(f"  PREFIX {prefix.decode('utf-8', errors='replace')!r}")
        except Exception:
            print(f"  PREFIX_BYTES {prefix[:80]!r}")


if __name__ == "__main__":
    probe_api()
