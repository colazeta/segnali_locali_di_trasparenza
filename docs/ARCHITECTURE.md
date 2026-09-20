# Architecture

## 1. Scope

Segnali locali di trasparenza is a national monitoring system for observable transparency signals in Italian municipalities.

The system separates four concerns:

1. **territorial identity** — what the municipality is at a given point in time;
2. **public-body identity** — which IPA entity represents the municipality;
3. **observations** — what was observed, when, where and with which evidence;
4. **presentation** — public pages, maps, comparisons and exploratory views.

The public UI must be reproducible from persisted project data. External APIs and MCP servers are enrichment inputs, not mandatory runtime dependencies.

## 2. Source hierarchy

### Tier 1 — canonical identity

**ISTAT / SITUAS** is authoritative for current municipality codes, names and territorial changes.

The current ISTAT municipality workbook is the canonical input for the current-state registry.

### Tier 2 — public-body identity

**IPA / AgID** supplies the administrative entity layer:

- Codice IPA;
- fiscal code;
- entity name and category;
- institutional website;
- contact metadata;
- update timestamp.

Municipal entities are identified conservatively. IPA category L6 includes “Comuni e loro Consorzi e Associazioni”; therefore category + seat location alone is not a sufficient deterministic link.

### Tier 3 — enrichment and cross-check

**Cruscotto Italia / AgID** is used for enrichment and verification by ISTAT code.

It is explicitly not a hard runtime dependency of the public site.

## 3. Entity model

A municipality is not modelled as one timeless row.

The current milestone produces a **municipality version** identified by the current ISTAT code. The historical lineage layer will later connect versions created by:

- code changes;
- renamings;
- province/UTS changes;
- mergers;
- incorporations;
- suppressions.

This distinction is particularly important after territorial recodings such as those affecting Sardinia in 2026.

## 4. Processing layers

```
official sources
      |
      v
data/raw/                    ephemeral, not committed
      |
      v
normalisation
      |
      +--> ISTAT current municipality versions
      |
      +--> IPA municipal-entity candidates
      |
      v
deterministic linkage
      |
      +--> matched
      +--> ambiguous
      +--> unmatched
      |
      v
data/processed/
      |
      +--> municipalities.csv
      +--> municipalities.jsonl
      |
      v
future collectors
      |
      v
transparency observations
      |
      v
public site / API
```

## 5. Non-negotiable provenance fields

Every future observation must contain at least:

- municipality identifier;
- signal type;
- observation timestamp;
- source URL;
- observed value/status;
- evidence reference or evidence hash;
- collector identifier;
- collector version;
- methodology version.

A derived indicator must retain links to the observations from which it was computed.

## 6. Transparency signals

Signals are atomic observations, not scores.

Examples:

- institutional website reachable;
- HTTPS correctly configured;
- “Amministrazione trasparente” entry point discovered;
- required section reachable;
- publication timestamp observed;
- machine-readable file exposed;
- broken link;
- document stale according to a defined rule;
- historical version still retrievable.

A synthetic score, if ever introduced, belongs to a later analytical layer and must be recomputable from versioned atomic observations.

## 7. Failure policy

The pipeline must prefer **unresolved** over silently wrong.

Examples:

- multiple plausible IPA entities → `ambiguous`;
- no deterministic IPA entity → `unmatched`;
- unexpected source schema → fail the build;
- duplicate current ISTAT code → fail the build;
- external enrichment unavailable → preserve the canonical registry and mark enrichment unavailable.

## 8. Planned milestones

### Milestone 0
National municipality registry: ISTAT + IPA + provenance.

### Milestone 1
Discovery of the official institutional website and “Amministrazione trasparente” entry point.

### Milestone 2
Availability and structural integrity of transparency sections.

### Milestone 3
Temporal monitoring, change detection and evidence snapshots.

### Milestone 4
Public municipality pages, search, map and comparative exploration.
