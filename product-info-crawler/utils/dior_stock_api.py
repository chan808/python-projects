import requests

_ENDPOINT = "https://api-fashion.dior.com/graph?GetBoutiqueStocks"
_HEADERS = {
    "content-type": "application/json",
    "accept": "*/*",
    "x-dior-locale": "ko_kr",
    "x-dior-universe": "couture",
    "x-checkout-authentication-type": "SLAS",
    "apollographql-client-name": "Newlook Couture Catalog V2 K8S",
    "apollographql-client-version": "5.418.0-git25ffc045.hotfix",
    "origin": "https://www.dior.com",
    "referer": "https://www.dior.com/",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/148.0.0.0 Safari/537.36"
    ),
}
_QUERY = (
    "query GetBoutiqueStocks($id: String!) "
    "{ product: getProduct(id: $id) "
    "{ variations { sku boutiqueStocks { status boutique { name } } } } }"
)


def _parse_stores(data: dict) -> list[str]:
    variations = (data.get("data") or {}).get("product", {}).get("variations") or []
    stores = []
    for v in variations:
        for bs in v.get("boutiqueStocks") or []:
            name = (bs.get("boutique") or {}).get("name", "")
            if bs.get("status") and name and name not in stores:
                stores.append(name)
    return stores


def fetch_stores_with_stock_via_driver(driver, code: str) -> list[str]:
    """
    Dior GraphQL API로 재고 보유 매장을 조회합니다. (driver는 사용하지 않음)
    code: 레퍼런스 컬럼 값 (예: "2LLBH095MAR_H00N")

    반환: 재고 보유 매장명 리스트 (재고 없음 = 빈 리스트, API 오류 = RuntimeError)
    """
    body = {
        "operationName": "GetBoutiqueStocks",
        "variables": {"id": code},
        "query": _QUERY,
    }
    try:
        resp = requests.post(_ENDPOINT, headers=_HEADERS, json=body, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"API 요청 실패: {exc}") from exc

    try:
        data = resp.json()
    except ValueError as exc:
        raise RuntimeError(f"응답 파싱 실패: {exc}") from exc

    return _parse_stores(data)
