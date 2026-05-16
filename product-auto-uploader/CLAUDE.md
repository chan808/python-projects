# product-auto-uploader

## 프로젝트 개요

엑셀 파일에서 상품 정보를 읽어 **트렌비, 필웨이, 머스트잇** 3개 사이트에 자동 업로드하는 Windows 데스크톱 도구.
"C:\Users\freetime\Desktop\product_info\Louis Vuitton.xlsx" 양식을 기반으로 하고, 실사용 시에는 사용자가 원하는 엑셀 파일을 등록해서 사용하도록 함.

- 브라우저 세션 저장 방식으로 비밀번호 불필요 (최초 1회 수동 로그인 후 재사용)
- GUI(Tkinter) + CLI 둘 다 지원
- 수동 모드(1개씩 폼 채운 뒤 브라우저에서 확인) / 자동 모드(순차 자동 제출)
- 마지막 업로드 행 번호 자동 저장, 재시작 시 이어서 진행
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
3. "신규 상품 생성" 버튼 클릭




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

## 사이트별 구현 현황

### 머스트잇 (mustit) — 구현 완료
- `app/uploaders/mustit.py` — base.py를 상속하되 `run()` 완전 오버라이드
- add01 → add02 페이지 전환, 동의 모달 처리
- 브랜드: JS DOM에서 `[id^="brand_list_"] span` 텍스트 매칭 후 클릭
- 카테고리: `#flag_Women` 클릭 → 검색창 입력 → 첫 번째 결과 클릭
- 색상/사이즈: 옵션 체크박스 활성화 후 텍스트 입력 (각 10자 제한)
- 이미지: `input[type='file']` → `input#uploadfiles` 버튼 클릭
- 자동 로그인: `input[name='id']`, `input[name='pw']`

### 필웨이 (fillway) — 구현 완료 (테스트 필요)
- `app/uploaders/fillway.py` — base.py를 상속하되 `run()` 완전 오버라이드
- 약관: `#clauseTotal` 전체 동의 체크
- 브랜드: `#brandAutoCompleteKeyword` 타입 → 자동완성 목록 첫 번째 클릭
- 카테고리: `_CATEGORY_MAP`으로 키워드 매핑 → 라디오 버튼 클릭
- 필드: `#proprietaryName`(상품명), `#sellingPrice`(가격), `input[name='model_name']`(레퍼런스), `textarea#g_intro`(설명)
- 이미지: `input.photoFile` 첫 번째에 파일 세팅
- 제출: `button#productRegisterSubmit`
- 자동 로그인: `input[name='id']`, `input[name='passwd']` (passwd 주의)

### 트렌비 (trenbe) — 미구현
- `app/uploaders/trenbe.py` — 빈 클래스 상태
- `selectors/trenbe.json` — TODO 플레이스홀더 상태
- 등록 URL: `https://partner.trenbe.com/v2/product`

---

## 참고: selectors/*.json 역할

머스트잇·필웨이처럼 `run()`을 완전 오버라이드한 업로더는 selectors JSON을 직접 참조하지 않음.
base.py의 `_fill_fields`를 그대로 쓰는 업로더(트렌비 등)만 selectors JSON 필요.

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
