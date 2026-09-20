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

Costruire il registry nazionale dei comuni collegando:

1. **ISTAT / SITUAS** — identità territoriale canonica e variazioni amministrative;
2. **IPA / AgID** — identità dell'ente pubblico, Codice IPA, codice fiscale, sito, PEC e altri metadati;
3. **Cruscotto Italia / AgID** — enrichment e controlli incrociati per codice ISTAT.

La chiave territoriale primaria di interoperabilità è il **codice ISTAT a 6 cifre**, preservando però la storia delle ricodifiche e delle variazioni.

## Stato

Repository inizializzato il 20 settembre 2026. La prima implementazione viene sviluppata nella milestone 0 prima di introdurre collector di trasparenza specifici.
