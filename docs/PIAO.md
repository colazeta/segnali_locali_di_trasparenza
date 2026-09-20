# Signal 001 — PIAO presence and metadata

The first active signal in the project is the presence of a **Piano Integrato di Attività e Organizzazione (PIAO)** for each Italian municipality.

Primary source: the official **Portale PIAO** of the Dipartimento della Funzione Pubblica.

## Unit of observation

One row = one PIAO record published on the official portal.

The collector preserves all observed historical plans from 2022 onward rather than retaining only the latest plan.

## Core metadata

For each observed PIAO:

- municipality ISTAT code;
- municipality IPA code;
- municipality name;
- Portale PIAO node id and URL;
- administration name shown by the portal;
- portal entity code when encoded in the page title;
- reference period, e.g. `2025-2027`;
- reference-period start and end year;
- approval date shown by the portal;
- portal publication timestamp **only when explicitly exposed in page metadata**;
- PDF URL on Portale PIAO;
- URL of the PIAO on the administration website when supplied;
- fetch timestamp;
- SHA-256 of the source HTML;
- municipality linkage basis.

## Publication date vs approval date

`approval_date` and `portal_published_at` are separate fields.

The public Portale PIAO record visibly exposes **Data Approvazione**. This must not be relabelled as a publication date.

If a page exposes a publication timestamp through HTML metadata such as `article:published_time`, `datePublished`, or equivalent metadata, it is stored in `portal_published_at`. Otherwise that field remains empty.

The collector always stores `fetched_at`, which represents when this project observed the record.

## Municipality-level view

The plan-level table is transformed into a 7,894-row municipality view containing:

- `piao_present_any`;
- `piao_count`;
- latest observed period;
- latest approval date;
- latest explicit portal publication timestamp;
- latest Portale PIAO page;
- latest PDF;
- latest administration-site link.

Absence means **no PIAO record was observed in the collected Portale PIAO corpus**. It is not automatically interpreted as legal non-compliance.

## Linkage

Preferred linkage is by Codice IPA when the Portale PIAO title exposes it, for example:

`Piano Integrato c_l719 2025-2027`

→ `c_l719` → Comune di Velletri in the national ISTAT↔IPA registry.

When the code is unavailable, a deterministic exact administration-name match may be used. No generic fuzzy matching is allowed.

## Outputs

- `piao_plans.csv`: all plan records;
- `piao_plans.jsonl`: same records in JSONL;
- `municipalities_piao.csv`: one row for every current municipality;
- `piao_unmatched.csv`: portal records that could not be deterministically linked;
- `manifest.json`: source, counts and output hashes.
