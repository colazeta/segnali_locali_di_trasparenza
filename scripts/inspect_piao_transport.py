from __future__ import annotations

import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def main() -> None:
    url = "https://piao.dfp.gov.it/piao?field_administration_ipa_value=c_l719&name="
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for script in soup.find_all("script", src=True):
        src = str(script.get("src", ""))
        if not src.startswith("/"):
            continue
        js_url = urljoin(response.url, src)
        js = requests.get(js_url, timeout=20).text
        print("BUNDLE", js_url, len(js))
        lowered = js.lower()
        for token in ("views/ajax", "field_administration_ipa_value", "view_name", "drupalsettings", "ajax"):
            start = 0
            while True:
                index = lowered.find(token, start)
                if index < 0:
                    break
                excerpt = re.sub(r"\\s+", " ", js[max(0, index - 220): index + 420])
                print("HIT", token, excerpt)
                start = index + len(token)


if __name__ == "__main__":
    main()
