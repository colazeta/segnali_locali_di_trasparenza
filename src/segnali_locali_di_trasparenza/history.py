"""Cumulative observation history, distinct from official publication dates."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
from typing import Any


def _time(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("Observation timestamps must include a timezone")
    return result


def update_history(
    publications: list[dict[str, Any]], manifest: dict[str, Any], *,
    snapshot_id: str, previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one accepted, non-overlapping snapshot without deleting observations."""
    start, finish = manifest["collection_started_at"], manifest["collection_finished_at"]
    if _time(start) > _time(finish):
        raise ValueError("Invalid collection interval")
    history = deepcopy(previous) if previous is not None else {
        "schema_version": 1, "snapshots": [], "publications": {}, "events": []
    }
    if history["schema_version"] != 1:
        raise ValueError("Unsupported history schema")
    snapshots = history["snapshots"]
    if any(s["snapshot_id"] == snapshot_id for s in snapshots):
        raise ValueError("Snapshot has already been recorded")
    if snapshots and _time(snapshots[-1]["collection_finished_at"]) >= _time(start):
        raise ValueError("Snapshots must be ordered and non-overlapping")
    ids = [p["piao_publication_id"] for p in publications]
    if any(not i for i in ids) or len(ids) != len(set(ids)):
        raise ValueError("Publication identifiers must be unique and non-empty")
    current_ids = set(ids)
    records = history["publications"]
    lower_bound = snapshots[-1]["collection_started_at"] if snapshots else None

    def event(kind: str, publication: dict[str, Any]) -> None:
        history["events"].append({
            "snapshot_id": snapshot_id, "event": kind,
            "piao_publication_id": publication["piao_publication_id"],
            "istat_code": publication["istat_code"],
            "reference_start_year": publication["reference_start_year"],
        })

    for pub in publications:
        observed = pub["retrieved_at"]
        if not (_time(start) <= _time(observed) <= _time(finish)):
            raise ValueError("Publication observation is outside collection interval")
        stable = {k: v for k, v in pub.items() if k != "retrieved_at"}
        fingerprint = hashlib.sha256(json.dumps(
            stable, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()).hexdigest()
        identity = pub["piao_publication_id"]
        old = records.get(identity)
        if old is None:
            entry = {
                "first_observed_at": observed,
                "first_observed_snapshot": snapshot_id,
                "first_observed_after": lower_bound,
                "observation_count": 0,
            }
            event("baseline_observation" if not snapshots else "newly_observed", pub)
        else:
            entry = old
            if not old["returned_in_latest_snapshot"]:
                event("returned_again", pub)
            if old["metadata_sha256"] != fingerprint:
                event("metadata_changed", pub)
        entry.update({
            "last_observed_at": observed, "last_observed_snapshot": snapshot_id,
            "returned_in_latest_snapshot": True, "metadata_sha256": fingerprint,
            "last_metadata": stable, "observation_count": entry["observation_count"] + 1,
        })
        records[identity] = entry
    for identity, old in records.items():
        if identity not in current_ids and old["returned_in_latest_snapshot"]:
            event("no_longer_returned", old["last_metadata"])
            old["returned_in_latest_snapshot"] = False
    snapshots.append({
        "snapshot_id": snapshot_id, "collection_started_at": start,
        "collection_finished_at": finish,
        "publications_csv_sha256": manifest["outputs"]["publications_csv_sha256"],
        "target_start_year": manifest["target_start_year"],
    })
    return history
