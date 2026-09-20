# Transparency signals

## Signal 001 — transparency entry point

The first national collector answers a deliberately narrow question:

> From the municipality's institutional website recorded in IPA, can the public
> “Amministrazione trasparente” entry point be discovered and confirmed?

This is a **discovery signal**, not a legal-compliance assessment.

## Discovery procedure

For each municipality version:

1. take the institutional URL linked from IPA;
2. normalise the URL without silently replacing the domain;
3. consult `robots.txt`;
4. request the institutional homepage;
5. inspect links whose anchor or URL contains transparency-related terms;
6. rank explicit “Amministrazione Trasparente” links above generic transparency links;
7. validate a small number of top candidates;
8. only when the homepage exposes no candidate, try a very small set of conventional
   paths;
9. persist the result and evidence metadata.

The collector is intentionally able to discover different technical patterns, including:

- canonical paths such as `/Amministrazione-Trasparente`;
- lowercase/hyphenated variants;
- legacy systems whose URL contains `transparenz`;
- links that redirect to a different application or host.

## Status vocabulary

| Status | Meaning |
|---|---|
| `found` | a candidate page was reached and confirmed |
| `missing_institutional_url` | the registry has no institutional URL |
| `robots_disallowed` | homepage access is disallowed by robots policy |
| `homepage_unreachable` | network/TLS/request failure |
| `homepage_http_error` | homepage returned HTTP error |
| `candidate_not_confirmed` | candidate page reachable but not semantically confirmed |
| `candidate_robots_disallowed` | candidate access disallowed by robots policy |
| `not_found` | no candidate could be observed with the bounded procedure |

**`not_found` does not mean that the municipality lacks a transparency section.**
It means that this collector did not observe one using this methodology and this
version of the website.

## Evidence

A successful observation records:

- ISTAT municipality code;
- municipality name;
- IPA institutional URL;
- observation timestamp;
- final homepage URL after redirects;
- confirmed transparency URL;
- discovery method;
- anchor text;
- HTTP status;
- SHA-256 of the confirmed HTML response;
- robots-policy status.

Future iterations may persist snapshots or WARC-like evidence when storage and
copyright/retention policy are defined.

## Collection ethics and operational safeguards

The collector:

- identifies itself with a project-specific User-Agent;
- respects `robots.txt`;
- caches robots policy per origin within a run;
- applies a delay between requests;
- retries bounded transient connection/read failures and HTTP 429/5xx responses with backoff;
- uses bounded candidate and fallback checks;
- supports restart/resume;
- does not brute-force arbitrary URL paths.

## What this signal does not establish

Finding an entry point does not establish:

- completeness of required subsections;
- timeliness of publications;
- document quality;
- machine readability;
- legal compliance;
- accuracy of published information.

Those are separate future signals and must be measured independently.


## Methodology versions

- `signal001-v1`: initial bounded discovery procedure.
- `signal001-v2`: adds bounded retries with backoff for transient network failures and
  HTTP 429/5xx responses; observation provenance records this version explicitly.
