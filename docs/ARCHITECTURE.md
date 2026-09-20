# Architecture

## 1. Current scope

The project currently monitors one observable only:

> PIAO publications associated with the 7,894 current Italian municipalities on the official Portale PIAO of the Dipartimento della Funzione Pubblica.

No generic “Amministrazione trasparente” crawler and no synthetic transparency score are part of the active scope.

## 2. Identity backbone

### Municipality identity

**ISTAT / SITUAS** is authoritative for current territorial identity and administrative changes.

### Public-body identity

**IPA / AgID** supplies the public-body identity layer, most importantly the **Codice IPA**.

The national registry currently links all 7,894 current municipalities deterministically to one IPA entity. This allows the PIAO source to be joined by identifier rather than by fuzzy administration-name matching.

## 3. PIAO primary source

Primary source:

- public catalogue: `https://piao.dfp.gov.it/piao`
- public JSON endpoint used by the catalogue: `GET /api/piao`

Two collection modes are maintained:

1. **national catalogue ingestion** — primary production method;
2. **per-IPA lookup** — validation and diagnostic fallback.

The national method acquires the complete official catalogue, validates pagination completeness, filters records to the 7,894 municipal IPA codes and performs the municipality join locally.

The per-IPA method queries:

```
GET /api/piao?ipaCode=<CODICE_IPA>&page=<N>
```

It is retained to validate the bulk result and investigate individual municipalities.

## 4. Processing architecture

```
ISTAT / SITUAS --------+
                       |
IPA / AgID ------------+--> municipality registry
                              7,894 current municipalities
                              7,894 deterministic IPA links
                                       |
                                       v
Portale PIAO national catalogue --> complete paginated snapshot
                                       |
                              pagination validation
                                       |
                              filter municipal IPA codes
                                       |
                                       v
                               PIAO publications
                              one row per publication
                                       |
                                       v
                              municipality PIAO status
                              exactly 7,894 rows
                                       |
                      +----------------+----------------+
                      |                                 |
                      v                                 v
               analytical summaries              public website
               national / region / area           municipality pages
```

## 5. Core outputs

### Publication grain

One row represents one PIAO version returned by the official source.

The publication dataset preserves:

- ISTAT municipality code;
- Codice IPA;
- portal administration name;
- PIAO reference period;
- reference-period start and end year;
- version;
- approval date;
- approval-act reference;
- approving authority;
- PIAO document URL;
- approval-act URL;
- institutional PIAO URL when supplied;
- attachments;
- retrieval timestamp;
- deterministic publication id.

### Municipality grain

Exactly one row per current municipality.

For a target cycle such as **2026–2028**, the municipality view records:

- whether any PIAO is observed on the portal;
- total number of PIAO publications;
- whether a PIAO whose reference period starts in 2026 is observed;
- number of such publications/versions;
- latest available reference period;
- latest version;
- latest approval date;
- latest document URL;
- retrieval status.

## 6. Three analytical states

For presentation and analysis, municipalities are classified into mutually exclusive states:

1. `target_period_present` — a PIAO 2026–2028 is observed;
2. `prior_period_only` — one or more PIAOs are observed, but none starts in 2026;
3. `no_piao_observed` — the official source returns no PIAO for that municipal IPA code;
4. `lookup_error` — reserved for technical collection errors.

The fourth state is operational rather than substantive. Technical failure must never be converted into “no PIAO”.

## 7. Publication date semantics

Three dates must remain distinct:

- **approval date** — explicitly exposed by the public PIAO API;
- **portal publication date** — populated only if an authoritative public source exposes it;
- **retrieved/first observed date** — when this monitor observed the record.

The verified anonymous public API does not currently expose an authoritative historical portal-publication timestamp. Approval date must therefore never be relabelled as publication date.

## 8. Completeness controls

A production snapshot is accepted only if:

- municipality registry rows = 7,894;
- municipality status rows = 7,894;
- no duplicate municipality ISTAT codes exist;
- national catalogue page coverage is complete;
- the collected catalogue row count matches the API-advertised total;
- catalogue-total drift during collection is rejected;
- per-IPA and bulk collection agree during validation.

The project prefers a failed/incomplete run over silently classifying missing observations as absence.

## 9. Refresh strategy

The ordinary production refresh is a **weekly full catalogue acquisition**.

Per-IPA queries are retained for:

- spot checks;
- diagnostic retries;
- investigating mismatches;
- validating changes to the bulk collector.

A future longitudinal layer may persist `first_observed_at` and `last_observed_at` for each deterministic PIAO publication id.
