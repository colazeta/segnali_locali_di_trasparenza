# Municipality lineage

## Purpose

The current ISTAT code is an interoperability key, not a timeless municipality identifier.

Municipalities may be renamed, recoded, moved between higher-level territorial units,
merged, split, incorporated or suppressed. Historical observations must therefore be
attached to the municipality version that existed when the observation was made.

## Official source

The lineage source layer calls **ISTAT SITUAS directly**.

It does not depend at runtime on third-party wrappers.

Two official SITUAS reports are persisted in the first implementation:

### Report 129 — administrative and territorial variations since 1991

Used as the event/evidence layer.

Important fields exposed by SITUAS include the variation type
(`DESC_COD_VARIAZIONE`) and the legal/procedural description
(`TESTO_PROVVEDIMENTO`).

### Report 99 — municipality code translation between two dates

Used as the longitudinal code-correspondence layer.

This is especially useful when linking datasets referring to municipalities at
different dates.

## Processing policy

The first lineage stage deliberately stores the official report records without
prematurely forcing every row into a predecessor/successor graph.

For each build it records:

- live SITUAS catalog metadata;
- exact report request URL;
- retrieval timestamp;
- row count;
- returned columns;
- SHA-256 of canonicalised report records;
- CSV and JSONL representations.

The graph layer will be derived only after the report-129 event semantics have been
tested by variation type.

## Planned graph

```
municipality_entity
    |
    +-- municipality_version A
    |       valid_from
    |       valid_to
    |       istat_code
    |
    +-- municipality_version B
            ...

municipality_transition
    predecessor_version_id
    successor_version_id
    transition_type
    effective_date
    legal_evidence
    situas_record_hash
```

A many-to-one transition supports mergers; one-to-many supports splits.

## Rule

Historical records are never overwritten to make them look current. Translation to a
current municipality, when useful analytically, is a derived relation and must remain
distinguishable from the original territorial identity.
