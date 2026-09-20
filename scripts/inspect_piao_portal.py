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

        for keyword in ["piao/document", "piao", "amministr", "annualita", "anno"]:
            if keyword.lower() in text.lower():
                print(f"  CONTAINS {keyword}")

        # Also surface short string literals around '/api/' even if minification
        # prevents the stricter regex from capturing them.
        positions = [match.start() for match in re.finditer(r"/api/", text)]
        for pos in positions[:100]:
            snippet = text[max(0, pos - 120) : min(len(text), pos + 240)]
            snippet = re.sub(r"\s+", " ", snippet)
            print(f"  SNIPPET {snippet}")


if __name__ == "__main__":
    main()
