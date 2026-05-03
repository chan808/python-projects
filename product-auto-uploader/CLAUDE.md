# product-auto-uploader

## 프로젝트 개요

엑셀 파일에서 상품 정보를 읽어 **트렌비, 필웨이, 머스트잇** 3개 사이트에 자동 업로드하는 Windows 데스크톱 도구.
"C:\Users\freetime\Desktop\product_info\Louis Vuitton.xlsx" 양식을 기반으로 하고, 실사용 시에는 사용자가 원하는 엑셀 파일을 등록해서 사용하도록 함.

- 브라우저 세션 저장 방식으로 비밀번호 불필요 (최초 1회 수동 로그인 후 재사용)
- GUI(Tkinter) + CLI 둘 다 지원
- 미리보기 모드(첫 상품만, 자동 제출 안 함) / 자동 제출 모드
---
## 로그인용 계정 정보
- 나중에 변경할 비밀번호라서 일단 보안은 신경쓸 필요가 적음
- 필웨이, 머스트잇 id, pw
ID : confiance
PW : qhdks1q2w#$
- 트렌비 id, pw
ID : confiance
PW : Qhdks1q2w#$

- 머스트잇은 다음 방식으로 실제 판매 등록 페이지에 접근 가능
1. 다음 사이트에 접속 "https://mustit.co.kr/product/add01"
2. 알림창이 뜨는데 없앤 후, ID와 PW 입력 후 로그인
3. "다음단계" 버튼 클릭

- 필웨이는 다음 방식으로 실제 판매 등록 페이지에 접근 가능
1. 다음 사이트에 접속 "https://www.feelway.com/tobe/page/mypage/productRegistration.php"
2. 알림창이 뜨는데 없앤 후, ID와 PW 입력 후 로그인

- 트렌비는 다음 방식으로 실제 판매 등록 페이지에 접근 가능
1. 다음 사이트에 접속 "https://partner.trenbe.com/v2/product"
2. ID와 PW 입력 후 로그인




---

## 기술 스택

| 분류 | 기술 |
|---|---|
| Language | Python 3.9 |
| 브라우저 자동화 | Playwright (Chromium) |
| 엑셀 파싱 | openpyxl |
| 데이터 검증 | Pydantic v2 |
| GUI | Tkinter |
| 실행 환경 | Windows (APPDATA/LOCALAPPDATA 경로 사용) |

---

## 폴더 구조

```
product-auto-uploader/
├── app/
│   ├── models.py              # ProductInput, SiteConfig, SiteSelectors, UploadResult
│   ├── config.py              # 설정 로드/저장 (APPDATA\ProductAutoUploader\user-config.json)
│   ├── services/
│   │   ├── excel_service.py   # 엑셀 → List[ProductInput] 변환
│   │   ├── upload_service.py  # 멀티 사이트 일괄 업로드 오케스트레이션
│   │   └── image_service.py   # 이미지 파일 탐색
│   ├── uploaders/
│   │   ├── base.py            # PlaywrightUploader (공통 로직 전체)
│   │   ├── mustit.py          # class MustitUploader(PlaywrightUploader): SITE = "mustit"
│   │   ├── trenbe.py          # class TrenbeUploader(PlaywrightUploader): SITE = "trenbe"
│   │   └── fillway.py         # class FilwayUploader(PlaywrightUploader): SITE = "fillway"
│   ├── ui/
│   │   ├── gui.py             # Tkinter GUI (엑셀 파일 선택 + 사이트 체크박스)
│   │   └── cli.py             # CLI (--excel, --sites, --submit-mode)
│   └── utils/
│       ├── logging_utils.py
│       └── text_normalizer.py # 브랜드명 정규화 (이미지 폴더 경로용)
├── selectors/
│   ├── mustit.json            # 머스트잇 폼 필드 CSS 셀렉터
│   ├── trenbe.json            # 트렌비 폼 필드 CSS 셀렉터
│   └── fillway.json           # 필웨이 폼 필드 CSS 셀렉터
└── app/main.py                # GUI 진입점
```

