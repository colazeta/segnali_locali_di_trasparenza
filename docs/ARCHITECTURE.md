# Architecture

## Scope

The project monitors observable transparency signals for Italian municipalities while keeping territorial identity, public-body identity and observations separate.

The active processing chain is:

```
ISTAT / SITUAS
      +
IPA / AgID
      |
      v
canonical municipality registry
      |
      v
Portale PIAO / Dipartimento Funzione Pubblica
      |
      v
PIAO plan records
      |
      +--> deterministic municipality linkage
      |
      v
municipality-level PIAO view
      |
      v
future public site / API
```

## Source precedence

1. **ISTAT / SITUAS** — territorial identity and administrative history.
2. **IPA / AgID** — public-body identity and Codice IPA.
3. **Portale PIAO / Dipartimento della Funzione Pubblica** — primary source for Signal 001.
4. **Cruscotto Italia / AgID** — optional enrichment and cross-check.

The public UI must be reproducible from persisted project outputs rather than requiring live external calls.

## Signal 001

The first active signal is **PIAO presence and metadata**.

The atomic object is one Portale PIAO plan record. Multiple records can belong to the same municipality across different reference periods.

The municipality-level state is derived from those records and includes presence, number of observed plans and latest observed plan metadata.

## Provenance

Every collected PIAO record retains:

- Portale PIAO node id and URL;
- fetch timestamp;
- source HTML hash;
- administration name;
- portal entity code where available;
- reference period;
- approval date;
- explicit publication metadata when available;
- PDF URL;
- administration-site URL;
- municipality linkage basis.

## Publication semantics

Approval and publication are distinct events.

The field shown publicly as **Data Approvazione** is stored as `approval_date`.

A portal publication timestamp is populated only when explicitly exposed by HTML metadata. It must never be inferred from the approval date.

## Failure policy

The pipeline prefers unresolved over silently wrong:

- unknown/ambiguous municipality link → unmatched audit output;
- missing publication metadata → empty field, not inferred value;
- unexpected source structure → test/build failure where appropriate;
- no observed PIAO → observational absence, not automatic legal non-compliance.

## Milestones

### Milestone 0
National municipality registry and administrative lineage.

### Milestone 1
PIAO corpus and municipality-level PIAO presence/metadata.

### Milestone 2
Temporal monitoring of new PIAO publications and changes.

### Milestone 3
Public municipality pages, search and comparative views.

Additional transparency signals may be introduced only as separate, explicitly defined datasets.
