from __future__ import annotations

import html
import json
import re
import shutil
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

from segnali_locali_di_trasparenza.timeliness import build_timeliness_table


STATUS_META = {
    "target_period_present": {
        "label": "PIAO {period} presente",
        "short": "{period} presente",
        "class": "status-target",
        "description": "Sul Portale PIAO è osservato almeno un piano che inizia nell'anno target.",
    },
    "prior_period_only": {
        "label": "Solo PIAO precedenti",
        "short": "Solo precedenti",
        "class": "status-prior",
        "description": "Sono presenti PIAO sul Portale, ma nessuno appartiene al ciclo target.",
    },
    "no_piao_observed": {
        "label": "Nessun PIAO osservato",
        "short": "Nessun PIAO",
        "class": "status-none",
        "description": "Nello snapshot validato non è stato osservato alcun PIAO per il Codice IPA comunale.",
    },
    "lookup_error": {
        "label": "Stato non determinabile",
        "short": "Errore tecnico",
        "class": "status-error",
        "description": "Un problema tecnico impedisce di determinare lo stato; non viene interpretato come assenza.",
    },
}


def _text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _truthy(value: object) -> bool:
    return _text(value).casefold() in {"true", "1", "yes", "si", "sì"}


def _safe_url(value: object) -> str:
    url = _text(value)
    if not url:
        return ""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return url


def _display_date(value: object) -> str:
    raw = _text(value)
    if not raw:
        return "—"
    parsed = pd.to_datetime(raw, errors="coerce")
    if pd.isna(parsed):
        return html.escape(raw)
    return parsed.strftime("%d/%m/%Y")


def _snapshot_date(value: object) -> str:
    raw = _text(value)
    if not raw:
        return ""
    parsed = pd.to_datetime(raw, errors="coerce", utc=True)
    if pd.isna(parsed):
        return raw
    return parsed.strftime("%d/%m/%Y")


