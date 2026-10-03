from copy import deepcopy

import pandas as pd
import pytest

from segnali_locali_di_trasparenza.catalogue_qa import require_accepted, validate_catalogue


def fixture():
    registry = pd.DataFrame([{"istat_code": "001001", "name": "None", "ipa_code": "c_b9"}])
    index = pd.DataFrame([
        {"page": "0", "position": "0", "record_fingerprint": "a",
         "piao_publication_id": "a", "ipa_code": "c_b9"},
        {"page": "0", "position": "1", "record_fingerprint": "b",
         "piao_publication_id": "b", "ipa_code": "c_b900"},
        {"page": "1", "position": "0", "record_fingerprint": "c",
         "piao_publication_id": "c", "ipa_code": "other"},
    ])
    publications = pd.DataFrame([
        {"istat_code": "001001", "ipa_code": "c_b9", "piao_publication_id": "a"}
    ])
    manifests = [{"shard_index": 0, "shard_count": 1, "advertised_total_at_start": 3,
                  "page_size_at_start": 2, "total_pages": 2, "pages_completed": [0, 1],
                  "observed_totals": [3], "observed_page_sizes": [1, 2]}]
    return registry, index, publications, manifests


def test_complete_catalogue_and_short_final_page():
    report = validate_catalogue(*fixture(), expected_shards=1)
    require_accepted(report)


@pytest.mark.parametrize("problem", ["missing_page", "duplicate_page", "positions",
                                     "duplicate_id", "prefix_join", "missing_projection",
                                     "total_drift", "registry_ipa", "source_ipa"])
def test_inconsistent_catalogue_is_rejected(problem):
    registry, index, pubs, manifests = deepcopy(fixture())
    if problem == "missing_page":
        index = index.iloc[:2]
    elif problem == "duplicate_page":
        index.loc[2, ["page", "position", "record_fingerprint"]] = ["0", "0", "a"]
    elif problem == "positions":
        index.loc[1, "position"] = "2"
    elif problem == "duplicate_id":
        index.loc[2, "piao_publication_id"] = "a"
    elif problem == "prefix_join":
        pubs.loc[0, "ipa_code"] = "c_b900"
    elif problem == "missing_projection":
        pubs = pubs.iloc[:0]
    elif problem == "total_drift":
        manifests[0]["observed_totals"] = [3, 4]
    elif problem == "registry_ipa":
        registry = pd.concat([registry, registry], ignore_index=True)
    elif problem == "source_ipa":
        index.loc[0, "ipa_code"] = "other"
    report = validate_catalogue(registry, index, pubs, manifests, expected_shards=1)
    with pytest.raises(RuntimeError, match="Catalogue validation failed"):
        require_accepted(report)
