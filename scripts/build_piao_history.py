"""Extend history from hash-verified accepted snapshot publications."""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from segnali_locali_di_trasparenza.history import update_history


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-dir", required=True)
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--previous-history")
    parser.add_argument("--previous-manifest")
    args = parser.parse_args()
    directory = Path(args.snapshot_dir)
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    qa = json.loads((directory / "catalogue_qa.json").read_text())
    if qa.get("accepted") is not True:
        raise ValueError("History requires an accepted snapshot")
    pubs_path = directory / "piao_publications.csv"
    if digest(pubs_path) != manifest["outputs"]["publications_csv_sha256"]:
        raise ValueError("Publication checksum mismatch")
    if bool(args.previous_history) != bool(args.previous_manifest):
        raise ValueError("Previous history and manifest must be supplied together")
    previous = None
    if args.previous_history:
        previous_path = Path(args.previous_history)
        previous_manifest = json.loads(Path(args.previous_manifest).read_text())
        if digest(previous_path) != previous_manifest["outputs"]["history_json_sha256"]:
            raise ValueError("Previous history checksum mismatch")
        previous = json.loads(previous_path.read_text())
    pubs = pd.read_csv(pubs_path, dtype=str, keep_default_na=False).to_dict("records")
    history = update_history(pubs, manifest, snapshot_id=args.snapshot_id, previous=previous)
    output = directory / "piao_history.json"
    output.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n")
    manifest["outputs"]["history_json_sha256"] = digest(output)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
