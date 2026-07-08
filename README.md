# WLC Role ACL Collector

Aruba AOS8 WLC에 접속해 SSID별 기본 Role과 Role별 ACL 접근 범위를 수집하고, 운영자가 한눈에 볼 수 있는 Excel/HTML 보고서를 생성하는 도구입니다.

## 목적

- 어떤 SSID가 어떤 AAA Profile을 사용하는지 확인합니다.
- SSID별 기본 Role(`initial-role`, `mac-default-role`, `dot1x-default-role`)을 정리합니다.
- Role에 연결된 ACL 규칙과 접근 요약을 제공합니다.
- ACL에 `alias <이름>`이 있으면 netdestination 내용을 함께 정리합니다.
- ClearPass/RADIUS 동적 Role은 직접 수집하지 않고, 동적 Role 가능성으로 표시합니다.

## 현재 구현 범위

구현된 기능:

- 사내망 내부 공유용 Streamlit 웹앱 실행
- Windows GUI 실행 파일과 CLI 실행 파일 배포
- Aruba AOS8 WLC 접속 후 SSID, Role, ACL, Alias, VLAN/사용자 관측 정보 수집
- Excel/HTML 보고서 생성
- HTML 보고서 안의 Role별 ACL 보기, 주석 저장, Access Check
- 사내 Role 대역 Excel(`Role_Networks` Sheet 우선) 입력과 내부용 비교 보고서
- 안전 진단 모드와 민감정보 마스킹된 진단 보고서
- fixture/offline/mock 기반 검증과 GitHub Actions Windows Release 검증

아직 포함하지 않는 기능:

- 코드서명, installer, MSIX, SmartScreen 평판 대응
- ClearPass/RADIUS 서버에서 동적 Role을 직접 조회하는 기능
- TCP/UDP 포트 번호까지 service object를 정밀 해석하는 기능
- Streamlit 웹앱 자체 사용자 계정/권한 관리 기능
- macOS에서 Windows EXE를 직접 생성하는 공식 빌드 경로

## Streamlit 웹앱 실행

사내망 내부에서 공용 PC 또는 노트북 1대에 실행해 두고, 다른 사용자가 브라우저로 접속하는 방식입니다. 인터넷 공개용으로 설계하지 않았습니다.

### 1. 공용 PC 준비

공용 PC에는 Python 3.11 이상이 필요합니다. PowerShell에서 아래 순서로 실행합니다.

