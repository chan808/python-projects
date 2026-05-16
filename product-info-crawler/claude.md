# product-info-crawler

명품 브랜드 상품 정보 수집기. Streamlit UI로 실행, 결과는 엑셀에 저장(Google Sheets는 나중에 구현 예정이라 현재는 신경 쓰지 않음).

**실행**: `streamlit run main.py` (또는 `실행.bat`)
**설치**: `설치.bat`

## 두 가지 사용 목적

1. **초기 수집** — 카테고리 URL의 전체 상품을 엑셀/Sheets로 저장. 상세 페이지 방문 시 색상·소재·사이즈·설명·재고매장까지 한 번에 수집
2. **재고 확인** — 수집된 상품의 매장별 재고 현황 업데이트 (LV 구현 완료, 별도 모드로도 실행 가능)

## 지원 브랜드

| 브랜드 | 설정 파일 | 스크래퍼 | 상태 |
|---|---|---|---|
| Louis Vuitton | `config/lv.json` | `scrapers/lv_scraper.py` | 완성 (상세 수집 + 재고매장 포함) |
| Dior | `config/dior.json` | `scrapers/dior_scraper.py` | 완성 (상세 수집 + 재고매장 포함) |
| Bottega Veneta | `config/bottega.json` | `scrapers/bottega_scraper.py` | 검증 필요 |
| Celine | `config/celine.json` | `scrapers/celine_scraper.py` | 검증 필요 |

## 남은 작업 (LV)

- 재고매장 API 정상 작동 여부 최종 확인 (빈값 = 매장 재고 없음 vs API 오류 구분)
- 이미지 다운로드 기능 검증 (`download_images: true` 설정 시)

## 상세 문서

- [아키텍처 및 폴더 구조](docs/architecture.md)
- [새 브랜드 추가 방법](docs/add-brand.md)
- [브랜드 설정 파일 가이드](docs/config-guide.md)
- [봇 탐지 대응](docs/bot-detection.md)
- [Google Sheets 설정](docs/gsheet-setup.md)
- [디버깅 가이드](docs/debugging.md)
