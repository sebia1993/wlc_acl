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
- GUI에서 사내 Role 대역표를 선택하면 내부용 보고서에 실제 Role 대역과 WLC 비교 상태가 표시됩니다.
- Role 대역표의 전체 파일 경로나 내부 대역 값은 run.log에 남기지 않습니다.
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
- 선택 사항: 사내에서만 사용하는 Role 대역표 Excel

장비 접속 대상 주의:

- 이 프로그램은 Mobility Master(MM)가 아니라 실제 WLC 컨트롤러에 접속해야 합니다.
- MM IP를 입력하면 Role/ACL 수집 결과가 누락되거나 장비 명령 결과가 예상과 다를 수 있습니다.

사내 Role 대역표를 사용할 경우 `Role_Networks` Sheet에 아래 컬럼이 있어야 합니다. 프로그램은 `Role_Networks` Sheet가 있으면 Sheet 순서와 관계없이 그 Sheet를 우선 읽습니다. `Role_Networks` Sheet가 없을 때만 기존 호환성을 위해 첫 번째 Sheet를 읽고 화면에 fallback 안내를 표시합니다. `네트워크 대역`은 CIDR 형식(`10.40.1.0/24`)을 권장합니다.

| 컬럼 | 예시 |
| --- | --- |
| Role 이름 | corp-employee |
| 네트워크 대역 | 10.40.1.0/24 |
| 서브넷마스크 | 255.255.255.0 |
| 설명 | 본사 임직원 무선 |
| 소유부서 | 네트워크팀 |
| 비고 | 내부용 |
| 마지막 확인일 | 2026-06-29 |

`서브넷마스크`는 CIDR을 쓰지 않고 `10.40.1.0`처럼 네트워크 주소만 입력할 때 필요합니다. `설명`, `소유부서`, `비고`, `마지막 확인일`은 관리용 선택 컬럼이며 보고서 매칭에는 사용하지 않습니다.

Excel 파일은 실제 `.xlsx` 또는 `.xlsm` 형식이어야 합니다. CSV나 구형 `.xls` 파일의 확장자만 `.xlsx`로 바꾸면 열 수 없습니다.

GUI의 `작성법` 버튼을 누르면 앱 내부 팝업으로 작성 규칙과 예시를 확인할 수 있습니다. `샘플 열기` 버튼을 누르면 제공된 `config\role_networks.example.xlsx`가 열립니다. 샘플 파일에는 실제 입력용 `Role_Networks` 시트와 설명용 `작성가이드` 시트가 있습니다. `작성가이드` 같은 안내 Sheet가 첫 번째에 있어도 `Role_Networks` Sheet가 있으면 안내 Sheet는 읽지 않습니다.

## 4. Windows GUI 실행 방법

배포 ZIP을 받은 경우:

1. ZIP 파일을 사내 PC에 압축 해제합니다.
2. `WlcRoleAclCollectorGUI.exe`를 실행합니다.
3. Windows SmartScreen 경고가 나오면 회사 보안 정책에 따라 실행 여부를 확인합니다.

ZIP에는 GUI 실행 파일과 콘솔 실행 파일이 함께 포함됩니다.

- `WlcRoleAclCollectorGUI.exe`: 일반 수집과 안전 진단을 실행하는 Windows 화면
- `WlcRoleAclCollectorCLI.exe`: 자동화 진단과 mock 서버 실행용 콘솔 도구

ZIP 안에는 설명서가 두 가지 형식으로 포함됩니다.

- `USER_GUIDE_KO.html`: 브라우저로 바로 열어 보기 좋은 사용자 설명서
- `USER_GUIDE_KO.md`: Markdown 원본 설명서
- `DEVELOPER_GUIDE_KO.html`: 브라우저로 바로 열어 보기 좋은 개발자 설명서
- `DEVELOPER_GUIDE_KO.md`: Markdown 원본 개발자 설명서
- `ERROR_CODES_KO.html` / `ERROR_CODES_KO.md`: 외부 공유 가능한 오류 코드 설명
- `DIAGNOSTIC_MODE_KO.html` / `DIAGNOSTIC_MODE_KO.md`: 원본 로그 없는 현장 진단 모드 설명
- `SECURITY_MODEL_KO.html` / `SECURITY_MODEL_KO.md`: 민감정보 저장/마스킹 기준

소스 코드 상태에서 실행하는 경우:

```powershell
cd "D:\Codex Project\Network\wlc_role_acl_collector"
python -m pip install -e .
python -m wlc_role_acl_collector.gui_app
```

## 5. GUI 입력 항목 설명

GUI의 기본 흐름은 `접속 정보 입력 → 수집 시작 → 결과 확인`입니다.

- 왼쪽: WLC 접속 정보, 인증 정보, 결과 저장 위치 입력
- 오른쪽 위: 현재 수집 상태, 단계, `수집 시작`, 결과 열기 버튼 표시
- 고급 옵션: 사내 Role 대역표, Timeout seconds, 안전 진단
- 수집 로그: 기본 숨김이며 필요할 때 `수집 로그 표시`로 확인
- 상단 배지: 보안모드, 읽기 전용 수집, AOS8 WLC 대상 표시

| 항목 | 설명 |
| --- | --- |
| WLC IP | 접속할 실제 WLC 컨트롤러 IP. MM이 아님 |
| 보고서 이름(선택) | 보고서에 표시할 이름. 비워두면 `wlc-장비IP` 형태로 자동 지정 |
| Protocol | 기본 `ssh`, 필요 시 `telnet` 선택 |
| Port | SSH는 기본 22, Telnet은 기본 23 |
| Username | WLC 로그인 계정 |
| Password | WLC 로그인 비밀번호 |
| Enable password | enable 권한 진입이 필요한 경우 입력 |
| Output | 결과 파일을 저장할 폴더 |

아래 항목은 `고급 옵션 표시`를 눌렀을 때 나타납니다.

| 항목 | 설명 |
| --- | --- |
| 사내 Role 대역표 | 선택 사항. 선택하면 내부용 HTML/Excel 보고서에 실제 Role 대역과 WLC 비교 상태 표시 |
| Timeout seconds | 명령어 응답 대기 시간. 장비가 느리면 90초 이상으로 증가 |
| 안전 진단 | 원본 장비 출력 없이 접속/명령 단계와 오류 코드만 확인 |

`사내 Role 대역표` 영역에는 세 가지 버튼이 있습니다.

| 버튼 | 설명 |
| --- | --- |
| 파일 선택 | 실제 사내 Role 대역표 Excel을 선택하고 즉시 검증 |
| 작성법 | 앱 내부 팝업으로 필수 컬럼, CIDR 예시, 오류 방지법 확인 |
| 샘플 열기 | 제공된 `role_networks.example.xlsx` 템플릿 열기 |

입력이 끝나면 `수집 시작` 버튼을 누릅니다.

수집이 완료되면 `HTML 보고서 열기` 버튼을 먼저 눌러 결과를 확인합니다. Excel 원본 표가 필요하면 `Excel 열기`, 실행 폴더나 run.log가 필요하면 `결과 폴더 열기`를 사용합니다.

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

- 첫 화면의 `결론 요약`에서 확인 필요 건수, Unresolved, 동적 Role 가능성, 사내 Role 대역 비교 상태를 먼저 확인합니다.
- `Role ACL Detail`에서 실제 ACL 행을 확인합니다.
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

HTML 보고서 하단의 Access Check 영역에서 특정 Role 기준 허용/차단 여부를 보조로 확인할 수 있습니다.

Access Check는 선택한 Role 안에서 ACL 이름이 Role 이름과 정확히 같은 ACL만 검사합니다. 예를 들어 Role이 `guest-logon`이면 ACL 이름도 정확히 `guest-logon`인 항목만 판정 대상입니다. `guest-logon-acl`처럼 비슷하지만 이름이 다른 ACL은 Role ACL Detail에는 보일 수 있지만 Access Check 판정에는 사용하지 않습니다.

Role ACL Detail에서 Role 버튼을 클릭하면 Access Check의 Role 선택값도 같은 Role로 자동 변경됩니다. Role별 ACL을 보면서 바로 출발지/목적지 IP 검사를 이어갈 때 사용합니다.

입력 항목:

| 항목 | 설명 |
| --- | --- |
| Role | 확인할 사용자 Role |
| Source IP | 사용자 또는 단말의 출발지 IP |
| Destination IP | 접근하려는 목적지 IP |
| Service | 선택 사항. 기본값은 `자동 - Source/Destination 기준`이며, Source/Destination이 맞는 ACL을 위에서 아래 순서로 찾습니다. 특정 service ACL에 매칭되면 조건부로 표시됩니다. |

결과 의미:

| 결과 | 의미 |
| --- | --- |
| 허용(Allowed) | permit ACL에 매칭됨 |
| 차단(Blocked) | deny ACL에 매칭됨 |
| NAT/특수 Action 허용 | src-nat, dst-nat, redirect, route, tunnel, forward 같은 특수 action에 매칭됨 |
| 기본 차단(Implicit deny) | 매칭되는 ACL이 없어 기본 차단으로 판단 |
| 조건부 | Service 자동 매칭 상태에서 특정 service ACL에 매칭되어 추가 확인이 필요 |
| 일치하는 Role ACL 없음 | Role 이름과 정확히 같은 ACL이 없어 Access Check로 판정할 수 없음 |

중요한 제한:

- Access Check는 보고서 안에 포함된 ACL/Alias 데이터를 기준으로 판단합니다.
- Access Check는 ACL 이름이 Role 이름과 정확히 같은 ACL만 검사합니다.
- Service를 선택하지 않으면 `자동 - Source/Destination 기준` 모드로 동작하며, ACL 표시 순서대로 첫 번째 Source/Destination 매칭 규칙을 찾습니다.
- Service 자동 매칭 결과가 `any`가 아닌 특정 service ACL이면 조건부 판정으로 표시합니다.
- Service object의 실제 TCP/UDP 포트까지 세부 해석하는 기능은 아직 포함되어 있지 않습니다.
- 보안모드에서는 Access Check 이력이 HTML이나 브라우저 저장소에 기본 저장되지 않습니다.
- 사내 Role 대역표를 선택한 내부용 보고서에서는 Source IP가 해당 Role 대역 밖인지 경고합니다. 대역표를 선택하지 않은 보고서에서는 HTML 단독으로 “Source IP가 해당 Role 대역에 속하는지”까지 검증하지 않습니다.

