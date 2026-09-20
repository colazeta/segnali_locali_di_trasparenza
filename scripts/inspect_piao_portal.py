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


def inspect_public_catalogue() -> None:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (compatible; SegnaliLocaliDiTrasparenza/0.2; "
                "+https://github.com/colazeta/segnali_locali_di_trasparenza)"
            )
        }
    )
    url = "https://piao.dfp.gov.it/piao"
    response = session.get(url, timeout=30)
    print(
        f"PUBLIC status={response.status_code} final={response.url} "
        f"type={response.headers.get('content-type')} bytes={len(response.content)}"
    )
    response.raise_for_status()
    html = response.text

    patterns = [
        r"views/ajax",
        r"/node/\\d+",
        r"view_dom_id",
        r"data-drupal-selector",
        r"views-exposed-form",
        r"pager",
        r"search",
        r"field_anno",
        r"anno",
    ]
    for pattern in patterns:
        matches = list(re.finditer(pattern, html, flags=re.IGNORECASE))
        print(f"PUBLIC_PATTERN {pattern} count={len(matches)}")
        for match in matches[:20]:
            pos = match.start()
            snippet = html[max(0, pos - 350) : min(len(html), pos + 800)]
            snippet = re.sub(r"\\s+", " ", snippet)
            print(f"  PUBLIC_SNIPPET {snippet}")

    for src in SCRIPT_RE.findall(html):
        print(f"PUBLIC_SCRIPT {urljoin(response.url, src)}")

    hrefs = re.findall(r"""href=["']([^"']+)["']""", html, flags=re.IGNORECASE)
    node_hrefs = sorted({urljoin(response.url, h) for h in hrefs if "/node/" in h})
    print(f"PUBLIC_NODE_HREFS count={len(node_hrefs)}")
    for item in node_hrefs[:50]:
        print(f"  PUBLIC_NODE {item}")


if __name__ == "__main__":
    inspect_public_catalogue()


def inspect_public_catalogue_embeds() -> None:
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    response = session.get("https://piao.dfp.gov.it/piao", timeout=30)
    response.raise_for_status()
    html = response.text

    for pattern in [
        r"portale-piao[^\"'<> ]*",
        r"<iframe[^>]*>",
        r"<form[^>]*>",
        r"<div[^>]*(?:piao|search|plan)[^>]*>",
        r"<input[^>]*>",
        r"<select[^>]*>",
        r"drupalSettings",
    ]:
        matches = re.findall(pattern, html, flags=re.IGNORECASE)
        print(f"EMBED_PATTERN {pattern} count={len(matches)}")
        for value in matches[:100]:
            print(f"  EMBED {re.sub(r'\\s+', ' ', value)}")

    for src in SCRIPT_RE.findall(html):
        url = urljoin(response.url, src)
        if not url.startswith("https://piao.dfp.gov.it/"):
            continue
        js = session.get(url, timeout=30)
        print(f"PUBLIC_JS status={js.status_code} url={url} bytes={len(js.content)}")
        if js.status_code >= 400:
            continue
        text = js.text
        for keyword in ["portale-piao", "/api/", "iframe", "piao"]:
            positions = list(re.finditer(re.escape(keyword), text, flags=re.IGNORECASE))
            print(f"  JS_KEYWORD {keyword} count={len(positions)}")
            for match in positions[:40]:
                pos = match.start()
                snippet = text[max(0, pos - 300) : min(len(text), pos + 700)]
                snippet = re.sub(r"\\s+", " ", snippet)
                print(f"    JS_SNIPPET {snippet}")


if __name__ == "__main__":
    inspect_public_catalogue_embeds()


def probe_public_api() -> None:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (compatible; SegnaliLocaliDiTrasparenza/0.2; "
                "+https://github.com/colazeta/segnali_locali_di_trasparenza)"
            ),
            "Accept": "application/json",
        }
    )
    probes = [
        "https://piao.dfp.gov.it/api/piao?page=0",
        "https://piao.dfp.gov.it/api/piao?ipaCode=c_m208&page=0",
        "https://piao.dfp.gov.it/api/piao?administrationName=Lamezia%20Terme&page=0",
        "https://piao.dfp.gov.it/api/administrations?administrationName=Lamezia&limit=10",
    ]
    for url in probes:
        response = session.get(url, timeout=30)
        print(
            f"PUBLIC_API status={response.status_code} type={response.headers.get('content-type')} "
            f"bytes={len(response.content)} url={response.url}"
        )
        print(f"  PUBLIC_API_BODY {response.text[:8000]}")


if __name__ == "__main__":
    probe_public_api()
