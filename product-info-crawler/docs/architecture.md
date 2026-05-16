# 아키텍처 및 폴더 구조

## 기술 스택

| 분류 | 기술 |
|---|---|
| UI | Streamlit |
| 브라우저 자동화 | undetected-chromedriver + Selenium |
| HTML 파싱 | BeautifulSoup4 |
| 엑셀 출력 | openpyxl |
| Google Sheets | gspread + google-auth |

## 폴더 구조

```
product-info-crawler/
├── main.py                      # Streamlit UI + 크롤링 오케스트레이션
├── scrapers/
│   ├── base_scraper.py          # 공통 크롤링 로직 (템플릿 메서드 패턴)
│   ├── registry.py              # 브랜드명 → 스크래퍼 클래스 자동 매핑
│   └── {brand}_scraper.py       # 브랜드별 구현체
├── config/
│   └── {brand}.json             # 브랜드별 설정 (카테고리 URL, 셀렉터 등)
├── utils/
│   ├── config_loader.py         # JSON 설정 로드 + 유효성 검사
│   ├── excel_helper.py          # openpyxl 래퍼
│   ├── gsheet_helper.py         # gspread 래퍼
│   ├── helper.py                # 스크롤, 가격 파싱 유틸
│   ├── debug_helper.py          # HTML 스냅샷 저장
│   ├── image_downloader.py      # 상품 이미지 로컬 저장
│   └── lv_stock_api.py          # LV 한국 매장 재고 조회 (Selenium fetch 기반)
├── credentials/
│   └── service_account.json     # Google Sheets 서비스 계정 키 (git 제외)
└── tmp_debug/
    └── {brand_id}/              # 차단 페이지 스냅샷 + 상세 진단 JSON
```

## 데이터 컬럼 구조

엑셀/Google Sheets 공통 헤더:

```
번호 | 상품명 | 레퍼런스 | 색상 | 소재 | 카테고리 | 가격 | 사이즈 | 설명 | 재고매장 | 링크
```

- **레퍼런스**: 브랜드 고유 SKU. LV는 `M46990`(가방) / `Z3445U`(선글라스) 혼용 패턴 — 정규식 `[A-Z][0-9]{4}[0-9A-Z]`
- **재고매장**: LV는 상세 수집 시 자동 채워짐. 재고 없는 경우 빈값. 별도 "재고 매장 확인" 모드에서도 갱신 가능
- 엑셀 저장 위치: `~/Desktop/Brand_Product_Data/{브랜드명}.xlsx`
- Google Sheets 시트명 패턴: `{브랜드명} : {카테고리명}`

## 카테고리 수집 플로우

```
parse_category(category_name, url)
  ├── _before_navigate()                    # Hook: 브랜드별 오버라이드 가능
  ├── driver.get(url)
  ├── _dismiss_known_popups()               # 쿠키 동의 팝업 처리
  ├── scroll_until_lazy_content_loaded()    # 무한스크롤 + 더보기 버튼 클릭
  ├── _detect_block_reason()                # 봇 차단 감지
  └── extract_products_from_html()          # (추상 메서드) 브랜드별 구현
```

## 상세 정보 수집 플로우 (`fetch_detail: true`일 때)

```
enrich_with_details(products)                 # 5개마다 체크포인트 저장
  └── parse_detail(url)
        ├── _wait_for_detail_content()        # Hook: 렌더링 완료 대기 (브랜드별 오버라이드)
        ├── _parse_detail_from_next_data()    # __NEXT_DATA__ JSON 우선 (LV: 항상 빈 dict)
        ├── _extract_page_images()            # og:image 등 메타 태그에서 이미지 수집
        └── _fill_from_selectors()            # CSS 셀렉터 최종 폴백 (브랜드별 오버라이드)
```

**LV 전용 추가 단계** (`lv_scraper.py`가 `parse_detail` 오버라이드):
```
parse_detail(url)  [LvScraper]
  ├── super().parse_detail(url)               # 위 공통 플로우
  └── fetch_stores_with_stock_via_driver()    # 브라우저 fetch로 재고 매장 API 호출
```

LV는 Nuxt.js(Vue SSR) 앱이라 `__NEXT_DATA__`가 없음. 모든 상세 파싱은 `_fill_from_selectors`에서 CSS 셀렉터로 처리.

### LV 상세 필드별 셀렉터

| 필드 | 셀렉터 |
|---|---|
| 설명 | `p.lv-product__description` |
| 사이즈 | `div.lv-product-dimension bdo` (없는 상품은 빈값) |
| 색상 | `button.lv-product-variations__selector` 중 "소재" 버튼 → 없으면 특징 ul 첫 3개 li |
| 소재 | `div.lv-product-detailed-features__description ul > li` 첫 5개 |
| 재고매장 | LV API `POST /stores/query` — Selenium execute_async_script로 브라우저 쿠키 포함 호출 |

### LV 재고 API 주의사항

- `utils/lv_stock_api.py`에 `client_id`/`client_secret` 하드코딩 (LV 공개 키)
- 직접 `requests` 호출 불가 — Akamai `_abck` 쿠키가 필요하므로 반드시 Selenium 브라우저 컨텍스트에서 호출
- 호출 전 드라이버가 `kr.louisvuitton.com` 도메인에 있어야 함

## 제품 데이터 추출 우선순위

1. `__NEXT_DATA__` JSON (가장 정확 — LV는 해당 없음)
2. `JSON-LD` (`application/ld+json`)
3. CSS 셀렉터 (폴백)
