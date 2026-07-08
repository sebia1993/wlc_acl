@echo off
setlocal

cd /d "%~dp0"

if exist "%~dp0webapp_settings.cmd" (
    call "%~dp0webapp_settings.cmd"
)

if "%WLC_WEB_ADDRESS%"=="" set "WLC_WEB_ADDRESS=0.0.0.0"
if "%WLC_WEB_PORT%"=="" set "WLC_WEB_PORT=8763"

set "PYTHON_EXE=%~dp0python\python.exe"
set "PYTHONPATH=%~dp0python\Lib\site-packages;%~dp0app;%PYTHONPATH%"

if not exist "%PYTHON_EXE%" (
    echo [ERROR] 내장 Python 실행 파일을 찾을 수 없습니다.
    echo [ERROR] ZIP 압축을 완전히 푼 뒤 다시 실행하세요.
    pause
    exit /b 1
)

if /I "%~1"=="--smoke" (
    "%PYTHON_EXE%" -c "import streamlit; import wlc_role_acl_collector.web_logic; print('STREAMLIT_PORTABLE_OK')"
    exit /b %ERRORLEVEL%
)

echo [INFO] WLC Role ACL Collector Streamlit 웹앱을 시작합니다.
echo [INFO] 이 창을 닫으면 웹앱도 종료됩니다.
echo [INFO] 로컬 접속 주소: http://127.0.0.1:%WLC_WEB_PORT%
echo [INFO] 다른 PC 접속 주소 예시: http://공용PC_IP:%WLC_WEB_PORT%
echo.

"%PYTHON_EXE%" -m streamlit run "%~dp0app\app.py" ^
    --server.address "%WLC_WEB_ADDRESS%" ^
    --server.port "%WLC_WEB_PORT%" ^
    --server.headless true ^
    --browser.gatherUsageStats false

set "EXIT_CODE=%ERRORLEVEL%"
echo.
echo [INFO] 웹앱이 종료되었습니다. 종료 코드: %EXIT_CODE%
pause
exit /b %EXIT_CODE%
