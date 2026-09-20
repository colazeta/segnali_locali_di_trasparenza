# PIAO collection architecture

Verified on 20 September 2026.

## Objective

The active monitoring target is deliberately narrow:

> for each of the 7,894 current Italian municipalities, determine whether the
> official Portale PIAO contains a PIAO whose reference period starts in the
> target year (for 2026: **2026–2028**), while retaining all historical PIAO
> publications and their official metadata.

A PIAO `2025–2027` does **not** count as a PIAO `2026–2028`.

## Identity layer

The municipality registry provides:

- 7,894 current ISTAT municipalities;
- 7,894 deterministic Codice IPA links;
- zero ambiguous current links;
- zero unmatched current links.

Codice IPA is the normal join key to Portale PIAO.

## Official public source

Catalogue:

`https://piao.dfp.gov.it/piao`

Public JSON endpoint used by the catalogue:

`GET https://piao.dfp.gov.it/api/piao?page=<N>`

Optional official filters include `ipaCode` and `administrationName`.

### Measured pagination

A live probe on 20 September 2026 returned:

- total catalogue records: **39,745**;
- records per page: **6**;
- expected pages for a complete unfiltered snapshot: **6,625**.

The following attempted page-size parameters were ignored by the public endpoint
and still returned six records:

- `limit=60`
- `pageSize=60`
- `perPage=60`
- `itemsPerPage=60`

The public frontend itself exposes `piaoPerPage = 6`.

The authenticated export endpoint discovered in the management frontend is **not**
used: anonymous requests return an access-token error.

## Collection modes

### 1. National catalogue ingestion — primary full refresh

The collector:

1. fetches page 0;
2. records the official `total` and page size;
3. derives the exact page count;
4. fetches the remaining pages with bounded parallelism;
5. rejects the snapshot if the advertised total changes during collection;
6. rejects incomplete non-final pages;
7. rejects the snapshot unless the number of unique publication identities equals
   the official total;
8. retains only records whose Codice IPA belongs to the municipality registry;
9. joins those records locally to ISTAT municipalities;
10. produces exactly one municipality-status row for every current municipality.

The default parallelism is intentionally bounded. The aim is shorter elapsed time,
not aggressive load against the government service.

### 2. Per-IPA lookup — diagnostic/fallback

`GET /api/piao?ipaCode=<CODICE_IPA>&page=<N>`

This mode is retained for:

- pilot validation;
- investigating one municipality;
- rechecking an anomalous municipality;
- parity samples against the bulk collector;
- possible targeted incremental checks.

It is not intended to duplicate the full national refresh permanently.

## Measured baseline

The first complete per-IPA national baseline completed successfully with:

- municipality status rows: **7,894**;
- PIAO publication rows linked to municipalities: **31,147**;
- municipalities with at least one PIAO: **7,374**;
- municipalities with a PIAO starting in 2026: **4,709**;
- municipalities with historical PIAO records but no 2026–2028 PIAO: **2,665**;
- municipalities with no PIAO record observed on the official portal: **520**;
- duplicate municipality status codes: **0**;
- missing municipality status codes: **0**;
- unexpected municipality status codes: **0**.

This corresponds to:

- 59.65% with a 2026–2028 PIAO observed;
- 33.76% with older PIAO history but no 2026–2028 PIAO observed;
- 6.59% with no PIAO record observed.

These are observations of the official portal, not legal-compliance findings.

### Baseline request cost

Given six records per page, the per-IPA baseline required an estimated **8,254**
catalogue requests once pagination for entities with more than six publications is
included.

A complete national catalogue snapshot requires **6,625** page requests at the
currently fixed page size: roughly 20% fewer requests, although it also transfers
non-municipal PIAO records that are discarded after the IPA filter.

## 2026 status semantics

The municipality-level fields are explicit:

- `target_start_year = 2026`
- `period_starting_target_year_present`
- `period_starting_target_year_publication_count`

For example, Lamezia Terme currently has:

- PIAO history present: yes;
- publications observed: 6;
- `2026–2028`: not observed;
- latest observed period: `2025–2027`;
- latest version: 3;
- latest approval date: 2025-06-06.

## Dates

The public API exposes `approvalDate`, but does not expose an authoritative
historical portal-publication timestamp.

The project therefore keeps separate:

- `approval_date`
- `portal_publication_date` (empty when not exposed)
- `retrieved_at`

No PDF date, search-engine timestamp or HTTP header is substituted for an official
publication date.

## Failure semantics

A municipality is never labelled as having no PIAO because of a failed request.

For the national catalogue mode, `not_observed` is assigned only after the entire
catalogue snapshot has passed completeness validation.

For per-IPA mode, request/API errors remain explicit errors.

## Intended recurring operation

Once catalogue/per-IPA parity is validated:

- national catalogue ingestion becomes the normal full refresh;
- per-IPA collection remains a targeted validation/fallback capability;
- full refresh runs weekly;
- derived municipality status is regenerated from the complete observed corpus;
- later incremental checks may focus on municipalities still missing the target
  period, without changing the canonical weekly snapshot.
