# 디버깅 가이드

## 차단 페이지 확인

차단 감지 시 `tmp_debug/{brand_id}/` 폴더에 HTML 스냅샷이 저장된다.

파일명 패턴: `{카테고리명}_{차단종류}_{날짜시간}.html`

브라우저로 열면 실제 차단 화면 내용 확인 가능.

## 상세 페이지 파싱 진단

`fetch_detail: true` 상태에서 각 카테고리의 처음 3개 상품 파싱 결과가 자동 저장된다.

```
tmp_debug/{brand_id}/diag_01.json
tmp_debug/{brand_id}/diag_02.json
tmp_debug/{brand_id}/diag_03.json
```

JSON 구조:
```json
{
  "url": "https://...",
  "detail": {
    "description": "...",
    "sizes": "...",
    "image_urls": "..."
  }
}
```

## 분석 스크립트

루트에 `analyze_lv.py`, `analyze_dior.py` 등 일회성 분석 스크립트가 있다. HTML 구조 파악용으로 사용 후 커밋 불필요.

## 흔한 오류

| 오류 | 원인 | 해결 |
|---|---|---|
| `PermissionError: 엑셀 파일이 열려 있습니다` | 엑셀 파일이 열린 상태 | 파일 닫고 재실행 |
| `RuntimeError: 차단 페이지가 감지되었습니다` | 봇 차단 | `tmp_debug/` 스냅샷 확인 후 딜레이 조정 |
| `RuntimeError: 상품을 찾지 못했습니다` | 셀렉터 불일치 또는 차단 | HTML 스냅샷에서 실제 구조 확인 |
| `gspread.SpreadsheetNotFound` | Sheets 파일명 불일치 | `config.google_sheets.spreadsheet_name` 확인 |
| `ConfigError: 서비스 계정 키 파일이 없습니다` | credentials 파일 누락 | `credentials/service_account.json` 확인 |
