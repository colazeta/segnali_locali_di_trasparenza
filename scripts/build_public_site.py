from __future__ import annotations

import argparse
import json
from pathlib import Path

from segnali_locali_di_trasparenza.public_site import build_site


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True)
    parser.add_argument("--status", required=True)
    parser.add_argument("--publications", required=True)
    parser.add_argument("--assets-dir", default="site/assets")
    parser.add_argument("--output-dir", default="_site")
    parser.add_argument("--base-path", default="")
    args = parser.parse_args()

    summary = build_site(
        registry_path=Path(args.registry),
        status_path=Path(args.status),
        publications_path=Path(args.publications),
        assets_dir=Path(args.assets_dir),
        output_dir=Path(args.output_dir),
        base_path=args.base_path,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
