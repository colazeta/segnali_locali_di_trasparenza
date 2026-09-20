# Data model

## 1. Municipality registry

The canonical municipality layer preserves current territorial identity and the deterministic link to IPA.

Key fields:

| Field | Meaning |
|---|---|
| `municipality_version_id` | Technical identifier for the current ISTAT-coded version |
| `istat_code` | Current 6-digit ISTAT municipality code |
| `name` | Official municipality name |
| `region_code`, `region_name` | Region |
| `supra_code`, `supra_name` | Supra-municipal statistical unit |
| `cadastral_code` | Cadastral code |
| `ipa_code` | Deterministically linked Codice IPA |
| `ipa_name` | IPA entity name |
| `fiscal_code` | Public-body fiscal code |
| `institutional_url` | Institutional website reported by IPA |

Administrative lineage remains separate from the current-state row so mergers, renamings and recodings do not overwrite history.

## 2. PIAO publication

**Grain: one row per PIAO publication/version returned by the official public source.**

Core schema:

```
piao_publication
  piao_publication_id
  istat_code
  municipality_name
  ipa_code
  portal_administration_name
  reference_label
  reference_period
  reference_start_year
  reference_end_year
  version
  approval_date
  approval_act_reference
  approval_authority
  employees_under_50
  piao_document_url
  piao_document_file_name
  piao_document_mime_type
  approval_act_url
  approval_act_file_name
  institutional_piao_url
  attachment_count
  attachments_json
  portal_publication_date
  portal_publication_date_status
  retrieved_at
  source_catalogue_url
```

### Publication identifier

`piao_publication_id` is deterministic and is derived from:

- Codice IPA;
- reference period;
- version;
- primary PIAO document URL.

It is used to de-duplicate pages and to support future longitudinal first/last-observed tracking.

## 3. Municipality PIAO status

**Grain: exactly one row per current municipality.**

For a configured target start year, for example 2026:

```
municipality_piao_status
  istat_code
  municipality_name
  ipa_code
  lookup_status
  piao_present_on_portal
  publication_count

  target_start_year
  period_starting_target_year_present
  period_starting_target_year_publication_count

  latest_reference_period
  latest_reference_start_year
  latest_reference_end_year
  latest_version
  latest_approval_date
  latest_piao_document_url

  portal_publication_date_status
  retrieved_at
  error
```

For `target_start_year = 2026`, `period_starting_target_year_present = true` means that a **2026–2028** PIAO is observed. A 2025–2027 PIAO does not satisfy this condition.

## 4. Analytical cycle status

A derived presentation layer classifies each municipality as:

```
target_period_present
prior_period_only
no_piao_observed
lookup_error
```

Definitions:

- `target_period_present`: at least one PIAO starts in the configured target year;
- `prior_period_only`: PIAOs exist, but none starts in the target year;
- `no_piao_observed`: no PIAO is returned for the municipal IPA code;
- `lookup_error`: the municipality could not be assessed because collection failed.

## 5. Date semantics

`approval_date` is the date explicitly exposed by the source as the PIAO approval date.

`portal_publication_date` is a separate field and remains empty when the official public source does not expose a historical publication timestamp.

`retrieved_at` records when this project observed the record.

These fields must never be substituted for one another.

## 6. Future longitudinal state

Once repeated snapshots are persisted, the deterministic publication id can support:

```
piao_observation_history
  piao_publication_id
  first_observed_at
  last_observed_at
  first_snapshot_id
  last_snapshot_id
```

This will answer when the monitor first observed a PIAO without misrepresenting that timestamp as the official historical publication date.
