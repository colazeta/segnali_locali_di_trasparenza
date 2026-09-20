# Segnali locali di trasparenza

Monitor nazionale dei **PIAO pubblicati dai comuni italiani** sul Portale PIAO del Dipartimento della Funzione Pubblica.

## Perimetro corrente

In questa fase il progetto monitora **una sola cosa**:

> per ciascuno dei 7.894 comuni italiani correnti, esiste un PIAO sul Portale PIAO ufficiale e, in particolare, esiste il PIAO del ciclo target?

Per il ciclo corrente usato dal progetto:

> **target 2026 = PIAO 2026–2028**

Un PIAO 2025–2027 comprende l'anno 2026, ma **non** viene classificato come PIAO 2026–2028.

Non vengono monitorate genericamente le sezioni “Amministrazione trasparente” e non viene prodotto alcun punteggio di trasparenza.

## Base comunale

Il registry nazionale collega deterministicamente tutti i comuni correnti:

- **ISTAT / SITUAS** — identità territoriale;
- **IPA / AgID** — Codice IPA dell'ente;
- 7.894 comuni correnti;
- 7.894 collegamenti ISTAT ↔ IPA;
- 0 ambigui;
- 0 non collegati.

## Fonte PIAO

Fonte primaria:

- Portale PIAO — Dipartimento della Funzione Pubblica;
- catalogo pubblico: https://piao.dfp.gov.it/piao;
- endpoint JSON pubblico usato dal catalogo: `GET /api/piao?page=<N>`.

La pipeline produttiva acquisisce **l'intero catalogo nazionale pagina per pagina**, valida la completezza e poi collega localmente ogni record ai 7.894 comuni usando il Codice IPA completo restituito dal Portale.

Il lookup `GET /api/piao?ipaCode=<CODICE_IPA>&page=<N>` resta disponibile soltanto per diagnostica e validazione. Il parametro `ipaCode` non viene trattato come filtro esatto lato server: il Codice IPA restituito nel record viene sempre ricontrollato localmente.

## Snapshot nazionale validato iniziale — 20 settembre 2026

La validazione iniziale della pipeline bulk ha acquisito:

- **39.745** record complessivi dal catalogo ufficiale;
- **6.625 / 6.625** pagine;
- **0** pagine mancanti;
- **0** duplicati di pagina/record;
- **31.126** pubblicazioni PIAO collegate ai comuni;
- **7.370** comuni con almeno un PIAO;
- **4.692** comuni con un PIAO **2026–2028**;
- **2.678** comuni con PIAO precedenti ma senza 2026–2028;
- **524** comuni senza alcun PIAO osservato.

La pipeline bulk è stata confrontata con una baseline indipendente per-IPA, ripulita tramite il Codice IPA effettivamente restituito: **0 mismatch** negli identificativi delle pubblicazioni e nei campi comunali chiave.

## Metadati raccolti

Per ogni PIAO osservato vengono conservati:

- codice ISTAT del comune;
- Codice IPA;
- denominazione del comune e denominazione mostrata dal Portale;
- periodo di riferimento;
- anno iniziale e finale;
- versione;
- data di approvazione;
- estremi e autorità dell'atto di approvazione;
- URL ufficiale del documento PIAO;
- URL dell'atto;
- URL del PIAO sul sito dell'ente, quando disponibile;
- allegati;
- timestamp di acquisizione.

### Data di pubblicazione

La **data di approvazione** e la **data di pubblicazione sul Portale PIAO** sono concetti distinti.

L'API pubblica anonima verificata il 20 settembre 2026 espone la data di approvazione ma non espone un timestamp storico autorevole di pubblicazione sul Portale. Per questo:

- `approval_date` contiene esclusivamente la data di approvazione;
- `portal_publication_date` resta vuoto quando la fonte ufficiale non lo espone;
- `retrieved_at` registra quando il monitor ha osservato il PIAO.

Non vengono usati timestamp dei motori di ricerca, date interne dei PDF o header HTTP come sostituti della data ufficiale di pubblicazione.

## Stati analitici

Ogni comune viene ricondotto a uno stato mutuamente esclusivo:

- `target_period_present` — PIAO 2026–2028 osservato;
- `prior_period_only` — esistono PIAO, ma nessun 2026–2028;
- `no_piao_observed` — nessun PIAO osservato sul Portale;
- `lookup_error` — stato tecnico, mai trasformato in assenza.

## Output

### Una riga per comune

`piao_status.csv` contiene esattamente 7.894 righe e include:

- presenza di qualsiasi PIAO;
- numero di pubblicazioni;
- presenza del periodo target;
- ultimo periodo disponibile;
- ultima versione;
- ultima data di approvazione;
- URL dell'ultimo documento.

### Una riga per PIAO

`piao_publications.csv` e `piao_publications.jsonl` conservano tutte le pubblicazioni PIAO osservate.

### Analisi

Il workflow produce inoltre:

- stato del ciclo per comune;
- copertura per regione;
- copertura per area sovracomunale;
- summary nazionale.

## Automazione

Il workflow **national PIAO snapshot** esegue settimanalmente:

1. rebuild del registry ISTAT ↔ IPA;
2. acquisizione sharded del catalogo PIAO;
3. validazione integrale di tutte le pagine;
4. join esatto per Codice IPA;
5. costruzione degli output comunali e delle pubblicazioni;
6. tabelle analitiche nazionali e territoriali.

Se la copertura non è completa, lo snapshot non viene accettato.

## Esecuzione locale

Per test e diagnostica:

```bash
pip install -e ".[dev]"
pytest -q
python scripts/build_municipality_registry.py
python scripts/collect_piao.py --registry data/processed/municipalities.csv --istat-codes 079160
```

La scansione per-IPA non è la pipeline produttiva.

## Documentazione

- [PIAO source and API](docs/PIAO_SOURCE.md)
- [PIAO collection architecture](docs/PIAO_COLLECTION_ARCHITECTURE.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Data model](docs/DATA_MODEL.md)
- [Municipality lineage](docs/LINEAGE.md)
- [Official sources](docs/SOURCES.md)

## Semantica dell'assenza

`piao_present_on_portal = false` significa soltanto che, nello snapshot validato, il catalogo ufficiale non contiene un PIAO collegato a quel Codice IPA comunale.

Non equivale automaticamente a inadempimento normativo.
