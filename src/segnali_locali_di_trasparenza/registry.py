from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Iterable
from pathlib import Path

import pandas as pd
import requests


ISTAT_URL = (
    "https://www.istat.it/storage/codici-unita-amministrative/"
    "Elenco-comuni-italiani.xlsx"
)
IPA_URL = (
    "https://indicepa.gov.it/ipa-dati/dataset/"
    "5baa3eb8-266e-455a-8de8-b1f434c279b2/resource/"
    "d09adf99-dc10-4349-8c53-27b1e5aa97b6/download/enti.xlsx"
)

MUNICIPALITY_IPA_CATEGORY = "L6"
MUNICIPAL_PREFIX_RE = re.compile(
    r"^\s*(?:comune(?:\s+di)?|gemeinde|comun(?:\s+de)?|municipio)\b\s*",
    flags=re.IGNORECASE,
)


def download(url: str, destination: Path, timeout: int = 90) -> str:
    """Download a source file and return its SHA-256 digest."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": "segnali-locali-di-trasparenza/0.1"},
    )
    response.raise_for_status()
    destination.write_bytes(response.content)
    return hashlib.sha256(response.content).hexdigest()


def normalise_header(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("\n", " ")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def normalise_name(value: object) -> str:
    if pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = MUNICIPAL_PREFIX_RE.sub("", text.lower())
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def name_aliases(*values: object) -> set[str]:
    """Build deterministic aliases from official multilingual municipality names."""
    aliases: set[str] = set()
    for value in values:
        if pd.isna(value) or not str(value).strip():
            continue
        text = str(value).strip()
        pieces = [text, *re.split(r"\s*(?:/|\||;| – | - )\s*", text)]
        for piece in pieces:
            normalised = normalise_name(piece)
            if normalised:
                aliases.add(normalised)
    return aliases


def clean_code(value: object, width: int | None = None) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().removesuffix(".0")
    text = re.sub(r"\s+", "", text)
    if width and text.isdigit():
        return text.zfill(width)
    return text


def _resolve_column(
    frame: pd.DataFrame,
    aliases: Iterable[str],
    *,
    required: bool = True,
) -> str | None:
    lookup = {normalise_header(column): str(column) for column in frame.columns}
    for alias in aliases:
        key = normalise_header(alias)
        if key in lookup:
            return lookup[key]

    for alias in aliases:
        key = normalise_header(alias)
        matches = [original for normalised, original in lookup.items() if key in normalised]
        if len(matches) == 1:
            return matches[0]

    if required:
        raise KeyError(
            f"Unable to resolve expected column. aliases={list(aliases)!r}; "
            f"available={list(frame.columns)!r}"
        )
    return None


def read_istat(path: Path) -> pd.DataFrame:
    """Normalise the current ISTAT municipality workbook to the project schema."""
    raw = pd.read_excel(path, dtype=str, keep_default_na=False)

    columns = {
        "istat_code": _resolve_column(
            raw,
            ["Codice Comune formato alfanumerico", "Codice Comune formato numerico"],
        ),
        "name": _resolve_column(raw, ["Denominazione in italiano"]),
        "name_full": _resolve_column(
            raw,
            ["Denominazione (Italiana e straniera)"],
            required=False,
        ),
        "name_other": _resolve_column(
            raw,
            ["Denominazione altra lingua"],
            required=False,
        ),
        "region_code": _resolve_column(raw, ["Codice Regione"]),
        "region_name": _resolve_column(raw, ["Denominazione Regione"]),
        "supra_code": _resolve_column(
            raw,
            [
                "Codice dell'Unità territoriale sovracomunale (valida a fini statistici)",
                "Codice Provincia (Storico)",
            ],
        ),
        "supra_name": _resolve_column(
            raw,
            [
                (
                    "Denominazione dell'Unità territoriale sovracomunale "
                    "(valida a fini statistici)"
                ),
                "Denominazione dell'Unità territoriale sovracomunale",
            ],
        ),
        "province_abbr": _resolve_column(raw, ["Sigla automobilistica"], required=False),
        "cadastral_code": _resolve_column(raw, ["Codice Catastale del comune"], required=False),
    }

    out = pd.DataFrame(index=raw.index)
    out["municipality_version_id"] = raw[columns["istat_code"]].map(
        lambda value: f"IT-ISTAT-{clean_code(value, 6)}"
    )
    out["istat_code"] = raw[columns["istat_code"]].map(lambda value: clean_code(value, 6))
    out["name"] = raw[columns["name"]].astype("string").str.strip()

    for target in ["name_full", "name_other"]:
        source = columns[target]
        out[target] = (
            raw[source].fillna("").astype(str).str.strip() if source else ""
        )

    out["region_code"] = raw[columns["region_code"]].map(lambda value: clean_code(value, 2))
    out["region_name"] = raw[columns["region_name"]].astype("string").str.strip()
    out["supra_code"] = raw[columns["supra_code"]].map(lambda value: clean_code(value, 3))
    out["supra_name"] = raw[columns["supra_name"]].astype("string").str.strip()

    if columns["province_abbr"]:
        out["province_abbr"] = raw[columns["province_abbr"]].fillna("").astype(str).str.strip()
    else:
        out["province_abbr"] = ""

    if columns["cadastral_code"]:
        out["cadastral_code"] = (
            raw[columns["cadastral_code"]].fillna("").astype(str).str.strip().str.upper()
        )
    else:
        out["cadastral_code"] = ""

    out["name_normalised"] = out["name"].map(normalise_name)

    if out["istat_code"].eq("").any():
        raise ValueError("ISTAT source contains empty municipality codes after normalisation")
    if out["istat_code"].duplicated().any():
        duplicated = out.loc[out["istat_code"].duplicated(False), "istat_code"].tolist()
        raise ValueError(f"Duplicate current ISTAT municipality codes: {duplicated[:20]}")

    return out.reset_index(drop=True)


def read_ipa(path: Path) -> pd.DataFrame:
    """Read IPA entities and retain only the fields needed for municipality linkage."""
    raw = pd.read_excel(path, dtype=str, keep_default_na=False)

    needed = {
        "ipa_code": "Codice_IPA",
        "ipa_name": "Denominazione_ente",
        "fiscal_code": "Codice_fiscale_ente",
        "ipa_category": "Codice_Categoria",
        "seat_istat_code": "Codice_comune_ISTAT",
        "seat_cadastral_code": "Codice_catastale_comune",
        "institutional_url": "Sito_istituzionale",
        "updated_at_ipa": "Data_aggiornamento",
    }

    resolved = {
        target: _resolve_column(raw, [source], required=target != "updated_at_ipa")
        for target, source in needed.items()
    }

    out = pd.DataFrame(index=raw.index)
    for target, source_column in resolved.items():
        if source_column is None:
            out[target] = ""
        else:
            out[target] = raw[source_column].fillna("").astype(str).str.strip()

    out["seat_istat_code"] = out["seat_istat_code"].map(lambda value: clean_code(value, 6))
    out["seat_cadastral_code"] = out["seat_cadastral_code"].str.upper()
    out["ipa_category"] = out["ipa_category"].str.upper()
    out["ipa_name_normalised"] = out["ipa_name"].map(normalise_name)
    out["looks_like_municipality"] = out["ipa_name"].str.match(MUNICIPAL_PREFIX_RE, na=False)

    return out.reset_index(drop=True)


def _official_aliases(
    municipality: pd.Series,
    curated_aliases: dict[str, list[str]] | None,
) -> set[str]:
    aliases = name_aliases(
        municipality.get("name", ""),
        municipality.get("name_full", ""),
        municipality.get("name_other", ""),
    )
    if curated_aliases:
        aliases.update(
            name_aliases(*curated_aliases.get(str(municipality["istat_code"]), []))
        )
    return aliases


def _location_candidates(
    municipality: pd.Series,
    ipa_municipal_entities: pd.DataFrame,
) -> pd.DataFrame:
    candidates = ipa_municipal_entities[
        ipa_municipal_entities["seat_istat_code"].eq(municipality["istat_code"])
    ].copy()

    if candidates.empty and municipality.get("cadastral_code", ""):
        candidates = ipa_municipal_entities[
            ipa_municipal_entities["seat_cadastral_code"].eq(municipality["cadastral_code"])
        ].copy()

    return candidates


def _score_candidates(candidates: pd.DataFrame, aliases: set[str]) -> pd.DataFrame:
    candidates = candidates.copy()
    candidates["name_exact"] = candidates["ipa_name_normalised"].isin(aliases)
    candidates["name_contains"] = candidates["ipa_name_normalised"].map(
        lambda candidate: any(
            alias and (alias in candidate or candidate in alias) for alias in aliases
        )
    )
    return candidates


def link_ipa(
    istat: pd.DataFrame,
    ipa: pd.DataFrame,
    *,
    curated_aliases: dict[str, list[str]] | None = None,
) -> pd.DataFrame:
    """
    Deterministically link current ISTAT municipalities to IPA entities.

    The linker uses current ISTAT/cadastral location, official multilingual names,
    and narrowly curated aliases. If location metadata is missing in IPA, a unique
    exact official-name match across category L6 is accepted. No fuzzy matching is
    used.
    """
    municipal_entities = ipa[ipa["ipa_category"].eq(MUNICIPALITY_IPA_CATEGORY)].copy()
    rows: list[dict[str, object]] = []

    for _, municipality in istat.iterrows():
        aliases = _official_aliases(municipality, curated_aliases)
        candidates = _score_candidates(
            _location_candidates(municipality, municipal_entities),
            aliases,
        )
        selected = None
        status = "unmatched"
        basis = ""

        if not candidates.empty:
            exact = candidates[candidates["name_exact"]]
            contains = candidates[
                candidates["name_contains"] & candidates["looks_like_municipality"]
            ]

            if len(exact) == 1:
                selected = exact.iloc[0]
                status = "matched_exact"
                basis = "location+official_name"
            elif len(contains) == 1:
                selected = contains.iloc[0]
                status = "matched_contains"
                basis = "location+official_name_contains"
            elif len(candidates) == 1 and bool(
                candidates.iloc[0]["looks_like_municipality"]
            ):
                selected = candidates.iloc[0]
                status = "matched_unique_location"
                basis = "unique_location"
            else:
                status = "ambiguous"
                basis = "multiple_location_candidates"
        else:
            global_exact = municipal_entities[
                municipal_entities["ipa_name_normalised"].isin(aliases)
            ]
            if len(global_exact) == 1:
                candidates = global_exact.copy()
                selected = global_exact.iloc[0]
                status = "matched_global_exact"
                basis = "unique_official_name_global"

        row = municipality.drop(labels=["name_normalised"], errors="ignore").to_dict()
        row["ipa_match_status"] = status
        row["ipa_match_basis"] = basis
        row["ipa_candidate_count"] = len(candidates)

        for field in [
            "ipa_code",
            "ipa_name",
            "fiscal_code",
            "institutional_url",
            "updated_at_ipa",
        ]:
            row[field] = "" if selected is None else selected[field]

        rows.append(row)

    return pd.DataFrame(rows)


def validate_registry(registry: pd.DataFrame) -> dict[str, int]:
    total = len(registry)
    matched = int(registry["ipa_code"].ne("").sum())
    ambiguous = int(registry["ipa_match_status"].eq("ambiguous").sum())
    unmatched = int(registry["ipa_match_status"].eq("unmatched").sum())

    if registry["istat_code"].duplicated().any():
        raise ValueError("Processed registry contains duplicate ISTAT codes")
    if registry["municipality_version_id"].duplicated().any():
        raise ValueError("Processed registry contains duplicate municipality version ids")

    return {
        "municipalities": total,
        "ipa_matched": matched,
        "ipa_ambiguous": ambiguous,
        "ipa_unmatched": unmatched,
    }
