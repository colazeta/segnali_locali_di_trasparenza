from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from segnali_locali_di_trasparenza.situas import SituasClient, validity_end


VARIATIONS_REPORT = 129
TRANSLATION_REPORT = 99
LINEAGE_START = "01/01/1991"


def canonical_hash(records: list[dict[str, object]]) -> str:
    payload = json.dumps(
        records,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_records(records: list[dict[str, object]], stem: Path) -> dict[str, str]:
    stem.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(records)
    csv_path = stem.with_suffix(".csv")
    jsonl_path = stem.with_suffix(".jsonl")
    frame.to_csv(csv_path, index=False)
    frame.to_json(jsonl_path, orient="records", lines=True, force_ascii=False)
    return {"csv": str(csv_path), "jsonl": str(jsonl_path)}


def main() -> None:
    output_dir = Path("data/lineage")
    manifest_dir = Path("data/manifests")
    manifest_dir.mkdir(parents=True, exist_ok=True)

    client = SituasClient()
    catalog = client.catalog()

    variation_entry = client.report_entry(VARIATIONS_REPORT, catalog=catalog)
    translation_entry = client.report_entry(TRANSLATION_REPORT, catalog=catalog)

    variation_request, variations = client.report(
        VARIATIONS_REPORT,
        catalog=catalog,
    )
    translation_end = validity_end(translation_entry)
    translation_request, translations = client.report(
        TRANSLATION_REPORT,
        date_from=LINEAGE_START,
        date_to=translation_end,
        catalog=catalog,
    )

    variation_outputs = write_records(
        variations,
        output_dir / "situas_variations_1991_current",
    )
    translation_outputs = write_records(
        translations,
        output_dir / "situas_code_translation_1991_current",
    )

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "authority": "ISTAT / SITUAS",
        "reports": {
            "variations": {
                "report_id": VARIATIONS_REPORT,
                "title": variation_request.title,
                "validity": variation_request.validity,
                "request_url": variation_request.url,
                "rows": len(variations),
                "columns": sorted(
                    {key for row in variations for key in row}
                ),
                "sha256": canonical_hash(variations),
                "outputs": variation_outputs,
            },
            "translation": {
                "report_id": TRANSLATION_REPORT,
                "title": translation_request.title,
                "validity": translation_request.validity,
                "request_url": translation_request.url,
                "rows": len(translations),
                "columns": sorted(
                    {key for row in translations for key in row}
                ),
                "sha256": canonical_hash(translations),
                "outputs": translation_outputs,
            },
        },
        "source_policy": {
            "catalog": "live SITUAS get_elenco_microservizi gateway",
            "data": "official SITUAS publish/reportspooljson endpoints",
            "runtime_dependency_on_opensituas": False,
        },
    }

    manifest_path = manifest_dir / "municipality_lineage.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
