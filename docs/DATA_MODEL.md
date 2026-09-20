# Data model

## Municipality version

Current municipality records are versioned territorial identities.

| Field | Meaning |
|---|---|
| `municipality_version_id` | Technical id for the current ISTAT-coded version |
| `istat_code` | Current 6-digit ISTAT municipality code |
| `name` | Current official municipality name |
| `region_code` | ISTAT region code |
| `region_name` | Region name |
| `supra_code` | Current supra-municipal statistical territorial code |
| `supra_name` | Current supra-municipal unit name |
| `province_abbr` | Vehicle-registration province abbreviation when supplied |
| `cadastral_code` | Municipality cadastral code |

A future `municipality_entity` / lineage table will connect successive municipality versions.

## Public-body link

| Field | Meaning |
|---|---|
| `ipa_match_status` | `matched_exact`, `matched_contains`, `matched_unique_location`, `ambiguous`, `unmatched` |
| `ipa_candidate_count` | Number of IPA L6 candidates considered |
| `ipa_code` | Selected Codice IPA, only for deterministic links |
| `ipa_name` | IPA entity name |
| `fiscal_code` | Public body's fiscal code |
| `institutional_url` | Institutional website reported by IPA |
| `updated_at_ipa` | IPA source update/verification date when available |

No fuzzy match is accepted automatically.

## Future municipality lineage

The historical layer should use separate structures rather than overwriting current rows:

```
municipality_entity
  municipality_id
  canonical_label

municipality_version
  municipality_version_id
  municipality_id
  istat_code
  valid_from
  valid_to
  official_name
  territorial attributes...

municipality_transition
  predecessor_version_id
  successor_version_id
  transition_type
  effective_date
  legal_source
```

Examples of `transition_type`:

- `rename`
- `code_change`
- `province_change`
- `merger`
- `incorporation`
- `split`
- `suppression`

## Transparency observation

Atomic observation table planned for milestone 1 onward:

```
transparency_observation
  observation_id
  municipality_version_id
  public_body_ipa_code
  signal_type
  observed_at
  value
  status
  source_url
  evidence_uri
  evidence_sha256
  collector
  collector_version
  methodology_version
  raw_payload_uri
```

### Observation status

Suggested controlled vocabulary:

- `observed`
- `not_observed`
- `not_applicable`
- `unreachable`
- `ambiguous`
- `collector_error`

“Not observed” must never be silently converted into “absent”.

## Derived indicators

Derived indicators must be stored separately from observations:

```
derived_indicator
  municipality_version_id
  indicator_id
  reference_date
  value
  methodology_version
  generated_at
```

Each derived record must be reproducible from persisted observations.


## PIAO plan record

Signal 001 uses a plan-level table:

```
piao_plan
  portal_node_id
  portal_url
  portal_entity_code
  administration_name
  istat_code
  municipality_match_basis
  period_label
  period_start_year
  period_end_year
  approval_date
  portal_published_at
  pdf_url
  pa_url
  fetched_at
  source_html_sha256
```

`approval_date` is the approval date explicitly shown by Portale PIAO.

`portal_published_at` is populated only when publication metadata are explicitly exposed by the source page. It is not inferred from approval date.

## Municipality PIAO view

A derived current-municipality table contains:

```
municipality_piao
  istat_code
  ipa_code
  name
  piao_present_any
  piao_count
  piao_latest_period
  piao_latest_approval_date
  piao_latest_portal_published_at
  piao_latest_portal_url
  piao_latest_pdf_url
  piao_latest_pa_url
```

All historical plan rows remain available in the plan-level table.
