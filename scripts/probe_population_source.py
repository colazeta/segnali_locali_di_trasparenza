from __future__ import annotations

import json
from pathlib import Path
import re

import requests


URL = (
    "https://situas-servizi.istat.it/publish/reportspooljson"
    "?pfun=74&pdata=31/05/2026"
)
POSAS_PAGE = "https://demo.istat.it/app/?i=POS"


def main() -> None:
    response = requests.get(
        URL,
        timeout=90,
        headers={
            "User-Agent": (
                "segnali-locali-di-trasparenza/0.1 "
                "(+https://github.com/colazeta/segnali_locali_di_trasparenza)"
            ),
            "Accept": "application/json,text/plain;q=0.9,*/*;q=0.5",
        },
    )
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("resultset") or payload.get("items") or []
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("SITUAS report 74 returned no rows")

    years = sorted(
        {
            str(row.get("ANNO_POP_RES") or "").strip()
            for row in rows
            if str(row.get("ANNO_POP_RES") or "").strip()
        }
    )
    keys = sorted({key for row in rows[:50] for key in row})
    lamezia = [
        row
        for row in rows
        if str(row.get("PRO_COM_T") or "").zfill(6) == "079160"
    ]

    page = requests.get(
        POSAS_PAGE,
        timeout=90,
        headers={"User-Agent": "Mozilla/5.0 segnali-locali-di-trasparenza/0.1"},
    )
    page.raise_for_status()
    html = page.text

    zip_tokens = sorted(set(re.findall(r"[^\"'<>\\s]+\\.zip(?:\\?[^\"'<>\\s]*)?", html)))
    script_srcs = sorted(
        set(re.findall(r"<script[^>]+src=[\"']([^\"']+)[\"']", html, flags=re.IGNORECASE))
    )
    hrefs = sorted(
        set(re.findall(r"href=[\"']([^\"']+)[\"']", html, flags=re.IGNORECASE))
    )
    downloadish = [
        value
        for value in hrefs
        if "download" in value.casefold() or ".zip" in value.casefold() or ".csv" in value.casefold()
    ]

    result = {
        "situas_source_url": URL,
        "situas_rows": len(rows),
        "situas_population_reference_years": years,
        "situas_keys": keys,
        "situas_lamezia": lamezia[:1],
        "posas_page": POSAS_PAGE,
        "posas_html_length": len(html),
        "posas_zip_tokens": zip_tokens[:100],
        "posas_script_srcs": script_srcs,
        "posas_downloadish_hrefs": downloadish[:100],
    }
    Path("data/probes").mkdir(parents=True, exist_ok=True)
    Path("data/probes/situas_population_probe.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
