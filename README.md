# WLC Role ACL Collector

Aruba AOS8 WLC에 접속해 SSID별 기본 Role과 Role별 ACL 접근 범위를 수집하고, 운영자가 한눈에 볼 수 있는 Excel/HTML 보고서를 생성하는 도구입니다.

## 목적

- 어떤 SSID가 어떤 AAA Profile을 사용하는지 확인합니다.
- SSID별 기본 Role(`initial-role`, `mac-default-role`, `dot1x-default-role`)을 정리합니다.
- Role에 연결된 ACL 규칙과 접근 요약을 제공합니다.
- ACL에 `alias <이름>`이 있으면 netdestination 내용을 함께 정리합니다.
- ClearPass/RADIUS 동적 Role은 직접 수집하지 않고, 동적 Role 가능성으로 표시합니다.

## Windows GUI 실행

일반 사용자는 GUI 실행을 권장합니다.

```powershell
cd "D:\Codex Project\Network\wlc_role_acl_collector"
python -m pip install -e .
python -m wlc_role_acl_collector.gui_app
```

배포본을 사용하는 경우 아래 파일을 실행하면 됩니다.

```text
dist\WlcRoleAclCollectorGUI.exe
```

GUI 입력 항목:

- WLC IP/Hostname
- Protocol: `ssh` 또는 `telnet`
- Port: SSH는 `22`, Telnet은 `23` 자동 기본값
- Username
- Password, Enable password
- Output 폴더
- Timeout seconds

`수집 시작`을 누르면 WLC 접속부터 명령 수집, 보고서 생성까지 순서대로 진행합니다. 접속에 실패하면 Run Log와 오류창에 원인이 표시됩니다.

수집 중에는 Run Log에 현재 실행 중인 명령, Role 진행 번호, 실패 명령이 표시됩니다. 창을 줄여도 입력 영역은 스크롤되고 하단 실행/결과 버튼은 계속 보입니다.

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

Python이 없는 사용자에게 배포할 때 단일 EXE와 ZIP을 생성합니다.

```powershell
cd "D:\Codex Project\Network\wlc_role_acl_collector"
.\build_windows_gui_exe.ps1
```

결과:

- `dist\WlcRoleAclCollectorGUI.exe`
- `dist\WlcRoleAclCollectorGUI_v0.1.0.zip`

## CLI 실행

GUI가 기본 사용 방식이지만 CLI도 사용할 수 있습니다.

```powershell
python -m wlc_role_acl_collector collect
```

입력 예시:

```text
WLC IP/Hostname: 10.10.10.10
Controller name [wlc-10.10.10.10]:
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
