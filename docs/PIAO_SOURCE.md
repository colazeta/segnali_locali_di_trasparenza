# Portale PIAO public source

Verified on 20 September 2026.

## Official public catalogue

The Dipartimento della funzione pubblica exposes the public catalogue at:

- https://piao.dfp.gov.it/piao

The page mounts a React application in `#piao-react-view`.

The frontend uses two public JSON endpoints on the same official host:

- `GET /api/administrations`
- `GET /api/piao`

These endpoints are used by the anonymous public catalogue. They are distinct from
the authenticated management application at `portale-piao.dfp.gov.it`.

## Municipality lookup

The catalogue can identify an administration by Codice IPA:

```
GET https://piao.dfp.gov.it/api/administrations?ipaCode=<IPA>&limit=<N>
```

A successful response contains records such as:

```json
{
  "administrationIpaCode": "c_m208",
  "administrationName": "Comune di Lamezia Terme"
}
```

Our municipality registry already contains deterministic IPA links for all current
7,894 ISTAT municipalities, so no name-based matching is needed for normal
collection.

## PIAO publications

The catalogue queries publications as:

```
GET https://piao.dfp.gov.it/api/piao?ipaCode=<IPA>&page=<ZERO_BASED_PAGE>
```

The response container exposes:

- `list`
- `count`
- `total`

Each publication record currently exposes these top-level fields:

- `administrationIpaCode`
- `administrationName`
- `version`
- `years`
- `content`

The observed `content` object exposes:

- `approvalDate` — date of approval;
- `estremiAtto` — approval-act reference;
- `autorita` — approving authority;
- `atto` — approval-act file;
- `nDipendenti` — under-50-employees flag;
- `piaoPDF` — PIAO file;
- `attachments` — zero or more attachments;
- `linkPiaoPA` — PIAO URL on the administration's institutional/transparency site.

Documents are served from official URLs under
`https://portale-piao.dfp.gov.it/api/piao/document?f=...`.

## Publication date limitation

The anonymous public API does **not** currently expose a field identifying the
date on which a PIAO record was published to the Portale PIAO.

The project therefore keeps three concepts separate:

1. `approval_date` — source field `approvalDate`;
2. `portal_publication_date` — empty until an authoritative public source exposes it;
3. `retrieved_at` — when our monitor observed the record.

The approval date must never be relabelled as the portal publication date.

For future longitudinal monitoring, the project may also maintain
`first_observed_at` and `last_observed_at`. Those dates describe our observation
history, not the historical publication timestamp.

## Interface stability

The endpoints above are public interfaces used by the official public frontend,
but they are not treated as a documented, versioned API contract.

Collection therefore must:

- validate the response shape;
- fail visibly on incompatible schema changes;
- preserve retrieval timestamps;
- retain source URLs;
- distinguish request/API errors from absence of a PIAO;
- never use authenticated management endpoints or bypass access controls.