```powershell
cd "D:\Codex Project\Network\wlc_role_acl_collector"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 2. 공용 PC에서 웹앱 실행

공용 PC 안에서만 테스트할 때는 아래 명령을 사용합니다.

```powershell
streamlit run app.py
```

사내망의 다른 PC에서 접속하게 하려면 아래처럼 실행합니다.

```powershell
streamlit run app.py --server.address 0.0.0.0 --server.port 8763
```

다른 사용자는 브라우저에서 아래 주소로 접속합니다.

```text
http://공용PC_IP:8763
```

Windows 방화벽에서 TCP `8763` 포트 허용이 필요할 수 있습니다. 공용 PC가 꺼지거나 절전모드에 들어가면 접속이 끊기므로, 장시간 사용 시 전원/절전 설정을 확인하세요.

### 3. 웹 화면 사용 순서

1. 브라우저에서 Streamlit 주소에 접속합니다.
2. WLC IP 또는 Host를 입력합니다.
3. Protocol, Port, Timeout seconds를 확인합니다.
4. Username, Password, Enable password를 입력합니다.
5. 필요하면 사내 Role 대역표 Excel(`.xlsx` 또는 `.xlsm`)을 업로드합니다.
6. `수집 실행` 버튼을 누릅니다.
7. 진행 상태와 로그를 확인합니다.
8. 결과 요약과 SSID/Role 미리보기를 확인합니다.
9. 필요한 파일을 다운로드합니다.

다운로드 파일:

- `wlc_role_acl_<날짜시간_세션>.xlsx`
- `wlc_role_acl_<날짜시간_세션>_ssid_role_map.csv`
- `wlc_role_acl_<날짜시간_세션>.html`

### 4. Streamlit 사용 시 보안 주의사항

- 접속 주소를 아는 사내 사용자는 웹앱에 접근할 수 있습니다.
- 장비 계정/비밀번호는 코드에 저장하지 말고 실행 화면에서 입력하세요.
- 서버 PC에서 실제 WLC 접속이 실행되므로, 서버 PC가 WLC에 접근 가능한 네트워크에 있어야 합니다.
- 업로드한 Role 대역표와 생성된 결과 파일은 서버의 임시 작업 폴더에서 처리한 뒤 다운로드용 bytes만 세션에 보관합니다.
- 사내 Role 대역표를 업로드하고 보고서 포함 옵션을 켜면 HTML/Excel 결과에 내부 대역 정보가 들어갑니다. 회사 외부 공유 전 반드시 내용을 확인하세요.
- 인터넷 공개, 사용자별 로그인, 권한 분리, 감사 로그 보관이 필요한 환경에서는 별도 인증/프록시/접근제어 구성이 필요합니다.

## Windows GUI 실행

일반 사용자는 GUI 실행을 권장합니다.

### Release ZIP로 실행

GitHub Release에서 Windows 배포 파일을 받는 방식이 일반 사용자용 경로입니다.

1. GitHub Releases에서 아래 두 파일을 다운로드합니다.
   - `wlc-role-acl-collector_vYYYY.MM.DD-HHMMSS_windows.zip`
   - `wlc-role-acl-collector_vYYYY.MM.DD-HHMMSS_windows.zip.sha256`
2. Windows PC에서 ZIP 압축을 풉니다.
3. 압축을 푼 폴더에서 `WlcRoleAclCollectorGUI.exe`를 실행합니다.
4. CLI가 필요하면 같은 폴더의 `WlcRoleAclCollectorCLI.exe`를 사용합니다.

Release ZIP 안에는 아래 파일이 포함됩니다.

- `WlcRoleAclCollectorGUI.exe`
- `WlcRoleAclCollectorCLI.exe`
- `USER_GUIDE_KO.md`, `USER_GUIDE_KO.html`
- `DEVELOPER_GUIDE_KO.md`, `DEVELOPER_GUIDE_KO.html`
- `ERROR_CODES_KO.md`, `ERROR_CODES_KO.html`
- `DIAGNOSTIC_MODE_KO.md`, `DIAGNOSTIC_MODE_KO.html`
- `SECURITY_MODEL_KO.md`, `SECURITY_MODEL_KO.html`
- `config\role_networks.example.xlsx`
- `config\mock_scenarios\*.json`

ZIP 파일과 `.sha256` 파일은 배포용 산출물입니다. 저장소에 커밋하지 않습니다.

### Python 소스에서 실행

개발 PC에서 소스 코드로 실행하려면 Python 3.11 이상이 필요합니다.

```powershell
cd "D:\Codex Project\Network\wlc_role_acl_collector"
python -m pip install -e .
python -m wlc_role_acl_collector.gui_app
```

GUI 입력 항목:

- WLC IP
- Report name: 선택 사항입니다. 비워두면 `wlc-장비IP` 형태로 자동 지정됩니다.
- Protocol: `ssh` 또는 `telnet`
- Port: SSH는 `22`, Telnet은 `23` 자동 기본값
- Username
- Password, Enable password
- Output 폴더
- 고급 옵션의 사내 Role 대역표: 선택 사항입니다. `Role 이름`, `네트워크 대역` 컬럼을 가진 Excel 파일을 넣으면 내부용 HTML/Excel 보고서에 로컬 기준 Role 대역과 WLC 추정값 비교 결과가 표시됩니다. CIDR(`10.40.1.0/24`) 입력을 권장하며, CIDR을 쓰지 않을 때만 `서브넷마스크` 컬럼이 필요합니다.
- 고급 옵션의 Timeout seconds

사내 Role 대역표는 실제 Excel 통합 문서 형식(`.xlsx` 또는 `.xlsm`)이어야 합니다. CSV, HTML, 구형 `.xls` 파일의 확장자만 `.xlsx`로 바꾸면 열 수 없습니다. GUI의 `작성법` 버튼에서 앱 내부 작성 가이드를 볼 수 있고, `샘플 열기` 버튼으로 제공된 `config\role_networks.example.xlsx`를 열 수 있습니다. 샘플 파일의 `Role_Networks` 시트를 복사/수정해서 사용하고, `작성가이드` 시트에서 예시와 주의사항을 확인하세요. 프로그램은 `Role_Networks` Sheet가 있으면 Sheet 순서와 관계없이 그 Sheet를 우선 읽고, 없을 때만 첫 번째 Sheet를 읽으며 화면에 fallback 안내를 표시합니다.

기본 화면은 `접속 정보 입력 → 수집 시작 → 결과 확인` 순서입니다. 사내 Role 대역표, Timeout seconds, 안전 진단은 `고급 옵션 표시`를 눌렀을 때 나타납니다.

`수집 시작`을 누르면 WLC 접속부터 명령 수집, 보고서 생성까지 순서대로 진행합니다. 완료 후에는 `HTML 보고서 열기`를 먼저 확인하고, 필요할 때 `Excel 열기` 또는 `결과 폴더 열기`를 사용합니다. 접속에 실패하면 오류창에 원인이 표시되며, `수집 로그 표시`를 눌러 현재 실행 중인 명령, Role 진행 번호, 실패 명령을 확인할 수 있습니다.

ACL에 `alias <이름>`이 있으면 자동으로 `show netdestination <이름>`을 실행합니다. 보고서의 `Role_ACL_Detail`에는 source/destination 상세가 붙고, `Alias_Detail` 시트에는 alias 내부 host/network/range/name 목록이 정리됩니다.

기본 결과 저장 위치:

```text
%USERPROFILE%\Documents\WlcRoleAclCollector\outputs
```

실패해도 결과 폴더에 아래 파일이 남습니다.

- `run.log`
- `raw\<controller>.txt`

## 실패 진단

- `Authentication failed`: ID/PW 오류, 계정 잠금, WLC 로그인 권한을 확인합니다.
- `Connection timed out or was refused`: IP, SSH/Telnet 포트, 방화벽, WLC SSH/Telnet 활성화 여부를 확인합니다.
- `Command failed after login`: 로그인은 되었지만 `show configuration effective` 또는 Role별 명령 권한/지원 여부를 확인합니다.

실패 메시지에는 가능한 경우 실패 명령 ID, 실제 명령어, `run.log` 경로가 함께 표시됩니다.

## Windows EXE 만들기

Python이 없는 사용자에게 배포할 때 Windows 단일 EXE와 ZIP을 생성합니다.

이 작업은 Windows PC 또는 GitHub Actions의 `windows-latest` runner에서 검증합니다. macOS 개발 PC에서는 소스 코드 수정, 테스트, 문서 검증을 수행하고, Windows EXE 최종 검증은 GitHub Actions 또는 Windows PC에서 확인합니다.

```powershell
cd "D:\Codex Project\Network\wlc_role_acl_collector"
.\build_windows_gui_exe.ps1
```

결과:

- `dist\WlcRoleAclCollectorGUI.exe`
- `dist\WlcRoleAclCollectorCLI.exe`
- `dist\WlcRoleAclCollectorGUI_v0.1.0.zip`

로컬 빌드 ZIP에는 GUI/CLI exe, 한국어 문서, `config\role_networks.example.xlsx`, `config\mock_scenarios`가 포함됩니다. GitHub Release에서는 이 ZIP을 아래 이름으로 복사하고 SHA256 파일을 함께 업로드합니다.

```text
wlc-role-acl-collector_vYYYY.MM.DD-HHMMSS_windows.zip
wlc-role-acl-collector_vYYYY.MM.DD-HHMMSS_windows.zip.sha256
```

배포 ZIP 구조와 checksum은 다음 스크립트로 검증합니다.

```powershell
python .\tools\verify_release_package.py --dist .\dist --smoke-cli
```

`--smoke-cli`는 Windows에서 ZIP을 풀고 `WlcRoleAclCollectorCLI.exe --help`를 실행합니다. Windows가 아닌 환경에서는 CLI smoke 실행을 건너뛰고 ZIP 구조 검증만 수행합니다.

## GitHub Release 자동 배포

- PR 단계: `pull_request` to `main`에서 테스트, Windows 빌드, ZIP 구조 검증을 수행합니다. Release는 만들지 않습니다.
- main push 단계: `push` to `main`에서 테스트, Windows 빌드, ZIP 검증, SHA256 생성, KST 기준 tag 생성, 공개 GitHub Release 생성을 수행합니다.
- 자동 tag 형식은 `vYYYY.MM.DD-HHMMSS`입니다. 같은 초에 tag가 이미 있으면 suffix를 붙입니다.
- Release title은 `wlc-role-acl-collector <tag>` 형식입니다.
- Release notes는 GitHub Actions에서 한국어로 생성되며 변경 커밋, 기준 SHA, 브랜치명, 검증 명령, 산출물 파일명, SHA256 checksum을 포함합니다.

Release 준비 전에 `README.md`, `RELEASE_NOTES.md`, `CHANGELOG.md`를 함께 확인합니다. 실제 코드에 없는 기능, 내부 IP, 장비명, 계정, 비밀번호, 실제 로그, 고객 정보는 문서에 넣지 않습니다.

## CLI 실행

GUI가 기본 사용 방식이지만 CLI도 사용할 수 있습니다.

```powershell
python -m wlc_role_acl_collector collect
```

로컬 Role 대역 Excel을 함께 사용할 때:

```powershell
python -m wlc_role_acl_collector collect --role-networks config\role_networks.example.xlsx
```

입력 예시:

```text
WLC IP: 10.10.10.10
Report name [wlc-10.10.10.10]:
Protocol [ssh/telnet] (default: ssh):
Port [22]:
Username: admin
Password:
Enable password (optional):
Add another controller? [y/N]:
```

결과는 `outputs\<timestamp>\` 아래에 생성됩니다.

- `ssid_role_acl_report.xlsx`
- `ssid_role_acl_report.html`
- `raw\<controller>.txt`

## 수집 명령

장비에서 아래 명령을 실행합니다.

- `no paging`
- `show clock`
- `show version`
- `show configuration effective`
- `show ip interface brief`
- `show user-table`
- ACL에서 참조한 alias별 `show netdestination <alias>`
- 추출된 Role별 `show rights <role>`

`no paging`, `show clock`, `show version` 실패는 로그에 기록하고 계속 진행합니다. `show configuration effective` 출력이 없으면 보고서를 만들 수 없어 실패 처리합니다. Role별 `show rights <role>` 실패는 해당 Role만 실패로 기록하고 나머지 보고서 생성을 계속합니다.

`show user-table` 출력은 Role별 현재 접속자 수와 관측 대역 요약에만 사용하며, raw 결과 파일에는 원문 사용자 정보가 저장되지 않습니다. Excel에는 `Role_Network_Context` 시트가 추가되어 Role, Effective VLAN, 사용자 대역, 근거, 관측 사용자 수를 확인할 수 있습니다.

## Role 대역 해석

`Role_Network_Context`와 `SSID_Role_Map`에는 설정 기반 대역과 현재 접속자 관측값을 구분하기 위한 컬럼이 포함됩니다.

- `network_confidence`: `Exact`는 Role에 `user-role vlan`이 직접 설정된 경우입니다. `Inherited`는 Virtual AP VLAN을 상속한 경우입니다. `Dynamic Possible`은 AAA/RADIUS/ClearPass/user-derivation으로 실제 Role/VLAN이 동적으로 바뀔 수 있는 경우입니다. `Unknown`은 설정에서 VLAN 경로를 찾지 못한 경우입니다.
- `configured_vlan` / `configured_subnet`: 컨트롤러 설정 또는 `show ip interface brief`에서 확인한 VLAN과 subnet입니다.
- `observed_user_count`, `observed_vlans`, `observed_networks`: `show user-table`에서 현재 관측된 접속자 요약입니다. 참고 근거일 뿐 Role의 공식 subnet으로 단정하지 않습니다.

ACL의 Source/Destination 값이 `user`인 경우는 해당 Role을 받은 현재 사용자 IP를 의미합니다. `any`(`0.0.0.0/0`)와 다르며, `user` 표기만으로 Role의 subnet을 알 수는 없습니다.

HTML 보고서의 ACL 주석은 입력 즉시 브라우저 `localStorage`에 임시 저장됩니다. `주석 포함 HTML 저장`을 누르면 최신 주석이 포함된 독립 HTML 파일을 저장합니다. `PDF 저장/인쇄`는 브라우저 인쇄 기능을 사용하며, PDF에서는 HTML처럼 접기/펼치기 같은 인터랙션이 유지되지 않습니다.

## HTML Access Check

생성된 HTML 보고서 하단의 `Access Check` 영역에서 Role, Source IP, Destination IP, Service를 입력하면 해당 Role에 연결된 ACL을 위에서부터 검사해 첫 번째 매칭 룰 기준으로 결과를 표시합니다. 장비에 다시 접속하지 않고 보고서 안에 포함된 ACL/Alias 데이터를 사용합니다.

- `허용(Allowed)`: `permit` 룰에 매칭된 경우입니다.
- `차단(Blocked)`: `deny` 룰에 매칭된 경우입니다.
- `NAT/특수 Action 허용`: `src-nat`, `dst-nat`, `redirect`, `route`, `tunnel`, `forward` 같은 액션에 매칭된 경우입니다.
- `기본 차단(Implicit deny)`: Source/Destination/Service 기준으로 매칭되는 룰이 없는 경우입니다.
- `조건부`: Service를 선택하지 않았고, 매칭된 ACL 룰이 `any`가 아닌 특정 service에 제한된 경우입니다. 정확한 판정에는 Service 선택이 필요합니다.

Service 판정은 현재 ACL에 수집된 service token 기준입니다. 예를 들어 `svc-dns`, `svc-http`, `svc-https`, `any` 같은 값을 비교합니다. TCP/UDP 포트 번호를 직접 입력해 service object까지 정밀 해석하는 기능은 아직 포함하지 않습니다.

보안모드에서는 Access Check 조회 이력을 기본 저장하지 않습니다. 내부 보관용으로 이력 저장을 별도 활성화한 HTML은 Role, Source IP, Destination IP, Service, 판정 결과, 매칭 ACL 룰이 남을 수 있으므로 외부 공유 전 내용을 확인해야 합니다.

## 로컬 검증과 Git 기록

이 프로젝트는 GitHub 원격 저장소 없이 로컬 git만으로도 롤백 지점을 관리할 수 있습니다. 현재 상태 확인과 최근 커밋 확인은 다음 명령을 사용합니다.

```powershell
git status --short --branch
git log --oneline -n 5
```

테스트와 기본 정적 검증은 로컬 PowerShell 스크립트로 실행합니다.

```powershell
.\tools\validate.ps1
```

Streamlit 전환 관련 로컬 검증은 실제 WLC 접속 없이 fixture/offline 테스트로 확인합니다.

```powershell
python -m pytest tests\test_web_logic.py tests\test_tooling.py -q
python -m compileall -q app.py src tests tools
```

브라우저 수동 확인 절차:

1. `streamlit run app.py`를 실행합니다.
2. 브라우저에 표시된 로컬 주소로 접속합니다.
3. 입력 폼, Role 대역 Excel 업로드 영역, `수집 실행` 버튼, 진행 상태 영역, 결과 요약/미리보기 영역이 표시되는지 확인합니다.
4. 실제 WLC 검증은 서버 PC가 사내망에서 장비에 접근 가능한 환경일 때만 수행합니다.

## Secure Role Network Handling

Role network Excel files are treated as internal-only data. GUI and CLI behavior differ intentionally:

- In the GUI, selecting the internal Role network workbook creates an internal-only HTML/Excel report that includes local Role networks and WLC comparison status.
- In the CLI, local Role network values are not exported unless `--export-local-role-networks` is explicitly enabled.
- The generated HTML Access Check does not persist lookup history by default.
- Run logs record only the number of loaded Role network rows, not the Excel file path or subnet values.
- `outputs/`, `config/private/`, and local sensitive workbook/report name patterns are ignored by local git.

For CLI-created internal-only reports, use the explicit opt-in:

```powershell
python -m wlc_role_acl_collector collect --role-networks config\role_networks.example.xlsx --export-local-role-networks
```

Do not use the export option for files that may leave the company network.

검증 스크립트는 `pytest`, Python `compileall`, HTML Access Check JavaScript 문법 검사를 순서대로 실행합니다. Node.js가 설치되어 있지 않으면 JavaScript 문법 검사는 건너뛰고 경고만 표시합니다.

직전 로컬 커밋으로 되돌릴 필요가 있을 때는 먼저 `git log --oneline`으로 대상 커밋을 확인하십시오. 작업 중인 변경을 보존해야 하면 `git diff`나 별도 백업을 먼저 확인한 뒤 롤백 방식을 결정하는 것이 안전합니다.
