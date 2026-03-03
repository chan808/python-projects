@echo off
title 쇼핑몰 크롤러 - 실행하기

cd /d "%~dp0"

echo 가상환경 활성화 중...
call .venv\Scripts\activate.bat

echo 프로그램을 실행합니다. 브라우저가 자동으로 열립니다.
streamlit run main.py

echo 프로그램이 종료되었습니다.
pause