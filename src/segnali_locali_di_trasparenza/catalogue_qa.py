"""Acceptance checks for a complete catalogue and its exact municipal projection."""
from __future__ import annotations

import math
from typing import Any

import pandas as pd


class CatalogueValidationError(RuntimeError):
    pass


def validate_catalogue(
    registry: pd.DataFrame,
    index: pd.DataFrame,
    publications: pd.DataFrame,
    manifests: list[dict[str, Any]],
    *,
    expected_shards: int,
) -> dict[str, Any]:
    """Return machine-readable evidence; never repair inconsistent source data."""
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, **evidence: Any) -> None:
        checks.append({"check": name, "passed": bool(passed), **evidence})

    check("shard_coverage", sorted(int(m["shard_index"]) for m in manifests)
          == list(range(expected_shards)))
    check("shard_count", all(int(m["shard_count"]) == expected_shards for m in manifests))
    totals = {int(m["advertised_total_at_start"]) for m in manifests}
    sizes = {int(m["page_size_at_start"]) for m in manifests}
    pages = {int(m["total_pages"]) for m in manifests}
    observed_totals = {int(v) for m in manifests for v in m["observed_totals"]}
    check("stable_catalogue_total", len(totals) == 1 and observed_totals == totals,
          advertised=sorted(totals), observed=sorted(observed_totals))
    check("stable_page_size", len(sizes) == 1 and all(
        set(map(int, m["observed_page_sizes"])) <= (sizes | {
            int(m["advertised_total_at_start"]) % int(m["page_size_at_start"])
            if int(m["page_size_at_start"]) > 0 else -1}) for m in manifests),
        advertised=sorted(sizes))
    check("registry_identity", not registry["istat_code"].eq("").any()
          and not registry["istat_code"].duplicated().any())
    ipa_keys = registry["ipa_code"].str.strip().str.casefold()
    check("registry_ipa_unique", not ipa_keys.eq("").any() and not ipa_keys.duplicated().any())
    check("nonempty_catalogue", not index.empty)
    if len(totals) == len(sizes) == len(pages) == 1 and min(sizes) > 0:
        total, size, page_count = next(iter(totals)), next(iter(sizes)), next(iter(pages))
        check("page_calculation", page_count == math.ceil(total / size))
        completed = [int(p) for m in manifests for p in m["pages_completed"]]
        check("manifest_page_coverage", sorted(completed) == list(range(page_count)))
        check("shard_page_assignment", all(
            m["pages_completed"] == list(range(int(m["shard_index"]), page_count,
                                                expected_shards)) for m in manifests))
        if not index.empty:
            actual_pages = pd.to_numeric(index["page"], errors="raise").astype(int)
            positions = pd.to_numeric(index["position"], errors="raise").astype(int)
            check("index_page_coverage", sorted(actual_pages.unique()) == list(range(page_count)))
            bad_pages = []
            for page, rows in positions.groupby(actual_pages):
                expected_rows = min(size, total - int(page) * size)
                if sorted(rows.tolist()) != list(range(max(0, expected_rows))):
                    bad_pages.append(int(page))
            check("page_positions", not bad_pages, invalid_pages=bad_pages)
            check("catalogue_row_count", len(index) == total, actual=len(index), expected=total)
    if not index.empty:
        for column in ("record_fingerprint", "piao_publication_id"):
            check(f"unique_{column}", not index[column].eq("").any()
                  and not index[column].duplicated().any(),
                  duplicate_rows=int(index[column].duplicated(keep=False).sum()))
        municipal_index = index.loc[index["ipa_code"].str.strip().str.casefold().isin(ipa_keys)]
        check("municipal_projection", sorted(municipal_index["piao_publication_id"].tolist())
              == sorted(publications["piao_publication_id"].tolist()))
        expected_istat = dict(zip(ipa_keys, registry["istat_code"]))
        mapped = publications["ipa_code"].str.strip().str.casefold().map(expected_istat)
        check("exact_ipa_join", mapped.notna().all()
              and mapped.eq(publications["istat_code"]).all())
        source_ipa = index.drop_duplicates("piao_publication_id").set_index(
            "piao_publication_id")["ipa_code"].str.strip().str.casefold()
        check("publication_source_ipa", publications["piao_publication_id"].map(source_ipa)
              .eq(publications["ipa_code"].str.strip().str.casefold()).all())
    check("unique_municipal_publications", not publications["piao_publication_id"].eq("").any()
          and not publications["piao_publication_id"].duplicated().any())
    return {"schema_version": 1, "accepted": all(c["passed"] for c in checks), "checks": checks}


def require_accepted(report: dict[str, Any]) -> None:
    if not report["accepted"]:
        failures = [c["check"] for c in report["checks"] if not c["passed"]]
        raise CatalogueValidationError("Catalogue validation failed: " + ", ".join(failures))
