# Observation history

Accepted snapshot releases contain `piao_history.json`, extended from the previous
accepted release. The archive job verifies the current publications against their
manifest checksum, requires accepted catalogue QA, and verifies the previous
history checksum before updating anything. Failure to fetch or validate existing
history blocks archival and deployment; it does not silently start a new baseline.

Each publication retains:

- `first_observed_at` and its snapshot identifier;
- `last_observed_at` and its snapshot identifier;
- `first_observed_after`, a conservative lower bound from the preceding accepted
  snapshot's collection start (null for baseline observations);
- whether the record was returned in the latest accepted snapshot;
- an observation count, fingerprint and last normalised source metadata.

The cumulative event ledger records baseline observations, newly observed records,
metadata changes, records no longer returned, and records returned again. Events
include municipality identity and reference start year, allowing target-cycle
changes to be selected exactly. A version or document-URL change changes the
existing synthetic publication identifier: it appears as a new identity, and any
old identity no longer returned remains in history. This is not proof that a PDF's
bytes changed; routine collection does not download documents.

The ledger retains every accepted snapshot's collection interval and publication
checksum. Each release retains its own full evidence. Snapshots must be ordered
and non-overlapping; replaying a snapshot is rejected. A failed or partial collection
cannot update history. A baseline observation never claims to be a new publication.

An interval such as “first observed after 20 September and by 27 September” means
**new to this monitor's accepted observations**, not an official publication date.
The preceding collection start is used rather than its finish because pagination
is not instantaneous and the API exposes no transactional snapshot token.
`approval_date`, `portal_publication_date` and observation dates remain distinct.
“No longer returned” is an observation of the catalogue, not proof of legal
withdrawal, deletion or non-compliance.

There are no accepted release snapshots as of the 3 October 2026 inspection.
The first successful production run will establish the baseline. History integration
is tested locally; an accepted live national run is required to validate archival
end to end. Legacy archives without history require an explicit, audited bootstrap,
not an automatic reset.

Local extension:

```bash
python scripts/build_piao_history.py --snapshot-dir data/piao-national --snapshot-id RUN_ID
# For subsequent snapshots, also supply --previous-history and --previous-manifest.
```
