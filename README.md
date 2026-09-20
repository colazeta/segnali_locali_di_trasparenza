# Segnali locali di trasparenza

Monitor nazionale dei **PIAO pubblicati dai comuni italiani** sul Portale PIAO del Dipartimento della Funzione Pubblica.

## Perimetro corrente

In questa fase il progetto monitora **una sola cosa**:

> per ciascuno dei 7.894 comuni italiani correnti, esiste almeno un PIAO nel Portale PIAO ufficiale e a quale periodo si riferisce?

Non vengono monitorate genericamente le sezioni “Amministrazione trasparente” e non viene prodotto alcun punteggio di trasparenza.

## Base comunale

Il registry nazionale collega deterministicamente tutti i comuni correnti:

- **ISTAT / SITUAS** — identità territoriale;
- **IPA / AgID** — Codice IPA dell'ente;
- 7.894 comuni correnti;
- 7.894 collegamenti ISTAT ↔ IPA;
- 0 ambigui;
- 0 non collegati.

Il Codice IPA è la chiave usata per interrogare il Portale PIAO.

## Fonte PIAO

Fonte primaria:

- Portale PIAO — Dipartimento della Funzione Pubblica
- catalogo: https://piao.dfp.gov.it/piao
- API pubblica utilizzata dal catalogo: `GET /api/piao?ipaCode=<CODICE_IPA>&page=<N>`

Per ogni PIAO osservato vengono conservati:

- codice ISTAT del comune;
- Codice IPA;
- denominazione del comune e denominazione mostrata dal Portale;
- periodo di riferimento, ad esempio `2026-2028`;
- anno iniziale e anno finale;
- versione del PIAO;
- data di approvazione;
- estremi dell'atto di approvazione;
- autorità approvante;
- URL ufficiale del documento PIAO;
- URL dell'atto di approvazione;
- URL del PIAO sul sito dell'ente, quando disponibile;
- allegati;
- timestamp di acquisizione.

### Data di pubblicazione

La **data di approvazione** e la **data di pubblicazione sul Portale PIAO** sono concetti distinti.

L'API pubblica anonima verificata il 20 settembre 2026 espone la data di approvazione ma **non espone un timestamp storico di pubblicazione sul Portale**. Per questo:

- `approval_date` contiene esclusivamente la data di approvazione;
- `portal_publication_date` resta vuoto quando la fonte ufficiale non lo espone;
- `retrieved_at` registra quando il monitor ha osservato il PIAO.

Non vengono usati timestamp dei motori di ricerca, date dei PDF o header HTTP come sostituti della data ufficiale di pubblicazione.

## Output

### Una riga per comune

`piao_status.csv` contiene, per ogni comune:

- PIAO presente sul portale: sì/no;
- numero di PIAO osservati;
- presenza di un PIAO il cui **periodo di riferimento inizia nell'anno target** (es. `2026–2028` per target `2026`);
- ultimo periodo disponibile;
- ultima data di approvazione;
- URL dell'ultimo PIAO.

### Una riga per PIAO

`piao_publications.csv` e `piao_publications.jsonl` conservano tutti i PIAO osservati, non soltanto l'ultimo.

## Esecuzione

```bash
pip install -e ".[dev]"
pytest -q
python scripts/build_municipality_registry.py
python scripts/collect_piao.py --registry data/processed/municipalities.csv
```

## Documentazione

- [PIAO source and API](docs/PIAO_SOURCE.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Data model](docs/DATA_MODEL.md)
- [Municipality lineage](docs/LINEAGE.md)
- [Official sources](docs/SOURCES.md)

## Semantica dell'assenza

`piao_present_on_portal = false` significa soltanto che, durante quella rilevazione, l'API pubblica del Portale PIAO non ha restituito un PIAO per quel Codice IPA.

Non equivale automaticamente a inadempimento normativo.
