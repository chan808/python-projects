# product-info-crawler

명품 브랜드 상품 정보 수집기. Streamlit UI로 실행, 결과는 엑셀 또는 Google Sheets에 저장.

**실행**: `streamlit run main.py` (또는 `실행.bat`)
**설치**: `설치.bat`

## 두 가지 사용 목적

1. **초기 수집** — 카테고리 URL의 전체 상품을 엑셀/Sheets로 저장
2. **재고 확인** — 수집된 상품의 매장별 재고 현황 업데이트 (미구현)

## 지원 브랜드

| 브랜드 | 설정 파일 | 스크래퍼 | 상태 |
|---|---|---|---|
| Louis Vuitton | `config/lv.json` | `scrapers/lv_scraper.py` | 완성 |
| Dior | `config/dior.json` | `scrapers/dior_scraper.py` | 완성 |
| Bottega Veneta | `config/bottega.json` | `scrapers/bottega_scraper.py` | 검증 필요 |
| Celine | `config/celine.json` | `scrapers/celine_scraper.py` | 검증 필요 |

## 상세 문서

- [아키텍처 및 폴더 구조](docs/architecture.md)
- [새 브랜드 추가 방법](docs/add-brand.md)
- [브랜드 설정 파일 가이드](docs/config-guide.md)
- [봇 탐지 대응](docs/bot-detection.md)
- [Google Sheets 설정](docs/gsheet-setup.md)
- [디버깅 가이드](docs/debugging.md)
