WLC Role ACL Collector Streamlit 웹앱 실행 안내
================================================

이 ZIP은 Windows PC에서 Python을 별도로 설치하지 않고 실행하는 웹앱 패키지입니다.
ZIP 안에 내장 Python, 앱 코드, 실행에 필요한 라이브러리가 함께 들어 있습니다.

1. 실행 방법
-----------

1) GitHub Release에서 아래 파일을 다운로드합니다.
   - wlc-role-acl-collector_vYYYY.MM.DD-HHMMSS_streamlit_windows_portable.zip
   - wlc-role-acl-collector_vYYYY.MM.DD-HHMMSS_streamlit_windows_portable.zip.sha256

2) ZIP 파일을 원하는 폴더에 압축 해제합니다.
   예: C:\Tools\wlc-role-acl-collector-web

3) 압축을 푼 폴더에서 start_webapp.cmd 를 더블클릭합니다.

4) 브라우저에서 아래 주소로 접속합니다.
   - 실행한 PC에서 접속: http://127.0.0.1:8763
   - 다른 사내 PC에서 접속: http://공용PC_IP:8763

2. 포트 변경
------------

기본 포트는 8763입니다.
포트를 바꾸려면 webapp_settings.cmd 파일을 메모장으로 열고 아래 값을 변경합니다.

set "WLC_WEB_PORT=8763"

특정 PC 내부에서만 접속하게 하려면 아래처럼 변경합니다.

set "WLC_WEB_ADDRESS=127.0.0.1"

3. 방화벽과 네트워크
-------------------

다른 PC에서 접속하려면 실행 PC의 Windows 방화벽에서 TCP 8763 포트 허용이 필요할 수 있습니다.
서버 역할을 하는 실행 PC가 WLC에 접속 가능한 네트워크에 있어야 합니다.
실행 PC가 절전모드에 들어가거나 전원이 꺼지면 웹앱 접속도 끊깁니다.

4. Role 대역 Excel
-----------------

예제 파일은 config\role_networks.example.xlsx 입니다.
웹앱 화면에서 사내 Role 대역표 Excel 파일을 업로드하면 보고서에 내부 대역 비교 결과를 포함할 수 있습니다.
Excel에 Role_Networks Sheet가 있으면 해당 Sheet를 우선 사용하고, 없으면 첫 번째 Sheet를 사용합니다.

5. 주의사항
-----------

이 웹앱은 인터넷 공개용 서비스가 아닙니다.
접속 주소를 아는 사내 사용자는 화면에 접근할 수 있습니다.
장비 계정, 비밀번호, 내부 대역 정보는 코드나 파일에 저장하지 말고 실행 화면에서만 입력하세요.
