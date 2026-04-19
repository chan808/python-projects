# Product Auto Uploader

4명의 사용자가 각자 PC에서 실행하는 로컬 자동 업로드 도구 골격이다.

## 로그인 전략

비밀번호를 `json` 파일에 저장하는 방식은 권장하지 않는다.

- 보안상 취약하다.
- 사용자 PC 분실이나 공유 시 위험하다.
- 사이트 로그인 정책 변경에 취약하다.

현재 구조는 비밀번호 대신 `브라우저 로그인 세션`을 사용자별 로컬 폴더에 저장한다.

- 설정 파일: `%APPDATA%\ProductAutoUploader\user-config.json`
- 브라우저 세션: `%LOCALAPPDATA%\ProductAutoUploader\playwright-profile`
- 로그/스크린샷/결과: `%LOCALAPPDATA%\ProductAutoUploader\...`

즉, 사용자는 최초 1회 로그인만 해두면 이후 반복 입력 없이 같은 세션을 재사용할 수 있다.

## 설치

```powershell
pip install -r requirements.txt
python -m playwright install chromium
```

또는 배포용으로는 `setup.bat`을 실행하면 된다.

## 사용자 준비

1. 앱을 실행한다.
2. `이미지 루트 폴더`를 확인한다.
3. `머스트잇 등록 URL`을 입력한다.
4. `로그인 확인 셀렉터`를 입력한다.
5. `설정 저장`을 누른다.
6. `로그인 세션 준비`를 눌러 브라우저에서 1회 로그인한다.

## 실행 방식

일반 사용자는 GUI를 사용한다.

```powershell
python -m app.main
```

또는 `run_gui.bat`을 실행한다.

고급 사용자는 CLI도 사용할 수 있다.

```powershell
python -m app.ui.cli --prepare-login
python -m app.ui.cli --category 가방 --brand-name dior --product-code H064289S01 --product-name "Lady Dior" --price 4200000
```

기본 모드는 `preview`다. 즉, 입력과 이미지 업로드까지만 진행하고 최종 제출은 직접 확인 후 진행한다.

## 머스트잇 셀렉터

실제 등록 폼 셀렉터는 [mustit.json](C:\Users\freetime\Desktop\python-projects\product-auto-uploader\selectors\mustit.json)에 채워야 한다.

아직 `TODO_*` 상태라서, 실제 화면 확인 후 수정이 필요하다.
