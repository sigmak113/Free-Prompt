@echo off
chcp 65001 >nul
echo ===================================================
echo   간단 프롬프터 EXE 빌드
echo ===================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [오류] 파이썬이 설치되어 있지 않습니다.
    echo https://www.python.org 에서 Python 3.10 이상을 설치한 뒤
    echo "Add python.exe to PATH" 옵션을 체크하고 다시 실행하세요.
    pause
    exit /b 1
)

echo [1/3] PyInstaller 설치 확인 중...
python -m pip install --upgrade pyinstaller

echo.
echo [2/3] EXE 빌드 중... (Teleprompter.exe)
python -m PyInstaller --onefile --noconsole --name Teleprompter teleprompter.py

echo.
echo [3/3] 완료!
echo dist 폴더 안의 Teleprompter.exe 파일을 실행하세요.
echo.
pause
