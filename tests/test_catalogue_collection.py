"""Regression checks for the production shard CLI."""
import importlib.util
import json
from pathlib import Path
import sys

import pandas as pd
import pytest


def collector():
    path = Path(__file__).parents[1] / "scripts" / "collect_piao_catalogue_shard.py"
    spec = importlib.util.spec_from_file_location("shard_collector", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("drift", ["between_shards", "within_shard", "page_length"])
def test_shard_rejects_drift_without_a_success_manifest(tmp_path, monkeypatch, drift):
    module = collector()
    registry = tmp_path / "registry.csv"
    pd.DataFrame([{"istat_code": "001001", "name": "None", "ipa_code": "c_a1"}]).to_csv(
        registry, index=False)
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"total": 3, "page_size": 2}))
    output = tmp_path / "shard"
    monkeypatch.setattr(sys, "argv", ["collect", "--registry", str(registry),
        "--output-dir", str(output), "--shard-index", "0", "--shard-count", "1",
        "--catalogue-baseline", str(baseline), "--delay", "0"])
    record = {"administrationIpaCode": "other", "years": "Anno 2026-2028",
              "content": {}, "version": 1}

    def fetch(page, **kwargs):
        if page == 0:
            return [record, {**record, "version": 2}], 4 if drift == "between_shards" else 3, 2
        return ([] if drift == "page_length" else [record]), (
            4 if drift == "within_shard" else 3), 1

    monkeypatch.setattr(module, "fetch_catalogue_page", fetch)
    with pytest.raises(RuntimeError, match="snapshot rejected"):
        module.main()
    assert not (output / "manifest-00.json").exists()
