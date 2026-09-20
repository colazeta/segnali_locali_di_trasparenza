# Official sources

Verified on 20 September 2026.

## ISTAT / SITUAS — canonical municipality identity

Publication page:

https://www.istat.it/classificazione/codici-dei-comuni-delle-province-e-delle-regioni/

Stable current-workbook permalink:

https://www.istat.it/storage/codici-unita-amministrative/Elenco-comuni-italiani.xlsx

Role: **canonical source for current territorial identity**.

As of the ISTAT update effective 21 February 2026, the canonical number of current municipalities is **7,894**. The count must never be hard-coded: the pipeline derives it from the current source at every rebuild.

ISTAT also documents territorial changes, previous names, suppressions and historical administrative variations through SITUAS. Those sources will feed the lineage layer.

## IPA / AgID — public-body identity

Dataset:

https://www.indicepa.gov.it/ipa-dati/dataset/enti

Current resource used by the initial pipeline:

https://indicepa.gov.it/ipa-dati/dataset/5baa3eb8-266e-455a-8de8-b1f434c279b2/resource/d09adf99-dc10-4349-8c53-27b1e5aa97b6/download/enti.xlsx

Role: **administrative entity linkage**.

Relevant fields include:

- `Codice_IPA`
- `Denominazione_ente`
- `Codice_fiscale_ente`
- `Codice_Categoria`
- `Codice_comune_ISTAT`
- `Codice_catastale_comune`
- `Sito_istituzionale`
- `Data_aggiornamento`

Municipalities fall under IPA category `L6`, whose label is “Comuni e loro Consorzi e Associazioni”. Because the category is broader than municipalities alone, linkage must remain conservative.

The IPA dataset is continuously/daily updated and distributed under CC BY 4.0.

### Resource URL caveat

The CKAN resource identifier may change when IPA republishes the file. A later improvement should resolve the active resource through IPA's dataset/API metadata instead of assuming the current resource URL is permanent.

## Cruscotto Italia / AgID — enrichment

Project:

https://github.com/AgID/cruscotto-italia

Public MCP endpoint:

https://cruscotto-italia-mcp.dati.gov.it/mcp

No authentication is required. The documented rate limit is 60 requests/minute per IP.

Relevant tools include:

- `mcp_info`
- `search_comune`
- `comune_kpi`
- `comune_dashboard`

Role: **enrichment and cross-check**, keyed by 6-digit ISTAT municipality code.

Cruscotto Italia documentation currently describes approximately 7,896 per-municipality shards in parts of its infrastructure documentation, while current ISTAT reports 7,894 municipalities from 21 February 2026. This is treated as a useful freshness/control discrepancy, not as a reason to override ISTAT.

## Source precedence

For fields that conflict:

1. current municipality identity and territorial coding → **ISTAT/SITUAS**
2. public-body identity and institutional contact data → **IPA**
3. derived/enrichment domains → **their primary institutional source**, with Cruscotto Italia usable as federation/cross-check

Every ingestion must record source URL, retrieval timestamp and content hash when a file is downloaded.
