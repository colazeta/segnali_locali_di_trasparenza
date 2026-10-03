import pandas as pd
import pytest

from segnali_locali_di_trasparenza.status_qa import validate_status_coverage
from segnali_locali_di_trasparenza.public_site import classify_status


def test_missing_status_is_not_absence():
    registry = pd.DataFrame([{"istat_code": "001168", "name": "None"}])
    status = pd.DataFrame(columns=["istat_code", "lookup_status"])
    with pytest.raises(ValueError, match="missing=1"):
        validate_status_coverage(registry, status)


@pytest.mark.parametrize("states", [[""], [None], ["pending"], ["found", "found"]])
def test_invalid_and_duplicate_status_rejected(states):
    registry = pd.DataFrame([{"istat_code": "001168"}])
    status = pd.DataFrame([{"istat_code": "001168", "lookup_status": s} for s in states])
    with pytest.raises(ValueError):
        validate_status_coverage(registry, status)


def test_error_remains_error_and_prior_cycle_does_not_satisfy_target():
    registry = pd.DataFrame([{"istat_code": "001168", "name": "None"}])
    status = pd.DataFrame([{"istat_code": "001168", "lookup_status": "error"}])
    validate_status_coverage(registry, status)
    assert classify_status(pd.Series({"lookup_status": "error"})) == "lookup_error"
    assert classify_status(pd.Series({"lookup_status": "found", "piao_present_on_portal": "True",
        "period_starting_target_year_present": "False", "latest_reference_period": "2025-2027"})) == "prior_period_only"
    assert registry.iloc[0]["name"] == "None"
