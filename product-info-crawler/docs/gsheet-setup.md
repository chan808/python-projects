# Google Sheets 설정

## 초기 설정 순서

1. [Google Cloud Console](https://console.cloud.google.com)에서 프로젝트 생성
2. **Google Sheets API** + **Google Drive API** 활성화
3. 서비스 계정 생성 → JSON 키 파일 다운로드
4. 키 파일을 `credentials/service_account.json`으로 저장
5. 사용할 Google Sheets 파일을 서비스 계정 이메일로 **편집자 공유**
6. `config/{brand}.json`의 `google_sheets.spreadsheet_name`을 Sheets 파일명과 정확히 일치시킬 것

## 주의 사항

- `credentials/service_account.json`은 `.gitignore`에 포함 — 절대 커밋하지 말 것
- Sheets 파일명 오타 시 `gspread.SpreadsheetNotFound` 에러 발생
- 새 시트 생성 시 초기 행 수는 5000으로 설정됨 (`WORKSHEET_INITIAL_ROWS`)
