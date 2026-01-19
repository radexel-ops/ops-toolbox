@echo off
setlocal ENABLEDELAYEDEXPANSION
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

REM ===== 설정 =====
set "APP_ENTRY=master_app.py"          REM ← 실행할 파이썬 파일명 필요 시 변경
set "PY_VERSIONS=3.12 3.11 3.10"

REM ===== 경로 =====
set "PROJ_DIR=%~dp0"
set "SHARED_VENV=%PROJ_DIR%.venv"
set "LOCAL_VENV=%LOCALAPPDATA%\RDXL_RPA\.venv"
set "REQ=%PROJ_DIR%requirements.txt"
set "LOG=%PROJ_DIR%run_app.log"

echo [1/6] Project: "%PROJ_DIR%"

REM ===== 공유 .venv 유효성 검사 (pyvenv.cfg의 home 경로 존재 여부로 판별)
set "USE_SHARED=0"
if exist "%SHARED_VENV%\Scripts\python.exe" (
  if exist "%SHARED_VENV%\pyvenv.cfg" (
    for /f "usebackq delims=" %%L in (`
      powershell -NoLogo -NoProfile -Command ^
        "(Get-Content -Raw '%SHARED_VENV%\pyvenv.cfg') -split \"`n\" | ? {$_ -match '^\s*home\s*='} | select -first 1 | %% {$_ -replace '.*=\s*',''}"
    `) do set "VHOME=%%L"
    if defined VHOME (
      if exist "%VHOME%\python.exe" (
        set "USE_SHARED=1"
        echo [2/6] Shared venv OK → "%SHARED_VENV%"
      ) else (
        echo [2/6] Shared venv INVALID (home="%VHOME%") → will use LOCAL venv
      )
    ) else (
      echo [2/6] Shared venv pyvenv.cfg parse failed → will use LOCAL venv
    )
  ) else (
    echo [2/6] Shared venv has no pyvenv.cfg → will use LOCAL venv
  )
) else (
  echo [2/6] Shared venv not found → will use LOCAL venv
)

REM ===== 사용할 venv 디렉토리 선택
if "%USE_SHARED%"=="1" (
  set "VENV_DIR=%SHARED_VENV%"
) else (
  set "VENV_DIR=%LOCAL_VENV%"
)

set "PYEXE=%VENV_DIR%\Scripts\python.exe"

REM ===== 로컬 venv가 필요하면 생성
if not exist "%PYEXE%" (
  echo [3/6] Create local venv at "%VENV_DIR%" ...
  for %%V in (%PY_VERSIONS%) do (
    py -%%V -c "import sys;print(sys.version)" >nul 2>&1 && (
      echo    - Using Python %%V
      py -%%V -m venv "%VENV_DIR%" && goto :venv_ok
    )
  )
  echo    - Fallback to default py
  py -m venv "%VENV_DIR%" || (echo [ERROR] venv create failed & goto :fail_pause)
)
:venv_ok

REM ===== 패키지 설치/업그레이드 (로그 기록)
echo [4/6] Upgrade pip & install packages...
"%PYEXE%" -m pip install --upgrade pip >> "%LOG%" 2>&1
if exist "%REQ%" (
  "%PYEXE%" -m pip install -r "%REQ%" >> "%LOG%" 2>&1
) else (
  "%PYEXE%" -m pip install --upgrade ^
    openai google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2 requests >> "%LOG%" 2>&1
)

REM ===== 실행 파일 확인
if not exist "%PROJ_DIR%%APP_ENTRY%" (
  echo [ERROR] Not found: "%APP_ENTRY%" 1>&2
  goto :fail_pause
)

REM ===== 앱 실행
echo [5/6] Run app (log: "%LOG%") ...
echo ==== %DATE% %TIME% ================================== >> "%LOG%"
"%PYEXE%" -X utf8 -u "%PROJ_DIR%%APP_ENTRY%" 1>>"%LOG%" 2>&1
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
  echo [6/6] Exited with error (%RC%). Last 50 lines of log:
  powershell -NoLogo -NoProfile -Command "Get-Content -Path '%LOG%' -Tail 50"
  goto :fail_pause
)

echo [6/6] App finished normally. (ReturnCode=%RC%)
goto :end

:fail_pause
echo.
echo === Press any key to close ===
pause >nul
:end
endlocal
