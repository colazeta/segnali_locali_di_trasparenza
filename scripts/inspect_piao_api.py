from __future__ import annotations

import json

import requests


def main() -> None:
    for ipa in ('c_l719','c_m208','c_h501'):
        url=f'https://piao.dfp.gov.it/api/piao?ipaCode={ipa}&page=0'
        r=requests.get(url,timeout=20,headers={'Accept':'application/json'})
        print('API',ipa,r.status_code,r.url)
        try:
            data=r.json()
        except Exception:
            print(r.text[:5000])
            continue
        print(json.dumps(data,ensure_ascii=False,indent=2)[:30000])


if __name__ == '__main__':
    main()
