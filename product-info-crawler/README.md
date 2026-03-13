# Product Info Crawler

브랜드 카테고리 페이지에서 상품 정보를 수집해 Google Sheets 또는 Excel에 저장하는 내부용 크롤러입니다.
브랜드별 설정은 `config/*.json`에 두고, 실행 UI는 Streamlit으로 제공합니다.

## 현재 지원 기능

- `config` 디렉터리의 브랜드 설정 자동 탐색
- 브랜드별 scraper 동적 로딩
- 카테고리별 선택 실행
- Google Sheets / Excel 저장 대상 선택
- `덮어쓰기` / `이어쓰기` 저장 방식 선택
- 실행 진행률과 카테고리별 성공/실패 표시

## 디렉터리 구조

- `main.py`: Streamlit 진입점
- `config/`: 브랜드별 설정 파일
- `scrapers/`: 브랜드별 scraper 구현과 registry
- `utils/`: 설정 로더, Google Sheets/Excel 저장 헬퍼
- `credentials/`: 서비스 계정 키 파일 위치
- `tests/`: 스모크 테스트

## 설치

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Google Sheets 서비스 계정 키는 `credentials/service_account.json` 경로에 둡니다.

## 실행

```bash
streamlit run main.py
```

실행 후 화면에서 아래 순서로 사용합니다.

1. 브랜드 선택
2. 저장 대상 선택
3. 저장 방식 선택
4. 수집할 카테고리 선택
5. `크롤링 시작` 실행

## Excel 저장 경로

- 저장 폴더: `바탕화면/Brand_Product_Data`
- 파일명: 선택한 브랜드명과 동일한 `.xlsx` 파일
- 시트명: 사용자가 선택한 카테고리명

예시:

- `C:\Users\<사용자>\Desktop\Brand_Product_Data\Celine.xlsx`
- 시트: `Belts(Woman)`, `Bracelets(Woman)`

## 브랜드 추가 방법

1. `scrapers/{brand_key}_scraper.py` 파일 추가
2. 클래스 이름을 `{BrandKey}Scraper` 규칙으로 작성
3. `config/{brand_id}.json` 추가
4. 설정 파일의 `brand` 섹션에 아래 값 입력

```json
"brand": {
  "id": "celine",
  "display_name": "Celine",
  "scraper": "celine"
}
```

## 테스트

```bash
python -m unittest discover -s tests
```
