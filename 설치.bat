@echo off
title 쇼핑몰 크롤러 - 설치하기

REM 현재 폴더 기준
cd /d "%~dp0"

echo [1] Python 가상환경 생성 중...
python -m venv .venv
if errorlevel 1 (
    echo Python 이 설치되어 있는지 먼저 확인해주세요.
    pause
    exit /b 1
)

echo [2] 가상환경 활성화...
call .venv\Scripts\activate.bat

echo [3] 필요한 라이브러리 설치 중... (몇 분 걸릴 수 있습니다)
pip install --upgrade pip
pip install -r requirements.txt

echo ----------------------------------------
echo 설치가 완료되었습니다.
echo 이제 "실행하기.bat" 를 더블클릭해서 프로그램을 실행하세요.
echo ----------------------------------------
pause