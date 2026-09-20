from __future__ import annotations

import json

import requests


URL = "https://piao.dfp.gov.it/api/piao"
PROBES = [
    {"page": 0},
    {"page": 0, "limit": 60},
    {"page": 0, "pageSize": 60},
    {"page": 0, "perPage": 60},
    {"page": 0, "itemsPerPage": 60},
]


def main() -> None:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "segnali-locali-di-trasparenza/0.1 "
                "(+https://github.com/colazeta/segnali_locali_di_trasparenza)"
            ),
            "Accept": "application/json",
        }
    )
    for params in PROBES:
        response = session.get(URL, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        container = payload["result"][0]
        print(
            json.dumps(
                {
                    "params": params,
                    "url": response.url,
                    "success": payload.get("success"),
                    "list_length": len(container.get("list") or []),
                    "count": container.get("count"),
                    "total": container.get("total"),
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
