# Segnali locali di trasparenza

Monitor nazionale, verificabile e versionato di segnali di trasparenza nei comuni italiani.

## Stato corrente

La base nazionale contiene tutti i **7.894 comuni italiani correnti**, collegati deterministicamente tra ISTAT e IPA.

Il primo segnale attivo è:

> **Signal 001 — presenza del PIAO e metadati del Piano sul Portale PIAO del Dipartimento della Funzione Pubblica.**

Non viene utilizzato un punteggio sintetico.

## Registry nazionale

Le fonti di identità sono:

1. **ISTAT / SITUAS** — identità territoriale e variazioni amministrative;
2. **IPA / AgID** — identità dell'ente pubblico e Codice IPA;
3. **Cruscotto Italia / AgID** — enrichment e controlli incrociati.

## Signal 001 — PIAO

Per ogni PIAO osservato sul portale ufficiale vengono raccolti almeno:

- comune e codice ISTAT;
- Codice IPA;
- triennio di riferimento;
- data di approvazione;
- eventuale timestamp di pubblicazione sul Portale PIAO, se esplicitamente esposto nei metadati;
- URL della scheda sul Portale PIAO;
- URL del PDF;
- URL della pubblicazione sul sito dell'ente, quando disponibile;
- timestamp della nostra acquisizione;
- hash dell'HTML sorgente.

Il sistema mantiene tutti i PIAO storici disponibili, non soltanto l'ultimo.

**Data di approvazione e data di pubblicazione non vengono confuse.**

## Esecuzione

Richiede Python 3.11+.

```bash
pip install -e ".[dev]"
pytest -q
python scripts/build_municipality_registry.py
python scripts/collect_piao.py --registry data/processed/municipalities.csv
```

## Output principali

Registry:

- `data/processed/municipalities.csv`
- `data/processed/municipalities.jsonl`

PIAO:

- `data/piao/piao_plans.csv`
- `data/piao/piao_plans.jsonl`
- `data/piao/municipalities_piao.csv`
- `data/piao/piao_unmatched.csv`
- `data/piao/manifest.json`

## Documentazione

- [Architecture](docs/ARCHITECTURE.md)
- [Data model](docs/DATA_MODEL.md)
- [PIAO signal](docs/PIAO.md)
- [Official sources](docs/SOURCES.md)
- [Municipality lineage](docs/LINEAGE.md)

## Automazione

GitHub Actions valida registry e lineage e testa il collector PIAO su record reali del Portale. Un workflow separato è predisposto per la raccolta nazionale periodica dei PIAO.
