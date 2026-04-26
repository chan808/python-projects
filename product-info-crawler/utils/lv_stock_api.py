import time
import uuid

import requests


_API_URL = "https://api.louisvuitton.com/eco-eu/search-merch-eapi/v1/fra-fr/stores/query"
_CLIENT_ID = "607e3016889f431fb8020693311016c9"
_CLIENT_SECRET = "60bbcdcD722D411B88cBb72C8246a22F"

# 한국 영토 범위 — 경도 130° 상한으로 일본 매장(후쿠오카 등) 제외
_KOREA_BOUNDS = {
    "latitudeA": "33.10",
    "latitudeB": "38.70",
    "latitudeCenter": "36.00",
    "longitudeA": "125.00",
    "longitudeB": "130.00",
    "longitudeCenter": "127.50",
}

# Selenium execute_async_script에 전달하는 JS — 브라우저 쿠키가 자동 포함되어 Akamai 통과
_FETCH_SCRIPT = """
const [resolve, sku] = arguments;
fetch('https://api.louisvuitton.com/eco-eu/search-merch-eapi/v1/fra-fr/stores/query', {
    method: 'POST',
    headers: {
        'client_id': '607e3016889f431fb8020693311016c9',
        'client_secret': '60bbcdcD722D411B88cBb72C8246a22F',
        'content-type': 'application/json',
        'accept': 'application/json'
    },
    body: JSON.stringify({
        flagShip: false, country: '', clickAndCollect: false,
        pageType: 'productsheet', query: 'korea', skuId: sku,
        latitudeA: '33.10', latitudeB: '38.70', latitudeCenter: '36.00',
        longitudeA: '125.00', longitudeB: '130.00', longitudeCenter: '127.50'
    })
}).then(r => r.json())
  .then(data => resolve({ok: true, data}))
  .catch(e => resolve({ok: false, error: e.toString()}));
"""


def _parse_korean_stores(hits: list) -> list[str]:
    stores = []
    for hit in hits:
        country = hit.get("address", {}).get("addressCountry", "")
        if "Cor" not in country:  # "Corée" (프랑스어 대한민국) 필터
            continue
        props = {p["name"]: p["value"] for p in hit.get("additionalProperty", [])}
        if props.get("stockAvailability") == "true":
            stores.append(hit["name"])
    return stores


def fetch_stores_with_stock_via_driver(driver, sku: str) -> list[str]:
    """
    Selenium 브라우저 컨텍스트에서 fetch를 실행해 재고 보유 한국 매장을 조회합니다.
    브라우저 쿠키(_abck 등)가 자동 포함되므로 Akamai 차단을 우회합니다.
    호출 전에 driver가 LV 도메인 페이지에 있어야 합니다.
    """
    result = driver.execute_async_script(_FETCH_SCRIPT, sku)
    if not result.get("ok"):
        raise RuntimeError(f"API 호출 실패: {result.get('error')}")
    return _parse_korean_stores(result["data"].get("hits", []))
