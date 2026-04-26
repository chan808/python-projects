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
│   └── image_downloader.py      # 상품 이미지 로컬 저장
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

- **레퍼런스**: 브랜드 고유 SKU (예: LV는 `M12345` 패턴)
- **재고매장**: 미구현 — 추후 매장 재고 확인 기능에서 채울 컬럼
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
enrich_with_details(products)
  └── parse_detail(url)
        ├── _parse_detail_from_next_data()  # __NEXT_DATA__ JSON 우선
        ├── _extract_page_images()          # og:image 등 메타 태그 폴백
        └── _fill_from_selectors()          # CSS 셀렉터 최종 폴백
```

## 제품 데이터 추출 우선순위

1. `__NEXT_DATA__` JSON (가장 정확)
2. `JSON-LD` (`application/ld+json`)
3. CSS 셀렉터 (폴백)
