# 새 브랜드 추가 방법

## 1. 설정 파일 생성

`config/{brand_id}.json` 작성. 자세한 키 설명은 [config-guide.md](config-guide.md) 참고.

`brand.id`와 `brand.scraper` 값이 파일명과 일치해야 한다.

```json
{
  "brand": { "id": "gucci", "display_name": "Gucci", "scraper": "gucci" },
  ...
}
```

## 2. 스크래퍼 클래스 생성

`scrapers/{brand_id}_scraper.py` 생성 후 `BaseScraper` 상속.
`registry.py`가 파일명 규칙으로 자동 탐색하므로 별도 등록 불필요.

```python
from scrapers.base_scraper import BaseScraper

class GucciScraper(BaseScraper):
    BASE_URL = "https://www.gucci.com"

    def extract_products_from_html(self, html: str, category_name: str, category_url: str) -> list[dict]:
        # 반드시 구현. 반환 형식:
        # [{"category": ..., "name": ..., "price": ..., "url": ..., "reference": ..., "colors": ...}, ...]
        ...
```

네이밍 규칙: `{brand_id}_scraper.py` → `{BrandId}Scraper` (스네이크케이스를 파스칼케이스로 변환)

## 3. 셀렉터/구조 파악 방법

1. 브라우저 DevTools → Network 탭 → 페이지 HTML 소스에서 `__NEXT_DATA__` 스크립트 확인
2. JSON 구조를 파악해 `_parse_detail_from_next_data()` 오버라이드
3. `__NEXT_DATA__`가 없으면 `JSON-LD` 또는 CSS 셀렉터 방식으로

## 오버라이드 포인트

| 메서드 | 오버라이드 시점 |
|---|---|
| `extract_products_from_html()` | 필수. 카테고리 목록 파싱 |
| `_parse_detail_from_next_data()` | `__NEXT_DATA__` 구조가 브랜드마다 다를 때. Vue/Nuxt 앱이면 `return {}` |
| `_fill_from_selectors()` | CSS 셀렉터로 상세 필드 추출 로직이 브랜드별로 다를 때 |
| `_wait_for_detail_content()` | 상세 페이지 SPA 렌더링 완료 시점 감지가 필요할 때 (기본: `pass`) |
| `_before_navigate()` | 페이지 이동 전 추가 대기/처리 필요 시 |
| `_detail_wait_range()` | 상세 페이지 로딩 대기 시간 조정 |
| `parse_detail()` | 상세 수집 후 외부 API 추가 호출 필요 시 (예: LV 재고 API) |
| `parse_category()` | 페이지네이션 방식 등 플로우 자체가 다를 때 |