def _slug(value: object) -> str:
    text = unicodedata.normalize("NFKD", _text(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "n-a"


def _with_base(base_path: str, path: str) -> str:
    base = "/" + base_path.strip("/") if base_path.strip("/") else ""
    suffix = "/" + path.lstrip("/") if path else "/"
    return f"{base}{suffix}"


def classify_status(row: pd.Series) -> str:
    if _text(row.get("lookup_status")).casefold() == "error":
        return "lookup_error"
    if _truthy(row.get("period_starting_target_year_present")):
        return "target_period_present"
    if _truthy(row.get("piao_present_on_portal")):
        return "prior_period_only"
    return "no_piao_observed"


def _status_label(status: str, target_period: str, *, short: bool = False) -> str:
    meta = STATUS_META[status]
    template = meta["short" if short else "label"]
    return template.format(period=target_period)


def _layout(
    *,
    title: str,
    description: str,
    body: str,
    base_path: str,
    body_class: str = "",
) -> str:
    css = _with_base(base_path, "assets/style.css")
    js = _with_base(base_path, "assets/app.js")
    home = _with_base(base_path, "")
    escaped_title = html.escape(title)
    escaped_description = html.escape(description)
    base_json = json.dumps("/" + base_path.strip("/") if base_path.strip("/") else "")
    return f"""<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  <meta name="description" content="{escaped_description}">
  <link rel="stylesheet" href="{css}">
</head>
<body class="{html.escape(body_class)}">
  <a class="skip-link" href="#main">Vai al contenuto</a>
  <header class="site-header">
    <div class="shell header-inner">
      <a class="brand" href="{home}" aria-label="PIAO nei comuni italiani — Home">
        <span class="brand-kicker">Segnali locali di trasparenza</span>
        <span class="brand-title">PIAO nei comuni italiani</span>
      </a>
      <a class="header-source" href="https://piao.dfp.gov.it/piao" rel="noopener noreferrer">Fonte ufficiale ↗</a>
    </div>
  </header>
  <main id="main">
{body}
  </main>
  <footer class="site-footer">
    <div class="shell footer-grid">
      <div>
        <strong>PIAO nei comuni italiani</strong>
        <p>Monitor indipendente costruito su dati del Portale PIAO del Dipartimento della Funzione Pubblica, ISTAT e IPA.</p>
      </div>
      <div>
        <p><a href="{_with_base(base_path, 'tempi/')}">Tempi di adozione</a></p>
        <p><a href="{_with_base(base_path, 'metodologia/')}">Metodologia</a></p>
        <p><a href="https://github.com/colazeta/segnali_locali_di_trasparenza" rel="noopener noreferrer">Codice e dati ↗</a></p>
      </div>
    </div>
  </footer>
  <script>window.PIAO_BASE_PATH = {base_json};</script>
  <script src="{js}" defer></script>
</body>
</html>
"""


def _metric_card(value: str, label: str, detail: str = "") -> str:
    detail_html = f'<span class="metric-detail">{html.escape(detail)}</span>' if detail else ""
    return f"""
      <div class="metric-card">
        <strong>{html.escape(value)}</strong>
        <span>{html.escape(label)}</span>
        {detail_html}
      </div>"""


def _build_home(
    municipalities: pd.DataFrame,
    region_summary: pd.DataFrame,
    *,
    base_path: str,
    target_period: str,
    snapshot_date: str,
) -> str:
    counts = municipalities["cycle_status"].value_counts().to_dict()
    total = len(municipalities)
    target = int(counts.get("target_period_present", 0))
    prior = int(counts.get("prior_period_only", 0))
    none = int(counts.get("no_piao_observed", 0))
    errors = int(counts.get("lookup_error", 0))

    metrics = "".join(
        [
            _metric_card(f"{total:,}".replace(",", "."), "comuni monitorati"),
            _metric_card(
                f"{target:,}".replace(",", "."),
                f"PIAO {target_period}",
                f"{target / total * 100:.1f}%" if total else "",
            ),
            _metric_card(
                f"{prior:,}".replace(",", "."),
                "solo PIAO precedenti",
                f"{prior / total * 100:.1f}%" if total else "",
            ),
            _metric_card(
                f"{none:,}".replace(",", "."),
                "nessun PIAO osservato",
                f"{none / total * 100:.1f}%" if total else "",
            ),
        ]
    )

    error_note = ""
    if errors:
        error_note = f'<p class="alert">Attenzione: {errors} comuni hanno uno stato tecnico non determinabile.</p>'

    rows = []
    for _, row in region_summary.sort_values("region_name").iterrows():
        reg_total = int(row["municipalities"])
        reg_target = int(row["target_period_present"])
        pct = reg_target / reg_total * 100 if reg_total else 0
        rows.append(
            f"""
            <tr>
              <th scope="row">{html.escape(_text(row["region_name"]))}</th>
              <td>{reg_total}</td>
              <td>{reg_target}</td>
              <td>{int(row["prior_period_only"])}</td>
              <td>{int(row["no_piao_observed"])}</td>
              <td>{pct:.1f}%</td>
            </tr>"""
        )
    table_rows = "".join(rows)

    body = f"""
    <section class="hero">
      <div class="shell hero-grid">
        <div>
          <p class="eyebrow">Monitor nazionale · ciclo {html.escape(target_period)}</p>
          <h1>Dove sono i PIAO {html.escape(target_period)}?</h1>
          <p class="hero-copy">Una fotografia verificabile dei Piani Integrati di Attività e Organizzazione pubblicati sul Portale PIAO per tutti i comuni italiani.</p>
          <p class="snapshot">Snapshot validato: <strong>{html.escape(snapshot_date or "—")}</strong></p>
        </div>
        <div class="source-card">
          <span>Fonte primaria</span>
          <strong>Portale PIAO</strong>
          <p>Il catalogo ufficiale viene acquisito integralmente e collegato ai comuni tramite Codice IPA.</p>
          <a href="https://piao.dfp.gov.it/piao" rel="noopener noreferrer">Apri il Portale PIAO ↗</a>
        </div>
      </div>
    </section>

    <section class="shell metrics" aria-label="Indicatori nazionali">
      {metrics}
    </section>

    <section class="shell evidence-panel">
      <h2>Quanto sono tempestivi i comuni?</h2>
      <p>La classifica confronta la prima data di approvazione osservata del PIAO {html.escape(target_period)} con la scadenza normativa applicabile al singolo comune.</p>
      <p><a class="button-link" href="{_with_base(base_path, 'tempi/')}">Apri la classifica dei tempi →</a></p>
    </section>

    {error_note}

    <section class="shell search-panel">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Cerca</p>
          <h2>Trova un comune</h2>
        </div>
        <p>Nome, codice ISTAT o regione.</p>
      </div>
      <div class="search-box">
        <label class="sr-only" for="municipality-search">Cerca un comune</label>
        <input id="municipality-search" type="search" autocomplete="off" placeholder="Es. Lamezia Terme, Milano, 079160…">
      </div>
      <div class="filter-row" role="group" aria-label="Filtra per stato PIAO">
        <button class="filter-button is-active" data-filter="all" type="button">Tutti</button>
        <button class="filter-button" data-filter="target_period_present" type="button">{html.escape(target_period)} presente</button>
        <button class="filter-button" data-filter="prior_period_only" type="button">Solo precedenti</button>
        <button class="filter-button" data-filter="no_piao_observed" type="button">Nessun PIAO</button>
      </div>
      <div id="search-results" class="search-results" aria-live="polite">
        <p class="search-hint">Inizia a digitare oppure scegli un filtro.</p>
      </div>
    </section>

    <section class="shell region-section">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Territorio</p>
          <h2>Copertura per regione</h2>
        </div>
        <p>Il dato indica la presenza del ciclo {html.escape(target_period)} sul Portale PIAO, non un giudizio di conformità.</p>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Regione</th>
              <th>Comuni</th>
              <th>{html.escape(target_period)}</th>
              <th>Solo precedenti</th>
              <th>Nessun PIAO</th>
              <th>Copertura ciclo</th>
            </tr>
          </thead>
          <tbody>{table_rows}</tbody>
        </table>
      </div>
    </section>
    """
    return _layout(
        title=f"PIAO {target_period} nei comuni italiani",
        description=f"Monitor nazionale della presenza dei PIAO {target_period} nei comuni italiani.",
        body=body,
        base_path=base_path,
        body_class="home",
    )


def _publication_rows(publications: pd.DataFrame) -> str:
    if publications.empty:
        return '<p class="empty-state">Nessuna pubblicazione PIAO osservata per questo comune.</p>'

    rows: list[str] = []
    for _, item in publications.iterrows():
        period = html.escape(_text(item.get("reference_period")) or "—")
        version = html.escape(_text(item.get("version")) or "—")
        approval = _display_date(item.get("approval_date"))
        document = _safe_url(item.get("piao_document_url"))
        act = _safe_url(item.get("approval_act_url"))
        institutional = _safe_url(item.get("institutional_piao_url"))

        links = []
        if document:
            links.append(f'<a href="{html.escape(document, quote=True)}" rel="noopener noreferrer">PIAO ↗</a>')
        if act:
            links.append(f'<a href="{html.escape(act, quote=True)}" rel="noopener noreferrer">Atto ↗</a>')
        if institutional:
            links.append(f'<a href="{html.escape(institutional, quote=True)}" rel="noopener noreferrer">Sito ente ↗</a>')
        link_html = " · ".join(links) if links else "—"

        rows.append(
            f"""
            <tr>
              <td><strong>{period}</strong></td>
              <td>{version}</td>
              <td>{approval}</td>
              <td>{link_html}</td>
            </tr>"""
        )
    return f"""
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Periodo</th>
              <th>Versione</th>
              <th>Data approvazione</th>
              <th>Documenti</th>
            </tr>
          </thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </div>"""


def _build_municipality_page(
    row: pd.Series,
    publications: pd.DataFrame,
    *,
    base_path: str,
    target_period: str,
    snapshot_date: str,
) -> str:
    status = _text(row["cycle_status"])
    meta = STATUS_META[status]
    name = _text(row["name"])
    region = _text(row["region_name"])
    supra = _text(row["supra_name"])
    istat = _text(row["istat_code"])
    ipa = _text(row["ipa_code"])
    latest_period = _text(row.get("latest_reference_period")) or "—"
    latest_version = _text(row.get("latest_version")) or "—"
    approval = _display_date(row.get("latest_approval_date"))
    publication_count = int(float(_text(row.get("publication_count")) or 0))

    deadline = _display_date(row.get("expected_piao_deadline"))
    lag_raw = _text(row.get("approval_lag_days"))
    overdue_raw = _text(row.get("days_overdue_at_snapshot"))
    timeliness_status = _text(row.get("timeliness_status"))
    if lag_raw:
        lag = int(float(lag_raw))
        lag_value = "0 giorni" if lag == 0 else f"{lag:+d} giorni"
        timeliness_metric = _metric_card(
            lag_value,
            "lag di approvazione",
            f"scadenza {deadline}",
        )
    elif timeliness_status == "target_not_observed" and overdue_raw:
        overdue = int(float(overdue_raw))
        timeliness_metric = _metric_card(
            f"≥ {overdue} giorni",
            "ritardo minimo accumulato",
            f"scadenza {deadline}",
        )
    else:
        timeliness_metric = _metric_card("n.d.", "lag di approvazione", f"scadenza {deadline}")

    history = _publication_rows(publications)

    body = f"""
    <section class="municipality-hero">
      <div class="shell">
        <nav class="breadcrumb" aria-label="Percorso">
          <a href="{_with_base(base_path, '')}">Italia</a>
          <span>›</span>
          <span>{html.escape(region)}</span>
        </nav>
        <div class="municipality-title-row">
          <div>
            <p class="eyebrow">{html.escape(region)} · {html.escape(supra)}</p>
            <h1>{html.escape(name)}</h1>
            <p class="codes">ISTAT {html.escape(istat)} · IPA {html.escape(ipa)}</p>
          </div>
          <div class="status-pill {meta['class']}">{html.escape(_status_label(status, target_period))}</div>
        </div>
        <p class="status-explainer">{html.escape(meta['description'])}</p>
      </div>
    </section>

    <section class="shell municipality-metrics">
      {_metric_card(latest_period, "ultimo PIAO osservato")}
      {_metric_card(latest_version, "ultima versione")}
      {_metric_card(approval, "ultima approvazione")}
      {_metric_card(str(publication_count), "pubblicazioni osservate")}
      {timeliness_metric}
    </section>

    <section class="shell content-section">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Cronologia</p>
          <h2>PIAO disponibili sul Portale</h2>
        </div>
        <p>Ordinati dal periodo e dalla versione più recenti.</p>
      </div>
      {history}
    </section>

    <section class="shell evidence-panel">
      <h2>Come leggere questo dato</h2>
      <p>Lo stato descrive ciò che è stato osservato nel catalogo pubblico del Portale PIAO nello snapshot del <strong>{html.escape(snapshot_date or "—")}</strong>. “Nessun PIAO osservato” non equivale automaticamente a inadempimento normativo.</p>
      <p><strong>Data di approvazione</strong> e <strong>data di pubblicazione sul Portale</strong> restano distinte. L'API pubblica verificata non espone oggi un timestamp storico autorevole di pubblicazione sul Portale.</p>
      <p><a href="{_with_base(base_path, 'metodologia/')}">Leggi la metodologia completa →</a></p>
    </section>
    """

    return _layout(
        title=f"{name} — PIAO {target_period}",
        description=f"PIAO osservati sul Portale PIAO per il Comune di {name}.",
        body=body,
        base_path=base_path,
        body_class="municipality",
    )


def _build_timeliness_page(
    timeliness: pd.DataFrame,
    *,
    base_path: str,
    target_period: str,
    snapshot_date: str,
) -> str:
    lag = pd.to_numeric(timeliness["approval_lag_days"], errors="coerce")
    ranked = timeliness.loc[lag.notna()].copy()
    ranked["_lag"] = lag.loc[ranked.index].astype(int)
    ranked = ranked.sort_values(
        ["_lag", "region_name", "name", "istat_code"],
        kind="stable",
    )

    pending = timeliness.loc[
        timeliness["timeliness_status"].eq("target_not_observed")
    ].copy()
    pending["_overdue"] = pd.to_numeric(
        pending["days_overdue_at_snapshot"], errors="coerce"
    )
    pending = pending.sort_values(
        ["_overdue", "region_name", "name", "istat_code"],
        ascending=[False, True, True, True],
        na_position="last",
        kind="stable",
    )

    missing_date = timeliness.loc[
        timeliness["timeliness_status"].eq("target_present_approval_date_missing")
    ].copy()

    on_time = int((ranked["_lag"] <= 0).sum())
    late = int((ranked["_lag"] > 0).sum())
    median_lag = ranked["_lag"].median() if not ranked.empty else None
    median_text = (
        "—"
        if median_lag is None or pd.isna(median_lag)
        else f"{median_lag:+.0f} giorni"
    )

    ranked_rows: list[str] = []
    for _, row in ranked.iterrows():
        code = _text(row["istat_code"])
        rank = _text(row.get("approval_lag_rank_national")) or "—"
        lag_days = int(row["_lag"])
        lag_text = "0" if lag_days == 0 else f"{lag_days:+d}"
        status = (
            "In anticipo"
            if lag_days < 0
            else "In scadenza"
            if lag_days == 0
            else "In ritardo"
        )
        ranked_rows.append(
            f"""
            <tr>
              <td>{html.escape(rank)}</td>
              <th scope="row"><a href="{_with_base(base_path, f'comune/{code}/')}">{html.escape(_text(row["name"]))}</a></th>
              <td>{html.escape(_text(row["region_name"]))}</td>
              <td>{_display_date(row["expected_piao_deadline"])}</td>
              <td>{_display_date(row["target_first_approval_date"])}</td>
              <td>{html.escape(lag_text)}</td>
              <td>{html.escape(status)}</td>
            </tr>"""
        )

    pending_rows: list[str] = []
    for _, row in pending.iterrows():
        code = _text(row["istat_code"])
        overdue = _text(row.get("days_overdue_at_snapshot"))
        overdue_text = f"≥ {int(float(overdue))}" if overdue else "—"
        pending_rows.append(
            f"""
            <tr>
              <th scope="row"><a href="{_with_base(base_path, f'comune/{code}/')}">{html.escape(_text(row["name"]))}</a></th>
              <td>{html.escape(_text(row["region_name"]))}</td>
              <td>{_display_date(row["expected_piao_deadline"])}</td>
              <td>{html.escape(overdue_text)}</td>
            </tr>"""
        )

    missing_date_note = ""
    if not missing_date.empty:
        missing_date_note = (
            f'<p class="alert">{len(missing_date)} comuni hanno un PIAO {html.escape(target_period)} '
            "osservato ma senza una data di approvazione utilizzabile e non entrano nella classifica.</p>"
        )

    body = f"""
    <section class="hero">
      <div class="shell">
        <p class="eyebrow">Tempestività · ciclo {html.escape(target_period)}</p>
        <h1>Tempi di adozione dei PIAO</h1>
        <p class="hero-copy">Confronto tra la prima data di approvazione osservata del PIAO target e la scadenza normativa applicabile a ciascun comune.</p>
        <p class="snapshot">Snapshot validato: <strong>{html.escape(snapshot_date or "—")}</strong></p>
      </div>
    </section>

    <section class="shell metrics" aria-label="Indicatori di tempestività">
      {_metric_card(str(len(ranked)), "comuni classificabili")}
      {_metric_card(str(on_time), "entro la scadenza")}
      {_metric_card(str(late), "oltre la scadenza")}
      {_metric_card(median_text, "lag mediano")}
    </section>

    <section class="shell evidence-panel">
      <h2>Come leggere il lag</h2>
      <p>Il valore è <strong>data della prima approvazione osservata − scadenza applicabile</strong>. Un valore negativo indica un'approvazione anticipata; zero indica il giorno della scadenza; un valore positivo indica ritardo.</p>
      <p>Per il 2026 la scadenza è il 30 marzo per la generalità degli enti locali e il 30 aprile per i comuni di Calabria, Sardegna e Sicilia. Questa è una classifica di <strong>adozione</strong>, non della data storica di pubblicazione sul Portale, che l'API pubblica non espone.</p>
      {missing_date_note}
    </section>

    <section class="shell region-section">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Ranking</p>
          <h2>Classifica nazionale per lag di approvazione</h2>
        </div>
        <p>I pari merito condividono lo stesso rango.</p>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Rango</th>
              <th>Comune</th>
              <th>Regione</th>
              <th>Scadenza</th>
              <th>Prima approvazione</th>
              <th>Lag giorni</th>
              <th>Stato</th>
            </tr>
          </thead>
          <tbody>{''.join(ranked_rows)}</tbody>
        </table>
      </div>
    </section>

    <section class="shell region-section">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Censura a destra</p>
          <h2>PIAO target non ancora osservato</h2>
        </div>
        <p>Il ritardo è un limite inferiore alla data dello snapshot, non un lag finale.</p>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Comune</th>
              <th>Regione</th>
              <th>Scadenza</th>
              <th>Ritardo minimo (giorni)</th>
            </tr>
          </thead>
          <tbody>{''.join(pending_rows)}</tbody>
        </table>
      </div>
    </section>
    """
    return _layout(
        title=f"Tempi di adozione PIAO {target_period}",
        description=f"Classifica dei comuni italiani per tempestività di approvazione del PIAO {target_period}.",
        body=body,
        base_path=base_path,
        body_class="timeliness-page",
    )


def _build_methodology(*, base_path: str, target_period: str, snapshot_date: str) -> str:
    body = f"""
    <section class="shell methodology">
      <p class="eyebrow">Metodo</p>
      <h1>Come funziona il monitor</h1>
      <p class="lead">Il monitor acquisisce integralmente il catalogo pubblico del Portale PIAO, ne valida la completezza e collega le pubblicazioni ai comuni tramite Codice IPA.</p>

      <div class="method-grid">
        <article>
          <span>1</span>
          <h2>Universo dei comuni</h2>
          <p>Il registry corrente contiene 7.894 comuni ISTAT, ciascuno collegato deterministicamente al relativo ente IPA.</p>
        </article>
        <article>
          <span>2</span>
          <h2>Catalogo PIAO</h2>
          <p>Il catalogo ufficiale viene acquisito pagina per pagina. Uno snapshot è accettato solo se tutte le pagine attese sono presenti e il totale coincide con quello dichiarato dall'API.</p>
        </article>
        <article>
          <span>3</span>
          <h2>Join esatto</h2>
          <p>Ogni pubblicazione è associata al comune mediante il Codice IPA completo restituito nel record. Non vengono usati fuzzy matching per la pipeline produttiva.</p>
        </article>
        <article>
          <span>4</span>
          <h2>Ciclo target</h2>
          <p>Per il target corrente, “PIAO {html.escape(target_period)} presente” significa che esiste un record il cui periodo di riferimento inizia nel 2026. Un 2025–2027 non soddisfa questa condizione.</p>
        </article>
      </div>

      <h2>Date e limiti</h2>
      <p>La data di approvazione proviene dal campo ufficiale dell'API. Non viene reinterpretata come data di pubblicazione. Quando il Portale non espone un timestamp storico di pubblicazione, quel campo resta vuoto.</p>

      <h2>Snapshot</h2>
      <p>Questa versione del sito usa lo snapshot validato del <strong>{html.escape(snapshot_date or "—")}</strong>. Gli aggiornamenti produttivi sono pianificati settimanalmente.</p>

      <h2>Riproducibilità</h2>
      <p>Codice, controlli di qualità e documentazione sono pubblici nel repository del progetto.</p>
      <p><a class="button-link" href="https://github.com/colazeta/segnali_locali_di_trasparenza" rel="noopener noreferrer">Apri il repository ↗</a></p>
    </section>
    """
    return _layout(
        title="Metodologia — PIAO nei comuni italiani",
        description="Metodologia del monitor nazionale dei PIAO comunali.",
        body=body,
        base_path=base_path,
        body_class="methodology-page",
    )


def build_site(
    *,
    registry_path: Path,
    status_path: Path,
    publications_path: Path,
    output_dir: Path,
    assets_dir: Path,
    base_path: str = "",
) -> dict[str, object]:
    registry = pd.read_csv(registry_path, dtype=str, keep_default_na=False)
    status = pd.read_csv(status_path, dtype=str, keep_default_na=False)
    publications = pd.read_csv(publications_path, dtype=str, keep_default_na=False)

    registry["istat_code"] = registry["istat_code"].astype(str).str.zfill(6)
    status["istat_code"] = status["istat_code"].astype(str).str.zfill(6)
    publications["istat_code"] = publications["istat_code"].astype(str).str.zfill(6)

    target_year_values = {
        int(value)
        for value in status["target_start_year"]
        if _text(value).isdigit()
    }
    if len(target_year_values) != 1:
        raise ValueError(f"Expected one target start year, found {sorted(target_year_values)}")
    target_year = next(iter(target_year_values))
    target_period = f"{target_year}–{target_year + 2}"

    joined = registry[
        ["istat_code", "name", "region_name", "supra_name", "ipa_code"]
    ].merge(
        status,
        on="istat_code",
        how="left",
        validate="one_to_one",
        suffixes=("", "_status"),
    )
    if len(joined) != len(registry):
        raise ValueError("Municipality join changed registry row count")
    if joined["lookup_status"].eq("").any():
        raise ValueError("Status is missing for at least one municipality")

    joined["cycle_status"] = joined.apply(classify_status, axis=1)

    timeliness = build_timeliness_table(registry, status, publications)
    timeliness_columns = [
        "istat_code",
        "target_first_approval_date",
        "expected_piao_deadline",
        "approval_lag_days",
        "timeliness_status",
        "approval_lag_rank_national",
        "approval_lag_rank_region",
        "days_overdue_at_snapshot",
    ]
    joined = joined.merge(
        timeliness[timeliness_columns],
        on="istat_code",
        how="left",
        validate="one_to_one",
    )

    snapshot_date = _snapshot_date(status["retrieved_at"].max())

    region_rows: list[dict[str, object]] = []
    for region_name, group in joined.groupby("region_name", sort=True):
        counts = group["cycle_status"].value_counts().to_dict()
        region_rows.append(
            {
                "region_name": region_name,
                "municipalities": len(group),
                "target_period_present": int(counts.get("target_period_present", 0)),
                "prior_period_only": int(counts.get("prior_period_only", 0)),
                "no_piao_observed": int(counts.get("no_piao_observed", 0)),
                "lookup_error": int(counts.get("lookup_error", 0)),
            }
        )
    region_summary = pd.DataFrame(region_rows)

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "assets").mkdir(parents=True, exist_ok=True)
    (output_dir / "data").mkdir(parents=True, exist_ok=True)
    (output_dir / "comune").mkdir(parents=True, exist_ok=True)
    (output_dir / "tempi").mkdir(parents=True, exist_ok=True)
    (output_dir / "metodologia").mkdir(parents=True, exist_ok=True)

    for asset in ["style.css", "app.js"]:
        source = assets_dir / asset
        if not source.exists():
            raise FileNotFoundError(f"Missing site asset: {source}")
        shutil.copy2(source, output_dir / "assets" / asset)

    (output_dir / ".nojekyll").write_text("", encoding="utf-8")

    home = _build_home(
        joined,
        region_summary,
        base_path=base_path,
        target_period=target_period,
        snapshot_date=snapshot_date,
    )
    (output_dir / "index.html").write_text(home, encoding="utf-8")

    timeliness_page = _build_timeliness_page(
        timeliness,
        base_path=base_path,
        target_period=target_period,
        snapshot_date=snapshot_date,
    )
    (output_dir / "tempi" / "index.html").write_text(
        timeliness_page,
        encoding="utf-8",
    )

    methodology = _build_methodology(
        base_path=base_path,
        target_period=target_period,
        snapshot_date=snapshot_date,
    )
    (output_dir / "metodologia" / "index.html").write_text(
        methodology,
        encoding="utf-8",
    )

    grouped_publications = {
        code: group.sort_values(
            ["reference_start_year", "version", "approval_date"],
            ascending=[False, False, False],
            kind="stable",
        )
        for code, group in publications.groupby("istat_code")
    }

    search_records: list[dict[str, object]] = []
    for _, row in joined.sort_values(["name", "istat_code"]).iterrows():
        code = _text(row["istat_code"])
        municipality_dir = output_dir / "comune" / code
        municipality_dir.mkdir(parents=True, exist_ok=True)
        page = _build_municipality_page(
            row,
            grouped_publications.get(code, publications.iloc[0:0]),
            base_path=base_path,
            target_period=target_period,
            snapshot_date=snapshot_date,
        )
        (municipality_dir / "index.html").write_text(page, encoding="utf-8")

        status_key = _text(row["cycle_status"])
        search_records.append(
            {
                "istat_code": code,
                "name": _text(row["name"]),
                "region": _text(row["region_name"]),
                "supra": _text(row["supra_name"]),
                "status": status_key,
                "status_label": _status_label(status_key, target_period, short=True),
                "latest_period": _text(row.get("latest_reference_period")),
                "href": _with_base(base_path, f"comune/{code}/"),
            }
        )

    (output_dir / "data" / "municipalities.json").write_text(
        json.dumps(search_records, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    timeliness.to_json(
        output_dir / "data" / "piao_timeliness_ranking.json",
        orient="records",
        force_ascii=False,
    )

    summary = {
        "municipalities": len(joined),
        "publication_rows": len(publications),
        "target_start_year": target_year,
        "target_period": target_period,
        "snapshot_date": snapshot_date,
        "status_counts": {
            key: int((joined["cycle_status"] == key).sum())
            for key in STATUS_META
        },
        "pages": {
            "home": 1,
            "timeliness": 1,
            "methodology": 1,
            "municipality": len(joined),
        },
    }
    (output_dir / "data" / "site-build.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary
