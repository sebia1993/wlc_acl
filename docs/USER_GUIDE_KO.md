# WLC Role ACL Collector 사용자 설명서

## 1. 이 프로그램의 목적

이 프로그램은 Aruba AOS8 무선랜 컨트롤러에 접속해서 다음 정보를 수집하고 HTML/Excel 보고서로 정리합니다.

- 어떤 SSID 사용자가 어떤 Role을 받는지
- Role에 어떤 ACL이 적용되어 있는지
- ACL의 Source, Destination, Service, Action이 무엇인지
- Alias가 있으면 해당 Alias 안에 어떤 host, network, range가 있는지
- 특정 Role에서 출발지 IP와 목적지 IP를 입력했을 때 ACL 기준으로 허용/차단되는지

## 2. 기본 보안 정책

현재 프로그램은 보안모드가 기본값입니다.

- 장비 IP, ID, Password는 프로그램 실행 시 직접 입력합니다.
- Role network Excel은 선택해도 기본 보고서에 저장되지 않습니다.
- Role network Excel의 파일 경로나 내부 대역 값은 run.log에 남기지 않습니다.
- HTML Access Check 조회 이력은 기본 저장하지 않습니다.
- 생성된 보고서에는 WLC에서 수집한 ACL, Alias, 설정 정보가 포함될 수 있으므로 외부 공유 전 반드시 내용을 확인해야 합니다.

## 3. 실행 전 준비 사항

다음 정보가 필요합니다.

- WLC IP
- Username
- Password
- Enable password가 필요한 환경이면 Enable password
- 접속 방식: 기본 SSH, 필요 시 Telnet
- 결과 저장 폴더
- 선택 사항: 사내에서만 사용하는 Role network Excel

장비 접속 대상 주의:

- 이 프로그램은 Mobility Master(MM)가 아니라 실제 WLC 컨트롤러에 접속해야 합니다.
- MM IP를 입력하면 Role/ACL 수집 결과가 누락되거나 장비 명령 결과가 예상과 다를 수 있습니다.

Role network Excel을 사용할 경우 첫 번째 시트에 아래 컬럼이 있어야 합니다.

| 컬럼 | 예시 |
| --- | --- |
| Role 이름 | corp-employee |
| 네트워크 대역 | 10.10.10.0 |
| 서브넷마스크 | 255.255.255.0 |

Excel 파일은 실제 `.xlsx` 또는 `.xlsm` 형식이어야 합니다. CSV나 구형 `.xls` 파일의 확장자만 `.xlsx`로 바꾸면 열 수 없습니다.

## 4. Windows GUI 실행 방법

배포 ZIP을 받은 경우:

1. ZIP 파일을 사내 PC에 압축 해제합니다.
2. `WlcRoleAclCollectorGUI.exe`를 실행합니다.
3. Windows SmartScreen 경고가 나오면 회사 보안 정책에 따라 실행 여부를 확인합니다.

ZIP 안에는 설명서가 두 가지 형식으로 포함됩니다.

- `USER_GUIDE_KO.html`: 브라우저로 바로 열어 보기 좋은 사용자 설명서
- `USER_GUIDE_KO.md`: Markdown 원본 설명서
- `DEVELOPER_GUIDE_KO.html`: 브라우저로 바로 열어 보기 좋은 개발자 설명서
- `DEVELOPER_GUIDE_KO.md`: Markdown 원본 개발자 설명서

소스 코드 상태에서 실행하는 경우:

```powershell
cd "D:\Codex Project\Network\wlc_role_acl_collector"
python -m pip install -e .
python -m wlc_role_acl_collector.gui_app
```

## 5. GUI 입력 항목 설명

GUI는 정책 운영형 콘솔 구조입니다.

- 왼쪽: WLC 접속 정보, 로그인 정보, 결과 저장 위치, 선택 옵션 입력
- 오른쪽 위: 현재 수집 상태와 단계 표시
- 오른쪽 아래: 접속, 명령 실행, 보고서 생성 로그 확인
- 상단 배지: 보안모드, 읽기 전용 수집, AOS8 WLC 대상 표시

| 항목 | 설명 |
| --- | --- |
| WLC IP | 접속할 실제 WLC 컨트롤러 IP. MM이 아님 |
| Report name (optional) | 보고서에 표시할 이름. 비워두면 `wlc-장비IP` 형태로 자동 지정 |
| Protocol | 기본 `ssh`, 필요 시 `telnet` 선택 |
| Port | SSH는 기본 22, Telnet은 기본 23 |
| Username | WLC 로그인 계정 |
| Password | WLC 로그인 비밀번호 |
| Enable password | enable 권한 진입이 필요한 경우 입력 |
| Output | 결과 파일을 저장할 폴더 |
| Role network Excel (session only) | 선택 사항. 실행 중에만 읽고 기본 보고서에는 저장하지 않음 |
| Timeout seconds | 명령어 응답 대기 시간. 장비가 느리면 90초 이상으로 증가 |

입력이 끝나면 `수집 시작` 버튼을 누릅니다.

다중 모니터 사용 시 참고:

- 프로그램 창은 현재 모니터의 작업영역 안에 들어오도록 자동 보정됩니다.
- 모니터마다 배율이나 해상도가 달라도 창이 너무 크게 남아 하단 버튼이 잘리는 일을 줄이도록 설계되어 있습니다.
- 작은 모니터에서는 좌측 입력 영역을 스크롤해서 볼 수 있습니다.

## 6. 수집 후 생성되는 파일

결과는 기본적으로 아래 위치에 생성됩니다.

```text
%USERPROFILE%\Documents\WlcRoleAclCollector\outputs\<실행시각>\
```

주요 파일:

| 파일 | 설명 |
| --- | --- |
| `ssid_role_acl_report.html` | 운영자가 보기 쉬운 HTML 보고서 |
| `ssid_role_acl_report.xlsx` | Excel 보고서 |
| `run.log` | 실행 과정과 오류 원인 로그 |
| `raw\<controller>.txt` | 수집한 원본 명령 결과 일부 |

주의: `show user-table` 원문은 개인정보 노출을 줄이기 위해 raw 파일에 그대로 저장하지 않습니다. 다만 ACL, Alias, WLC 설정에는 내부 IP나 정책명이 포함될 수 있습니다.

## 7. HTML 보고서 보는 방법

HTML 파일을 브라우저로 열면 Role별 ACL을 확인할 수 있습니다.

- 상단 Role 버튼을 클릭하면 해당 Role의 ACL 목록이 보입니다.
- 사용자가 많은 Role이 앞쪽에 배치됩니다.
- 사용자가 0명인 Role은 기본 숨김 처리될 수 있으며, 필요 시 `Show zero-user roles`로 표시합니다.
- Role 이름과 관련 없는 ACL은 기본 숨김 처리되며, 필요 시 `Show other ACLs`로 표시합니다.
- Raw 컬럼은 기본 숨김이며, 필요 시 `Raw 보기` 버튼으로 표시합니다.
- Source 또는 Destination에 `alias 이름`이 있으면 alias 버튼을 클릭해 상세 host, network, range를 확인합니다.

## 8. ACL 주석 기능

ACL 행마다 Comment 입력란이 있습니다.

- 입력한 주석은 브라우저에 임시 저장됩니다.
- `주석 포함 HTML 저장` 버튼을 누르면 현재 주석이 포함된 별도 HTML 파일을 저장할 수 있습니다.
- PDF로 저장하려면 `PDF 저장/인쇄` 버튼을 누르고 브라우저 인쇄 화면에서 PDF 저장을 선택합니다.
- PDF는 정적인 문서이므로 HTML처럼 클릭, 접기, 펼치기 기능은 유지되지 않습니다.

## 9. Access Check 사용 방법

HTML 보고서의 Access Check 영역에서 특정 Role 기준 허용/차단 여부를 확인할 수 있습니다.

Role ACL Detail에서 Role 버튼을 클릭하면 Access Check의 Role 선택값도 같은 Role로 자동 변경됩니다. Role별 ACL을 보면서 바로 출발지/목적지 IP 검사를 이어갈 때 사용합니다.

입력 항목:

| 항목 | 설명 |
| --- | --- |
| Role | 확인할 사용자 Role |
| Source IP | 사용자 또는 단말의 출발지 IP |
| Destination IP | 접근하려는 목적지 IP |
| Service | 선택 사항. ACL service와 비교할 값 |

결과 의미:

| 결과 | 의미 |
| --- | --- |
| Allowed | permit ACL에 매칭됨 |
| Blocked | deny ACL에 매칭됨 |
| Allowed with NAT/Special Action | src-nat, dst-nat, redirect, route, tunnel, forward 같은 특수 action에 매칭됨 |
| Implicit deny | 매칭되는 ACL이 없어 기본 차단으로 판단 |
| Conditional | Service를 선택하지 않아 정확한 판정에 추가 확인이 필요 |

중요한 제한:

- Access Check는 보고서 안에 포함된 ACL/Alias 데이터를 기준으로 판단합니다.
- Service object의 실제 TCP/UDP 포트까지 세부 해석하는 기능은 아직 포함되어 있지 않습니다.
- 보안모드에서는 Access Check 이력이 HTML이나 브라우저 저장소에 기본 저장되지 않습니다.
- 보안모드에서는 Role network Excel의 로컬 대역이 HTML에 포함되지 않으므로, HTML 단독으로는 “Source IP가 해당 Role 대역에 속하는지”까지 검증하지 않습니다.

## 10. Role network Excel 사용 방식

Role network Excel은 사내망에서만 선택하는 보조 파일입니다.

기본 동작:

- 프로그램 실행 중에만 읽습니다.
- HTML/Excel 보고서에는 저장하지 않습니다.
- run.log에 파일 경로나 대역 값을 남기지 않습니다.

CLI에서 내부 보관용 보고서에 Role network를 반드시 포함해야 하는 경우에만 아래 옵션을 사용합니다.

```powershell
python -m wlc_role_acl_collector collect --role-networks config\role_networks.example.xlsx --export-local-role-networks
```

이 옵션을 사용한 보고서는 내부 네트워크 대역이 포함될 수 있으므로 외부 반출 금지 대상으로 취급해야 합니다.

## 11. 자주 발생하는 오류

| 오류 | 확인할 내용 |
| --- | --- |
| Authentication failed | ID/PW, 계정 잠금, WLC 로그인 권한 확인 |
| Connection timed out or was refused | IP, 방화벽, SSH/Telnet 활성화, 포트 확인 |
| Command failed after login | 로그인은 됐지만 `show configuration effective` 또는 `show rights` 권한/응답 문제 확인 |
| Unable to open Role network Excel file: File is not a zip file | 실제 Excel `.xlsx`가 아니라 CSV/HTML/구형 XLS를 확장자만 바꾼 파일인지 확인 |
| 보고서에 Role이 부족함 | 해당 Role의 `show rights <role>` 명령 권한 또는 수집 로그 확인 |
| Access Check 결과가 예상과 다름 | Service 선택 여부, Alias 상세 수집 여부, 숨겨진 other ACL 표시 여부 확인 |

## 12. 산출물 취급 주의

다음 파일은 내부 정보가 포함될 수 있습니다.

- `ssid_role_acl_report.html`
- `ssid_role_acl_report.xlsx`
- `run.log`
- `raw\<controller>.txt`
- Role network Excel

외부 공유 전에는 ACL, Alias, Controller 이름, 내부 IP, 정책명, 주석 내용을 반드시 확인하십시오.

## 13. 문제가 생겼을 때 전달하면 좋은 정보

개발자나 담당자에게 문의할 때는 아래 정보를 전달하면 원인 확인이 빠릅니다.

- 프로그램 실행 시각
- WLC IP 또는 Report name
- 오류 메시지 전체
- `run.log`
- 어느 단계에서 멈췄는지: 접속, 명령 수집, 보고서 생성, HTML 확인

비밀번호와 Role network Excel 원본은 전달하지 마십시오.
