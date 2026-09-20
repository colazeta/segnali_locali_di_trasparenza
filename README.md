# Segnali locali di trasparenza

Monitor nazionale, verificabile e versionato di segnali osservabili di trasparenza nei comuni italiani.

## Obiettivo

Il progetto costruisce una base canonica dei comuni italiani e registra nel tempo segnali di trasparenza pubblica come osservazioni separate, datate e corredate da evidenze.

Principi iniziali:

- il **comune** è un'entità amministrativa versionata nel tempo;
- l'**ente pubblico** che rappresenta il comune è collegato, ma non coincide concettualmente con esso;
- un **segnale di trasparenza** è un'osservazione riproducibile con fonte, timestamp, evidenza e versione metodologica;
- nessun punteggio sintetico viene introdotto prima di aver definito e validato indicatori osservabili;
- le fonti nazionali ufficiali sono preferite alle ricostruzioni proprietarie;
- la UI pubblica non deve dipendere in tempo reale da servizi esterni non controllati.

## Milestone 0 — Registry nazionale dei comuni

Il primo layer collega:

1. **ISTAT / SITUAS** — identità territoriale canonica e variazioni amministrative;
2. **IPA / AgID** — identità dell'ente pubblico, Codice IPA, codice fiscale e sito istituzionale;
3. **Cruscotto Italia / AgID** — enrichment e controlli incrociati per codice ISTAT.

Il codice ISTAT a 6 cifre è la chiave corrente di interoperabilità, ma non viene trattato come identificatore eterno: la successiva lineage layer conserverà ricodifiche, fusioni, soppressioni e cambi di denominazione.

## Esecuzione

Richiede Python 3.11+.

```bash
pip install -e ".[dev]"
pytest -q
python scripts/build_municipality_registry.py
```

Il build scarica le fonti ufficiali in `data/raw/` (non versionata) e produce:

- `data/processed/municipalities.csv`
- `data/processed/municipalities.jsonl`
- `data/manifests/municipality_registry.json`

Il manifest registra timestamp, URL delle fonti, hash dei file scaricati e metriche di linkage.

## Linkage ISTAT ↔ IPA

Il join è deliberatamente conservativo. IPA categoria `L6` comprende anche consorzi e associazioni di comuni; per questo i casi non deterministici sono marcati `ambiguous` o `unmatched`, non risolti tramite fuzzy matching automatico.

## Documentazione

- [Architecture](docs/ARCHITECTURE.md)
- [Data model](docs/DATA_MODEL.md)
- [Official sources](docs/SOURCES.md)

## Automazione

GitHub Actions esegue test e lint sulle modifiche e ricostruisce settimanalmente uno snapshot del registry usando le fonti ufficiali. Lo snapshot viene pubblicato come artifact di workflow; non viene ancora auto-committato nel repository.

## Stato

Repository inizializzato il 20 settembre 2026. La milestone 0 precede i collector specifici di trasparenza.
