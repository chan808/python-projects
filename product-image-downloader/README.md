# Image Extractor

명품 브랜드 공식 사이트에서 상품코드 기반으로 상품 이미지를 자동 수집하고,
배경 제거 + 1000x1000 정규화 처리 후 저장하는 프로그램.

## 지원 브랜드

- Celine
- Dior
- Vottega Veneta

## 설치

```bash
# 가상환경 생성 (권장)
python -m venv venv
venv\Scripts\activate   # Windows

# 의존성 설치 (가상환경 내에서)
pip install -r requirements.txt
```

**필수 사전 설치:**
- Python 3.10+
- Google Chrome 브라우저 (ChromeDriver 자동 설치됨)

## 실행

```bash
streamlit run ui/app.py
```

또는

```bash
python main.py
```

브라우저에서 `http://localhost:8501` 으로 접속

## 사용 방법

1. **브랜드 선택** - 드롭다운에서 브랜드를 선택합니다.
2. **상품코드 입력** - 아래 3가지 방법 중 선택:
   - **직접 입력**: 상품코드를 줄바꿈 또는 쉼표로 구분하여 입력
   - **Excel 업로드**: `.xlsx` 파일을 업로드하고, 열(Column)과 행(Row) 범위를 지정
   - **Google Spreadsheet**: 공개 스프레드시트 URL을 입력하고, 열/행 지정
3. **실행** 버튼 클릭
4. 처리 완료 후 바탕화면에 결과 저장됨

## 행(Row) 지정 형식

| 형식 | 설명 | 예시 |
|------|------|------|
| `5-8` | 연속 범위 | 5행 ~ 8행 |
| `2,3,4` | 개별 지정 | 2, 3, 4행 |
| `2, 5-7, 10` | 혼합 | 2행, 5~7행, 10행 |

## 저장 경로

```
바탕화면/{브랜드명}/{상품코드}/
  ├── {상품코드}_01.png
  ├── {상품코드}_02.png
  └── ...
```

예: `Desktop/celine/L100J2X9838SI/L100J2X9838SI_01.png`

## 처리 파이프라인

1. 최대 해상도 이미지 다운로드
2. rembg로 배경 제거
3. 1000x1000 캔버스에 비율 유지 리사이즈 + 중앙 정렬 + 흰색 배경 패딩
4. PNG로 저장

## 브랜드 추가 방법

`core/crawler/` 폴더에 새 모듈을 추가한 후 `core/crawler/registry.py`의 `_ensure_loaded()`에 import를 추가

## 프로젝트 구조

```
image-extractor/
├── core/
│   ├── crawler/
│   │   ├── base.py           # 추상 기본 크롤러
│   │   └── registry.py       # 브랜드 레지스트리
│   ├── image_processor/
│   │   └── processor.py      # 배경 제거 + 리사이즈
│   ├── spreadsheet_reader/
│   │   └── reader.py         # Excel/Google Sheets 읽기
│   └── driver.py             # Selenium 드라이버 팩토리
├── ui/
│   └── app.py                # Streamlit 웹 UI
├── config.py                 # 전역 설정
├── main.py                   # 실행 진입점
├── requirements.txt
└── README.md
```
