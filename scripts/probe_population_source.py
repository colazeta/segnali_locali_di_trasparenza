from __future__ import annotations

import io
import json
from pathlib import Path
import re
import zipfile

import pandas as pd
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

    sample_url = "https://demo.istat.it/data/posas/POSAS_2026_it_Comuni.zip"
    sample = requests.get(
        sample_url,
        timeout=90,
        headers={"User-Agent": "segnali-locali-di-trasparenza/0.1"},
    )
    sample.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(sample.content)) as archive:
        sample_names = archive.namelist()
        raw = archive.read(sample_names[0])
        sample_preview = {
            sample_names[0]: raw.decode("utf-8-sig").splitlines()[:8]
        }
        posas = pd.read_csv(
            io.BytesIO(raw),
            sep=";",
            skiprows=1,
            dtype={"Codice comune": str, "Comune": str},
        )

    posas["Codice comune"] = posas["Codice comune"].astype(str).str.zfill(6)
    posas["Totale"] = pd.to_numeric(posas["Totale"], errors="raise")
    totals = (
        posas.groupby(["Codice comune", "Comune"], as_index=False)["Totale"]
        .sum()
        .rename(columns={"Totale": "population_2026"})
    )

    registry = pd.read_csv(
        "data/processed/municipalities.csv",
        dtype=str,
        keep_default_na=False,
    )
    registry["istat_code"] = registry["istat_code"].astype(str).str.zfill(6)
    posas_codes = set(totals["Codice comune"])
    current_codes = set(registry["istat_code"])
    posas_only = totals.loc[totals["Codice comune"].isin(posas_codes - current_codes)]
    current_only = registry.loc[registry["istat_code"].isin(current_codes - posas_codes)]

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
        "posas_downloadish_hrefs": downloadish[:120],
        "sample_url": sample_url,
        "sample_zip_names": sample_names,
        "sample_preview": sample_preview,
        "posas_age_rows": len(posas),
        "posas_municipality_rows": len(totals),
        "posas_population_total": int(totals["population_2026"].sum()),
        "posas_only": posas_only.to_dict(orient="records"),
        "current_only": current_only[["istat_code", "name", "region_name", "supra_name"]].to_dict(orient="records"),
    }
    Path("data/probes").mkdir(parents=True, exist_ok=True)
    Path("data/probes/situas_population_probe.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
