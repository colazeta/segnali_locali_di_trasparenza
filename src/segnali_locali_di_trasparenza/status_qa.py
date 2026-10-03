"""Protect downstream products against incomplete or ambiguous status tables."""
import pandas as pd


def validate_status_coverage(registry: pd.DataFrame, status: pd.DataFrame) -> None:
    for name, frame in (("registry", registry), ("status", status)):
        if "istat_code" not in frame:
            raise ValueError(f"{name} is missing ISTAT identity")
        codes = frame["istat_code"]
        if codes.isna().any() or codes.eq("").any() or codes.duplicated().any():
            raise ValueError(f"{name} has missing or duplicate ISTAT identities")
    expected, observed = set(registry["istat_code"]), set(status["istat_code"])
    if expected != observed:
        raise ValueError(
            f"Status coverage mismatch: missing={len(expected - observed)}, "
            f"unexpected={len(observed - expected)}"
        )
    if "lookup_status" not in status:
        raise ValueError("Status is missing lookup_status")
    if not status["lookup_status"].isin(["found", "not_observed", "error"]).all():
        raise ValueError("Status contains missing or unrecognised lookup states")
