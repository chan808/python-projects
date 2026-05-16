import requests

_BASE_ENDPOINT = "https://api-fashion.dior.com/graph"
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

_BOUTIQUE_QUERY = (
    "query GetBoutiqueStocks($id: String!) "
    "{ product: getProduct(id: $id) "
    "{ variations { sku boutiqueStocks { status boutique { name } } } } }"
)

_DETAIL_QUERY = (
    "query GetProductDetail($id: String!) "
    "{ product: getProduct(id: $id) "
    "{ subtitle description sizeAndFit characteristics "
    "variations { sizeLabel title boutiqueStocks { status boutique { name } } } } }"
)


def _post(operation_name: str, variables: dict, query: str) -> dict:
    body = {"operationName": operation_name, "variables": variables, "query": query}
    try:
        resp = requests.post(
            f"{_BASE_ENDPOINT}?{operation_name}",
            headers=_HEADERS,
            json=body,
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"API 요청 실패: {exc}") from exc
    try:
        return resp.json()
    except ValueError as exc:
        raise RuntimeError(f"응답 파싱 실패: {exc}") from exc


def _parse_stores_from_variations(variations: list) -> list[str]:
    stores = []
    for v in variations:
        for bs in (v.get("boutiqueStocks") or []):
            name = (bs.get("boutique") or {}).get("name", "")
            if bs.get("status") and name and name not in stores:
                stores.append(name)
    return stores


def fetch_stores_with_stock_via_driver(driver, code: str) -> list[str]:
    """
    Dior GraphQL API로 재고 보유 매장을 조회합니다. (driver는 사용하지 않음)
    code: 레퍼런스 컬럼 값 (예: "2LLBH095MAR_H00N")
    """
    data = _post("GetBoutiqueStocks", {"id": code}, _BOUTIQUE_QUERY)
    variations = (data.get("data") or {}).get("product", {}).get("variations") or []
    return _parse_stores_from_variations(variations)


def fetch_product_detail(code: str) -> dict:
    """
    Dior GraphQL API 한 번으로 상품 상세 정보와 재고 매장을 모두 조회합니다.
    반환: { description, sizes, material, colors, store_inventory }
    브라우저 방문 없이 ~1초 내에 완료됩니다.
    """
    data = _post("GetProductDetail", {"id": code}, _DETAIL_QUERY)
    product = (data.get("data") or {}).get("product") or {}
    if not product:
        raise RuntimeError("상품 데이터 없음")

    variations = product.get("variations") or []

    # sizes: 원사이즈(U/TU) 제외한 sizeLabel → 없으면 sizeAndFit 첫 줄 치수
    size_labels = [
        lbl for v in variations
        if (lbl := (v.get("sizeLabel") or v.get("title") or "")) not in ("", "U", "TU")
    ]
    if size_labels:
        sizes = ", ".join(dict.fromkeys(size_labels))
    else:
        size_and_fit = (product.get("sizeAndFit") or "").strip()
        first_line = size_and_fit.split("\r\n")[0].split("\n")[0].strip()
        if first_line.startswith("크기:"):
            first_line = first_line.removeprefix("크기:").strip()
        if "cm" in first_line:
            first_line = first_line[:first_line.index("cm") + 2].strip()
        sizes = first_line

    # material: characteristics에서 "주요 소재:" 파싱
    material = ""
    for item in (product.get("characteristics") or []):
        if isinstance(item, str) and item.startswith("주요 소재:"):
            material = item.removeprefix("주요 소재:").strip()
            break

    return {
        "description": product.get("description") or "",
        "sizes": sizes,
        "material": material,
        "colors": product.get("subtitle") or "",
        "store_inventory": ", ".join(_parse_stores_from_variations(variations)),
    }
