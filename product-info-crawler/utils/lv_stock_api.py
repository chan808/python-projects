# Selenium execute_async_script에 전달하는 JS — 브라우저 쿠키(_abck 등)가 자동 포함되어 Akamai 통과
# execute_async_script(script, sku) 호출 시 Selenium은 arguments = [sku, callback] 순으로 주입한다.
# 반드시 arguments[0] = sku, arguments[arguments.length-1] = Selenium 콜백(resolve) 순서여야 한다.
_FETCH_SCRIPT = """
const sku = arguments[0];
const resolve = arguments[arguments.length - 1];
fetch('https://api.louisvuitton.com/eco-eu/search-merch-eapi/v1/kor-kr/stores/query', {
    method: 'POST',
    headers: {
        'client_id': '607e3016889f431fb8020693311016c9',
        'client_secret': '60bbcdcD722D411B88cBb72C8246a22F',
        'content-type': 'application/json',
        'accept': 'application/json'
    },
    body: JSON.stringify({
        flagShip: false,
        country: 'KR',
        query: '',
        clickAndCollect: false,
        skuId: sku,
        pageType: 'productsheet'
    })
})
.then(r => r.json())
.then(data => resolve({ok: true, data}))
.catch(e => resolve({ok: false, error: e.toString()}));
"""


def _parse_available_stores(hits: list) -> list[str]:
    stores = []
    for hit in hits:
        props = {p["name"]: p["value"] for p in hit.get("additionalProperty", [])}
        if props.get("stockAvailability") == "true":
            name = hit.get("name", "")
            if name:
                stores.append(name)
    return stores


def fetch_stores_with_stock_via_driver(driver, sku: str) -> list[str]:
    """
    Selenium 브라우저 컨텍스트에서 fetch를 실행해 재고 보유 한국 매장을 조회합니다.
    브라우저 쿠키(_abck 등)가 자동 포함되므로 Akamai 차단을 우회합니다.
    호출 전에 driver가 LV 도메인 페이지(kr 또는 en)에 있어야 합니다.

    반환: 재고 보유 매장명 리스트 (재고 없음 = 빈 리스트, API 오류 = RuntimeError)
    """
    result = driver.execute_async_script(_FETCH_SCRIPT, sku)
    if not result.get("ok"):
        raise RuntimeError(f"API 호출 실패: {result.get('error')}")

    data = result.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"응답 형식 오류 (dict 아님): {type(data)}")

    hits = data.get("hits")
    if hits is None:
        keys = list(data.keys())
        raise RuntimeError(f"응답에 hits 키 없음. 실제 키: {keys}")

    return _parse_available_stores(hits)
