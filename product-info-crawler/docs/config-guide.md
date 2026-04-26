# 브랜드 설정 파일 가이드

`config/{brand_id}.json` 전체 키 설명.

```jsonc
{
  "brand": {
    "id": "lv",               // scrapers/{id}_scraper.py 파일명과 일치
    "display_name": "Louis Vuitton",
    "scraper": "lv"           // registry.py가 이 값으로 클래스를 자동 탐색
  },
  "google_sheets": {
    "service_account_file": "credentials/service_account.json",
    "spreadsheet_name": "루이비통 상품 리스트"  // Sheets 파일명과 정확히 일치
  },
  "scraping_settings": {
    "headless": false,                   // true는 봇 탐지 확률 급증 — 웬만하면 false
    "scroll_pause_time": 3.0,            // 스크롤 후 대기(초)
    "max_products_per_category": 1000,   // 0이면 무제한
    "max_scroll_loops": 30,
    "max_placeholder_retries": 3,        // 스켈레톤 로딩 대기 재시도 횟수
    "initial_wait_sec": 20,              // 첫 페이지 로딩 대기
    "inter_category_delay_sec": 5,       // 카테고리 간 대기 (실제는 ×0.8~1.5 랜덤)
    "fetch_detail": false,               // true면 상품 상세 페이지도 방문
    "detail_page_delay_sec": 5,          // 상세 페이지 간 대기
    "detail_checkpoint_interval": 5,    // N개마다 중간 저장
    "download_images": false,            // true면 이미지 로컬 다운로드 (느리고 용량 큼)
    "popup_selectors": [...],            // 팝업 닫기 버튼 CSS 셀렉터 목록
    "popup_xpaths": [...]                // 팝업 닫기 버튼 XPath 목록
  },
  "selectors": {
    "product_card": "li.lv-product-card",  // (필수) 상품 카드 최상위 요소
    "lazy_placeholder": ".lv-skeleton",    // 로딩 중 플레이스홀더 (없으면 빈 문자열)
    "name": ".lv-product-card__name",      // (필수)
    "price": ".lv-product-card__price",    // (필수)
    "link": "a.lv-product-card__url"       // (필수)
  },
  "detail_selectors": {
    // fetch_detail: true일 때 __NEXT_DATA__ 파싱 실패 시 CSS 폴백으로 사용
    "description": ".lv-product-description__text",
    "sizes": ".lv-size-picker__option",
    "images": ".lv-product-media__image img[src]"
  },
  "categories": {
    "카테고리명": "https://..."  // 중복 키는 나중 값이 앞 값을 덮어씀 (주의)
  }
}
```

## 주의 사항

- `categories` 키 중복 시 JSON 표준에 따라 나중 값이 앞 값을 덮어씀 — LV config에 `Bag(Woman)` 중복 존재, 정리 필요
- `inter_category_delay_sec`는 최소 5 권장 (LV, Dior는 특히 엄격)
- `download_images: true`는 필요한 경우에만 — 느리고 디스크 사용량 큼
