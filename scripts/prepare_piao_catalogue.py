"""Pin catalogue pagination metadata once for all shards in a workflow run."""
from datetime import UTC, datetime
import json
from pathlib import Path

from segnali_locali_di_trasparenza.piao import fetch_catalogue_page


if __name__ == "__main__":
    records, total, page_size = fetch_catalogue_page(0)
    if page_size <= 0 or total <= 0 or len(records) != min(total, page_size):
        raise RuntimeError("Invalid initial catalogue pagination metadata")
    path = Path("data/manifests/piao_catalogue_baseline.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "retrieved_at": datetime.now(UTC).isoformat(),
        "total": total, "page_size": page_size,
    }, indent=2) + "\n", encoding="utf-8")
