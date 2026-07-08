@echo off

rem Streamlit 웹앱 접속 설정입니다.
rem 기본값은 사내망 다른 PC에서도 접속할 수 있도록 0.0.0.0:8763 입니다.
rem 특정 PC 내부에서만 실행하려면 WLC_WEB_ADDRESS를 127.0.0.1 로 변경하세요.

set "WLC_WEB_ADDRESS=0.0.0.0"
set "WLC_WEB_PORT=8763"