## 10. 사내 Role 대역표 사용 방식

사내 Role 대역표는 사내망에서만 선택하는 내부 기준 파일입니다. 프로그램 안에 저장하지 말고, 사내에서 관리하는 표준 Excel 원본을 실행할 때 선택하는 방식을 권장합니다.

GUI 기본 동작:

- 선택 즉시 Excel 형식과 대역 값을 검증합니다.
- 로드된 Role 수, 대역 수, 중복 제외 건수를 화면에 표시합니다.
- 수집 후 내부용 HTML/Excel 보고서에 실제 Role 대역과 WLC 비교 상태를 표시합니다.
- HTML 상단에 `내부망 전용 보고서` 안내가 표시됩니다.
- run.log에는 파일 경로나 대역 값을 남기지 않고 로드 행 수만 기록합니다.

샘플 Excel 구성:

| 시트 | 용도 |
| --- | --- |
| Role_Networks | 실제 프로그램이 우선 읽는 입력 시트. Sheet 순서와 관계없이 이 이름을 먼저 찾음 |
| 작성가이드 | 작성 규칙, 예시, 주의사항 안내 시트. Role_Networks Sheet가 있으면 읽지 않음 |

Sheet 선택 기준:

- `Role_Networks` Sheet가 있으면 Sheet 순서와 관계없이 그 Sheet를 우선 읽습니다.
- `Role_Networks` Sheet가 없으면 기존 호환성을 위해 첫 번째 Sheet를 읽습니다.
- fallback이 발생하면 화면 상태 메시지에 `Role_Networks Sheet가 없어 첫 번째 Sheet를 읽었다.`가 표시됩니다.

CLI는 기본적으로 대역표를 보고서에 내보내지 않습니다. CLI에서 내부 보관용 보고서에 Role network를 포함해야 하는 경우에만 아래 옵션을 사용합니다.

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

## 12. 진단 모드와 오류 코드

현장에서 문제가 발생했지만 원본 로그를 외부로 가져올 수 없는 경우 진단 모드를 사용합니다.

GUI에서 실행하는 경우:

1. `WlcRoleAclCollectorGUI.exe`를 실행합니다.
2. 평소 수집과 동일하게 `WLC IP`, `Protocol`, `Port`, `Username`, `Password`를 입력합니다.
3. `고급 옵션 표시`를 누릅니다.
4. `안전 진단` 버튼을 누릅니다.
5. 완료 후 `HTML 보고서 열기` 또는 `결과 폴더 열기`로 진단 결과를 확인합니다.

GUI 진단 모드는 수집 보고서용 raw 폴더를 만들지 않습니다. 결과 파일에는 단계, 오류 코드, command_id, 안전한 조치 안내만 포함됩니다.

CLI에서 실행하는 경우:

```powershell
WlcRoleAclCollectorCLI.exe diagnose --controllers config\controllers.example.csv --output-dir outputs
```

진단 모드는 아래 파일을 생성합니다.

- `diagnostic_summary.json`
- `diagnostic_summary.html`
- `diagnostic_run.log`

진단 파일에는 원본 장비 출력 대신 단계, 오류 코드, command_id, 안전 메시지만 저장합니다.

외부 분석 요청 시에는 먼저 아래 값만 전달합니다.

- `primary_code`
- `stage`
- `command_id`
- `raw_output_saved`

오류 코드별 의미는 `ERROR_CODES_KO.html`에서 확인합니다.

실제 장비 없이 개발 PC에서 동작 확인이 필요하면 mock 서버를 사용할 수 있습니다.

```powershell
WlcRoleAclCollectorCLI.exe mock-server --protocol telnet --scenario config\mock_scenarios\success_minimal.json
```

## 13. 산출물 취급 주의

다음 파일은 내부 정보가 포함될 수 있습니다.

- `ssid_role_acl_report.html`
- `ssid_role_acl_report.xlsx`
- `run.log`
- `raw\<controller>.txt`
- Role network Excel

외부 공유 전에는 ACL, Alias, Controller 이름, 내부 IP, 정책명, 주석 내용을 반드시 확인하십시오.

## 14. 문제가 생겼을 때 전달하면 좋은 정보

개발자나 담당자에게 문의할 때는 아래 정보를 전달하면 원인 확인이 빠릅니다.

- 프로그램 실행 시각
- WLC IP 또는 Report name
- 오류 메시지 전체
- `run.log`
- 어느 단계에서 멈췄는지: 접속, 명령 수집, 보고서 생성, HTML 확인
- 진단 모드를 실행한 경우 `primary_code`, `stage`, `command_id`

비밀번호와 Role network Excel 원본은 전달하지 마십시오.
