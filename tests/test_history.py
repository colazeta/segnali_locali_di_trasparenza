from copy import deepcopy

import pytest

from segnali_locali_di_trasparenza.history import update_history


def snapshot(day, pubs, previous=None):
    start = f"2026-09-{day:02d}T10:00:00+00:00"
    finish = f"2026-09-{day:02d}T12:00:00+00:00"
    rows = [{"piao_publication_id": p, "istat_code": "001001",
             "reference_start_year": "2026", "version": "1",
             "retrieved_at": f"2026-09-{day:02d}T11:00:00+00:00"} for p in pubs]
    manifest = {"collection_started_at": start, "collection_finished_at": finish,
                "target_start_year": 2026, "outputs": {"publications_csv_sha256": str(day)}}
    return update_history(rows, manifest, snapshot_id=str(day), previous=previous)


def test_history_preserves_first_last_absence_and_return():
    first = snapshot(20, ["a"])
    saved = deepcopy(first)
    second = snapshot(27, ["a", "b"], first)
    assert first == saved
    assert second["publications"]["a"]["first_observed_at"] == "2026-09-20T11:00:00+00:00"
    assert second["publications"]["a"]["last_observed_at"] == "2026-09-27T11:00:00+00:00"
    assert second["publications"]["b"]["first_observed_after"] == "2026-09-20T10:00:00+00:00"
    third = snapshot(28, ["b"], second)
    assert not third["publications"]["a"]["returned_in_latest_snapshot"]
    assert third["publications"]["a"]["last_observed_at"] == second["publications"]["a"]["last_observed_at"]
    fourth = snapshot(29, ["a", "b"], third)
    assert fourth["publications"]["a"]["observation_count"] == 3
    assert [e["event"] for e in fourth["events"]] == [
        "baseline_observation", "newly_observed", "no_longer_returned", "returned_again"]


def test_out_of_order_or_duplicate_snapshot_rejected():
    first = snapshot(20, ["a"])
    with pytest.raises(ValueError, match="already"):
        snapshot(20, ["a"], first)
    with pytest.raises(ValueError, match="ordered"):
        snapshot(19, ["a"], first)


def test_version_change_is_new_identity_and_old_record_is_retained():
    first = snapshot(20, ["version1"])
    second = snapshot(27, ["version2"], first)
    assert set(second["publications"]) == {"version1", "version2"}
    assert second["events"][-2]["event"] == "newly_observed"
    assert second["events"][-1]["event"] == "no_longer_returned"


def test_metadata_change_does_not_reset_first_observation():
    first = snapshot(20, ["a"])
    changed = deepcopy(first)
    changed["publications"]["a"]["metadata_sha256"] = "old-metadata"
    second = snapshot(27, ["a"], changed)
    assert second["events"][-1]["event"] == "metadata_changed"
    assert second["publications"]["a"]["first_observed_at"] == first["publications"]["a"]["first_observed_at"]


def test_history_cli_verifies_current_and_previous_checksums(tmp_path, monkeypatch):
    import hashlib
    import importlib.util
    import json
    from pathlib import Path
    import sys
    import pandas as pd

    path = Path(__file__).parents[1] / "scripts" / "build_piao_history.py"
    spec = importlib.util.spec_from_file_location("history_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    pubs = tmp_path / "piao_publications.csv"
    pd.DataFrame([{"piao_publication_id": "a", "istat_code": "001001",
        "reference_start_year": "2026", "retrieved_at": "2026-09-20T11:00:00+00:00"}]).to_csv(pubs, index=False)
    manifest = {"collection_started_at": "2026-09-20T10:00:00+00:00",
                "collection_finished_at": "2026-09-20T12:00:00+00:00",
                "target_start_year": 2026, "outputs": {
                    "publications_csv_sha256": hashlib.sha256(pubs.read_bytes()).hexdigest()}}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "catalogue_qa.json").write_text(json.dumps({"accepted": True}))
    argv = ["history", "--snapshot-dir", str(tmp_path), "--snapshot-id", "20"]
    monkeypatch.setattr(sys, "argv", argv)
    module.main()
    assert (tmp_path / "piao_history.json").exists()
    history_manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert "history_json_sha256" in history_manifest["outputs"]
    monkeypatch.setattr(sys, "argv", argv + ["--previous-history", str(tmp_path / "piao_history.json"),
        "--previous-manifest", str(tmp_path / "manifest.json")])
    (tmp_path / "piao_history.json").write_text('{}')
    with pytest.raises(ValueError, match="Previous history checksum"):
        module.main()
    monkeypatch.setattr(sys, "argv", argv)
    pubs.write_text(pubs.read_text() + '\n')
    with pytest.raises(ValueError, match="Publication checksum"):
        module.main()