---

## 업로드 플로우

```
1. 엑셀 파일 선택 (예: "Louis Vuitton.xlsx")
       ↓
2. brand_name = 파일명 ("Louis Vuitton")
   products = 194건 파싱 (재고매장 컬럼 제외)
       ↓
3. 각 상품 × 선택된 사이트
   - 이미지 탐색: register_pic_root / normalize(brand) / product_code /
   - Playwright 브라우저 오픈 (사이트별 세션 디렉토리)
   - 폼 필드 자동 입력 (selectors/*.json 기준)
   - 이미지 업로드
   - preview: 제출 안 함 / submit: 제출 버튼 클릭
```

---

## 엑셀 컬럼 매핑

| 엑셀 컬럼 | ProductInput 필드 | 필수 |
|---|---|---|
| 상품명 | product_name | ✓ |
| 레퍼런스 | product_code | ✓ |
| 카테고리 | category | ✓ |
| 가격 | price | ✓ |
| 색상 | color | - |
| 소재 | material | - |
| 사이즈 | size | - |
| 설명 | description | - |
| 번호 | (무시) | - |
| 재고매장 | (제외) | - |

brand_name은 엑셀 **파일명**에서 자동 추출.

---

## 설정 파일 위치

- 사용자 설정: `%APPDATA%\ProductAutoUploader\user-config.json`
- 브라우저 세션: `%LOCALAPPDATA%\ProductAutoUploader\playwright-profile\{mustit|trenbe|fillway}\`
- 로그: `%LOCALAPPDATA%\ProductAutoUploader\logs\`
- 결과 JSON: `%LOCALAPPDATA%\ProductAutoUploader\output\`

---

## 이미지 폴더 규칙

```
register_pic_root/
└── {normalize(brand_name)}/   # text_normalizer.py 적용 or brand_aliases 우선
    └── {product_code}/
        ├── 01.jpg
        └── 02.jpg
```

`brand_aliases`로 정규화 결과를 재정의 가능 (예: `"louis vuitton" → "LV"`).

---

## 현재 상태 (TODO)

**3개 사이트 모두 selectors/*.json이 TODO 플레이스홀더 상태** → 실제 폼 셀렉터 입력 필요.

각 사이트별로 필요한 항목:
1. 상품 등록 페이지 URL (`register_url`)
2. 로그인 확인 CSS 셀렉터 (`login_check_selector`) — 로그인 후 보이는 요소
3. 폼 필드 CSS 셀렉터: category, brand_name, product_code, product_name, price, color, material, size, description
4. 이미지 업로드 `<input type="file">` 셀렉터
5. 제출 버튼 셀렉터

TODO 셀렉터가 있는 필드는 자동 스킵됨 (크래시 없음). 값이 None인 선택 필드도 자동 스킵.

각 필드의 `action` 종류:
- `fill`: 일반 텍스트 입력
- `select_option`: `<select>` 드롭다운
- `type`: 자동완성 필드 (키보드 입력 시뮬레이션)

---

## 새 사이트 추가 방법

1. `app/uploaders/newsite.py` 생성: `class NewSiteUploader(PlaywrightUploader): SITE = "newsite"`
2. `selectors/newsite.json` 생성 (mustit.json 복사 후 셀렉터 채우기)
3. `app/config.py`: `SITES` 튜플과 `DEFAULT_SELECTORS_PATHS`에 추가
4. `app/models.py`: `AppConfig`에 필드 추가
5. `app/services/upload_service.py`: `UPLOADER_CLASSES`에 추가
6. `app/ui/gui.py`: `SITE_LABELS`에 추가

---

## 실행

```bash
pip install -r requirements.txt
playwright install chromium

# GUI
python app/main.py

# CLI (엑셀 기반 일괄 업로드)
python -m app.ui.cli --excel "C:/path/to/brand.xlsx" --sites mustit,trenbe --submit-mode preview

# CLI (로그인 세션 준비)
python -m app.ui.cli --prepare-login mustit
```
