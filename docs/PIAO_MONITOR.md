# PIAO monitor

## Scope

For now, the project monitors one thing only: whether each current Italian municipality has one or more PIAO records published on the official **Portale PIAO** of the Dipartimento della Funzione Pubblica.

The source is: https://piao.dfp.gov.it/piao

The portal is treated as the primary publication source. Municipal websites are not crawled to infer PIAO presence.

## Record grain

One row = one PIAO publication associated with one municipality.

A municipality may therefore have multiple rows, for example 2022-2024, 2023-2025, 2024-2026 and 2025-2027.

A municipality with no record returned by the official portal still receives one coverage row with `piao_present=false`.

## Metadata

For each PIAO record the collector stores: ISTAT municipality code; municipality name; registry IPA code; portal node id; official Portale PIAO URL; administration name; PIAO reference period; start/end year; approval date; portal publication timestamp when exposed by page metadata; PDF URL; administration-site PIAO URL when exposed; observation timestamp; collector/methodology versions; and SHA-256 of the HTML evidence.

## Publication date vs approval date

`approval_date` is the value explicitly displayed by Portale PIAO as “Data Approvazione”.

`portal_published_at` is populated only when the portal page exposes a publication timestamp through HTML metadata such as `article:published_time`. If it is not exposed, the field remains empty.

The collector does not infer a publication date from PDF contents, approval date, search-engine timestamps or HTTP Last-Modified headers.

## Presence

`piao_present = true` if at least one PIAO record is returned by the official portal for the municipality's IPA entity.

`piao_present = false` means only that no record was observed on Portale PIAO using the current collector. It does not independently prove that the municipality never adopted a PIAO.

## Outputs

- `piao_publications.csv`: all observed PIAO records
- `piao_publications.jsonl`: same records in JSON Lines format
- `municipalities_piao_latest.csv`: one row per municipality with its latest observed PIAO
- `piao_snapshot.json`: coverage and provenance manifest

No transparency score is produced.
