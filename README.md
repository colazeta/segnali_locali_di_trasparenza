# Segnali locali di trasparenza

Monitor nazionale dei **PIAO pubblicati dai comuni italiani**.

## Perimetro attuale

Per ora il progetto monitora un solo fenomeno: la presenza di PIAO sul **Portale PIAO ufficiale del Dipartimento della Funzione Pubblica**.

Per ciascuno dei 7.894 comuni il sistema mantiene l'anagrafica ISTAT↔IPA e raccoglie tutte le schede PIAO reperibili sul portale ufficiale.

Per ogni PIAO conserva almeno:

- comune e codice ISTAT;
- codice IPA;
- presenza sul Portale PIAO;
- anno/triennio di riferimento;
- data di approvazione;
- data di pubblicazione sul Portale PIAO, quando esposta dai metadati della pagina;
- URL della scheda ufficiale;
- URL del PDF;
- eventuale link al PIAO sul sito dell'ente;
- timestamp e hash dell'osservazione.

**Data di approvazione e data di pubblicazione restano campi distinti.** Se il Portale non espone una data di pubblicazione affidabile, il campo resta vuoto.

## Fonti

1. ISTAT / SITUAS — identità e storia amministrativa dei comuni;
2. IPA / AgID — identificazione dell'ente pubblico e codice IPA;
3. Portale PIAO / Dipartimento della Funzione Pubblica — fonte primaria delle pubblicazioni PIAO.

## Output

- `data/observations/piao_publications.csv` — tutte le pubblicazioni PIAO osservate;
- `data/processed/municipalities_piao_latest.csv` — un record per comune con l'ultimo PIAO osservato;
- `data/manifests/piao_snapshot.json` — copertura, conteggi e provenance.

Il progetto **non produce attualmente score di trasparenza** e non monitora genericamente la sezione “Amministrazione trasparente”.

Vedi [PIAO monitor](docs/PIAO_MONITOR.md) per la metodologia.
