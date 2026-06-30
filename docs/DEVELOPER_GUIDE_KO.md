# WLC Role ACL Collector 개발자 설명서

이 문서는 초급 개발자가 프로젝트 구조와 기능을 빠르게 이해할 수 있도록 만든 개발용 문서입니다. 사용자가 프로그램을 어떻게 쓰는지는 `USER_GUIDE_KO.md`를 보고, 코드를 고치거나 기능을 추가할 때는 이 문서를 먼저 보면 됩니다.

## 1. 프로젝트가 해결하는 문제

무선랜 컨트롤러에는 SSID, AAA Profile, Role, ACL, Alias 정보가 흩어져 있습니다. 운영자가 수동으로 확인하려면 여러 명령어를 실행하고 결과를 비교해야 합니다.

이 프로그램은 그 과정을 자동화합니다.

1. WLC에 SSH 또는 Telnet으로 접속합니다.
2. 필요한 `show` 명령어를 실행합니다.
3. 수집한 텍스트를 구조화된 데이터로 파싱합니다.
4. Role별 ACL과 Alias를 HTML/Excel 보고서로 만듭니다.
5. HTML 안에서 Source IP, Destination IP를 입력해 ACL 허용/차단 여부를 확인할 수 있게 합니다.

## 2. 전체 데이터 흐름

```text
GUI/CLI 입력
  -> WLC 접속 정보 생성
  -> collector.py
  -> raw command output
  -> aos8_parser.py
  -> ParsedController dataclass
  -> report.py
  -> Excel/HTML 보고서
  -> HTML Access Check
```

핵심은 `수집`, `파싱`, `보고서 생성`을 분리해 둔 것입니다. 장비 접속 방식이 바뀌어도 파서와 보고서 코드는 최대한 영향을 적게 받아야 합니다.

## 3. 주요 기능 목록

현재 구현된 주요 기능은 다음과 같습니다.

- Windows GUI로 WLC IP, 계정, 비밀번호, 출력 폴더 입력
- SSH 기본 포트 22, Telnet 기본 포트 23 지원
- WLC 명령어 자동 수집
- Role 목록 자동 탐색 후 Role별 `show rights <role>` 실행
- ACL 안의 `alias <name>` 탐색 후 `show netdestination <name>` 실행
- SSID, AAA Profile, 기본 Role 관계 파악
- Role별 ACL 표 생성
- Alias 상세 host, network, range 표시
- Role별 사용자 수 기준 정렬
- 사용자가 0명인 Role 기본 숨김
- Role 이름과 맞지 않는 ACL 기본 숨김
- Raw ACL 컬럼 기본 숨김
- ACL 행별 Comment 입력
- Comment 포함 HTML 저장
- PDF 저장/인쇄
- HTML Access Check
- 사내 Role 대역표 선택/검증
- GUI 내부용 보고서에 Role 대역과 WLC 비교 상태 표시
- Role 대역표 작성법 앱 내부 팝업
- Role 대역표 샘플 Excel 열기
- CLI 기본 보안모드에서 Role network Excel 값과 Access Check 이력 미저장

## 4. 폴더와 파일 역할

```text
wlc_role_acl_collector/
  src/wlc_role_acl_collector/
    gui_app.py          Windows GUI 화면과 버튼 동작
    gui_support.py      GUI 입력값 검증, 기본 출력 폴더 계산
    cli.py              CLI 명령어 진입점
    collector.py        WLC 접속 및 show 명령어 실행
    aos8_parser.py      Aruba AOS8 설정/명령 출력 파싱
    acl_evaluator.py    Source/Destination/Service 기준 ACL 매칭 판단
    report.py           Excel/HTML 보고서 생성
    role_networks.py    Role network Excel 로드 및 검증
    diagnostics.py      실패 메시지 분류와 사용자용 오류 설명
    diagnostic_codes.py 안정적인 오류 코드 정의
    diagnostic_events.py 원본 없는 단계 이벤트 모델
    diagnostic_mode.py  현장 진단 모드 실행 흐름
    diagnostic_report.py 안전 진단 JSON/HTML/log 생성
    redaction.py        민감정보 자동 마스킹
    mock_server.py      로컬 SSH/Telnet mock WLC 서버
    mock_scenarios.py   mock 응답 시나리오 로더
    config.py           CSV/환경변수 기반 설정 로드
    models.py           공통 dataclass 모델
  tests/                자동 테스트
  docs/                 사용자/개발자 문서
  config/               샘플 설정 파일
  tools/validate.ps1    전체 검증 스크립트
```

## 5. 주요 모듈 설명

### `gui_app.py`

일반 사용자가 보는 Windows GUI입니다.

주요 책임:

- 입력 필드 배치
- SSH/Telnet 선택 시 기본 포트 자동 변경
- 사내 Role 대역표 선택과 사전 검증 요약 표시
- 사내 Role 대역표 작성법 팝업 표시
- 샘플 Role 대역표 Excel 열기
- 수집 시작 버튼 처리
- 안전 진단 버튼 처리
- 백그라운드 스레드에서 수집 실행
- 백그라운드 스레드에서 원본 raw 저장 없는 진단 실행
- 완료 후 HTML/Excel 열기 버튼 활성화
- 진단 완료 후 진단 HTML과 결과 폴더 열기 버튼 활성화
- 오류 발생 시 메시지 박스 표시
- 장비 접속 대상은 MM이 아니라 실제 WLC 컨트롤러라는 안내 표시
- 정책 운영형 콘솔 디자인, 상태 단계 표시, 로그 색상 태그 표시

주의할 점:

- GUI가 멈추지 않도록 수집 작업은 별도 스레드에서 실행합니다.
- 비밀번호는 파일에 저장하지 않습니다.
- 사내 Role 대역표를 선택하면 GUI 보고서는 내부용 HTML/Excel에 실제 Role 대역을 포함합니다.
- 샘플 Excel은 배포본의 실행 파일 옆 `config\role_networks.example.xlsx` 또는 소스 repo의 `config\role_networks.example.xlsx`에서 찾습니다.
- Role network Excel 전체 경로와 내부 대역은 run.log에 남기지 않습니다.
- 진단 모드는 `diagnostic_summary.json/html`, `diagnostic_run.log`만 생성하고 raw 폴더를 만들지 않습니다.
- Windows 다중 모니터와 DPI 배율 차이를 고려해 창 위치/크기를 작업영역 안으로 보정합니다.
- GUI 색상, 단계 라벨, 주요 문구는 `gui_app.py` 상단 상수에서 관리합니다.

### `collector.py`

실제 WLC에 접속하는 계층입니다.

기본 수집 명령어:

```text
no paging
show clock
show version
show configuration effective
show ip interface brief
show user-table
```

추가 수집:

- 설정에서 Role을 찾은 뒤 `show rights <role>` 실행
- ACL에서 Alias를 찾은 뒤 `show netdestination <alias>` 실행

주의할 점:

- `show configuration effective`가 실패하면 보고서 생성에 필요한 핵심 데이터가 없으므로 실패 처리합니다.
- 일부 Role이나 Alias 명령이 실패해도 가능한 범위에서 보고서를 생성합니다.

### `aos8_parser.py`

WLC 텍스트 출력을 구조화된 데이터로 바꾸는 파일입니다.

파싱 대상:

- SSID Profile
- Virtual AP
- AP Group
- AAA Profile
- Role
- ACL rule
- Netdestination Alias
- VLAN/Subnet 정보
- User table 기반 관측 사용자 수

결과는 `ParsedController`에 담깁니다.

주의할 점:

- 네트워크 장비 출력은 버전이나 설정 방식에 따라 조금씩 다를 수 있습니다.
- 파서 수정 시 반드시 fixture 기반 테스트를 추가해야 합니다.

### `models.py`

프로그램에서 공유하는 데이터 구조가 모여 있습니다.

자주 보는 모델:

- `Controller`: WLC 접속 대상
- `CommandOutput`: 명령어 하나의 실행 결과
- `CollectionResult`: 한 컨트롤러의 전체 수집 결과
- `AclRule`: ACL 한 줄
- `RolePolicy`: Role에 연결된 ACL 목록과 rule
- `NetDestinationEntry`: Alias 내부 항목
- `SsidRoleMapping`: SSID와 Role 관계
- `ParsedController`: 파싱이 끝난 전체 결과
- `RoleNetworkDefinition`: 사용자가 선택한 Role network Excel 한 행

### `report.py`

Excel과 HTML 보고서를 만드는 파일입니다. 이 프로젝트에서 가장 큰 파일입니다.

주요 책임:

- 파싱 결과를 DataFrame으로 변환
- Excel 시트 생성
- HTML 문자열 생성
- Role 탭, ACL 표, Alias 상세, Comment UI 생성
- Access Check에 필요한 JSON 생성
- Role 탭 선택과 Access Check Role 선택값 동기화
- 보안모드에서 민감 데이터 export 차단

중요한 보안 기본값:

```python
export_local_role_networks=False
access_history_enabled=False
```

CLI는 이 기본값을 유지하므로 Role network Excel을 선택해도 `--export-local-role-networks`를 명시하지 않으면 내부 대역이 저장되지 않습니다. GUI는 사내 Role 대역표를 선택한 실행을 내부용 보고서 생성으로 간주해 `export_local_role_networks=True`로 보고서를 만듭니다.

### `acl_evaluator.py`

HTML Access Check의 판단 로직을 준비하는 파일입니다.

Access Check 대상 ACL:

- ACL 이름이 선택한 Role 이름과 정확히 같은 row만 판정 데이터에 포함합니다.
- 비교는 앞뒤 공백 제거 후 대소문자 무시 방식으로 수행합니다.
- `guest-logon` Role 기준 `guest-logon-acl`처럼 이름이 비슷하지만 정확히 같지 않은 ACL은 제외합니다.
- 대상 ACL이 없으면 `일치하는 Role ACL 없음` 상태를 표시합니다.

지원하는 Source/Destination 형태:

- `any`
- `user`
- `host 10.1.1.1`
- `network 10.1.1.0 255.255.255.0`
- `range 10.1.1.10 10.1.1.20`
- `alias 이름`

Service 미선택 동작:

- Source/Destination이 맞는 첫 ACL을 위에서 아래 순서로 자동 매칭합니다.
- 매칭된 ACL의 service가 `any`이면 확정 판정으로 표시합니다.
- 매칭된 ACL의 service가 `any`가 아니면 `조건부`로 표시합니다.

판정 결과:

- `허용(Allowed)`
- `차단(Blocked)`
- `NAT/특수 Action 허용`
- `기본 차단(Implicit deny)`
- `조건부`

주의할 점:

- Service object의 실제 TCP/UDP 포트까지 완전 해석하지는 않습니다.
- Alias가 IP 범위로 해석되지 않으면 warning을 표시합니다.

### `role_networks.py`

사용자가 선택한 Role network Excel을 읽고 검증합니다.

프로그램은 `Role_Networks` Sheet가 있으면 Sheet 순서와 관계없이 그 Sheet를 우선 읽습니다. `Role_Networks` Sheet가 없을 때만 기존 호환성을 위해 첫 번째 Sheet를 fallback으로 읽습니다. fallback이 발생하면 `RoleNetworkLoadSummary.sheet_fallback_used`가 `True`가 되고, `sheet_notice`에 `Role_Networks Sheet가 없어 첫 번째 Sheet를 읽었다.`가 들어가 GUI 상태 메시지에 표시됩니다. 샘플 Excel에는 `Role_Networks` 입력 시트와 `작성가이드` 설명 시트가 있으며, `Role_Networks` Sheet가 있으면 설명 시트는 파싱 결과에 영향을 주지 않습니다.

기본 정책:

- `.xlsx`, `.xlsm`만 허용
- Excel 임시 잠금 파일 `~$...xlsx` 거부
- CSV나 HTML 파일을 확장자만 `.xlsx`로 바꾼 경우 거부
- Role, network, subnet mask 컬럼 검사
- CIDR 형태로 정규화

이 데이터는 민감 정보로 취급합니다.

### `diagnostics.py`

사용자에게 보여줄 오류 메시지를 정리합니다.

예:

- 인증 실패
- 접속 timeout
- 로그인 후 명령 실패
- 알 수 없는 실패

오류 메시지를 개선하고 싶으면 이 파일을 보면 됩니다.

### 진단 모드 관련 파일

진단 모드는 실제 장비 원본 출력 없이 오류 코드와 단계 상태만 저장합니다.

- `diagnostic_codes.py`: `WLC-영역-번호` 코드, 단계, 원인, 조치 정의
- `diagnostic_events.py`: `DGN-*` 단계 이벤트 모델
- `diagnostic_mode.py`: live/offline 진단 실행과 primary code 결정
- `diagnostic_report.py`: `diagnostic_summary.json/html`, `diagnostic_run.log` 생성
- `redaction.py`: IP, MAC, 호스트명, secret 계열 값 마스킹

mock 관련 파일:

- `mock_scenarios.py`: JSON 시나리오 로드
- `mock_server.py`: 로컬 Telnet/SSH mock WLC 서버
- `config/mock_scenarios/*.json`: 실제 장비 출력이 아닌 synthetic 응답

## 6. 요구사항별 수정 위치

| 요구사항 | 주로 수정할 파일 |
| --- | --- |
| GUI 입력 필드 추가/삭제 | `gui_app.py`, `gui_support.py` |
| WLC 수집 명령 추가 | `collector.py` |
| WLC 출력 파싱 방식 변경 | `aos8_parser.py`, `models.py` |
| Excel 시트/컬럼 변경 | `report.py`, `tests/test_report.py` |
| HTML 화면 디자인 변경 | `report.py`, `tests/test_report.py` |
| Access Check 판단 로직 변경 | `acl_evaluator.py`, `tests/test_acl_evaluator.py` |
| Role network Excel 형식 변경 | `role_networks.py`, `tests/test_role_networks.py` |
| 오류 메시지 개선 | `diagnostics.py`, `tests/test_diagnostics.py` |
| 진단 코드/리포트 변경 | `diagnostic_codes.py`, `diagnostic_mode.py`, `diagnostic_report.py`, `tests/test_diagnostic_*.py` |
| mock 서버/시나리오 변경 | `mock_server.py`, `mock_scenarios.py`, `config/mock_scenarios`, `tests/test_mock_server.py` |
| 배포 ZIP 구성 변경 | `build_windows_gui_exe.ps1`, `tests/test_tooling.py` |
| 사용자 문서 변경 | `docs/USER_GUIDE_KO.md` |
| 개발자 문서 변경 | `docs/DEVELOPER_GUIDE_KO.md` |

## 7. 보안 관련 설계 원칙

이 프로젝트는 외부 개발 후 사내망에 반입해서 사용하는 흐름을 전제로 합니다.

그래서 기본값은 보수적으로 잡습니다.

- 장비 접속정보는 실행 시 직접 입력
- 비밀번호 저장 금지
- Role network Excel은 세션 전용
- 내부 대역을 기본 보고서에 저장하지 않음
- Access Check 이력 기본 미저장
- `outputs/`, `config/private/`, 민감 파일 패턴 git ignore

기능을 추가할 때 내부 IP, 계정, 비밀번호, 정책명, 사용자 정보가 파일에 남는지 먼저 확인해야 합니다.

## 8. 테스트 실행 방법

전체 검증:

```powershell
.\tools\validate.ps1
```

이 스크립트는 다음을 실행합니다.

1. `pytest`
2. `compileall`
3. HTML Access Check JavaScript 문법 검사

부분 테스트:

```powershell
python -m pytest tests\test_report.py
python -m pytest tests\test_acl_evaluator.py
python -m pytest tests\test_role_networks.py
```

기능을 바꾸면 최소한 관련 테스트는 실행해야 합니다. 보고서나 Access Check를 바꿨다면 가능하면 전체 검증을 실행합니다.

## 9. 빌드와 배포

Windows GUI EXE와 ZIP 생성:

```powershell
.\build_windows_gui_exe.ps1
```

결과:

```text
dist\WlcRoleAclCollectorGUI.exe
dist\WlcRoleAclCollectorCLI.exe
dist\WlcRoleAclCollectorGUI_v0.1.0.zip
```

ZIP에는 다음 파일이 포함됩니다.

- `WlcRoleAclCollectorGUI.exe`
- `WlcRoleAclCollectorCLI.exe`
- `USER_GUIDE_KO.md`
- `USER_GUIDE_KO.html`
- `DEVELOPER_GUIDE_KO.md`
- `DEVELOPER_GUIDE_KO.html`
- `ERROR_CODES_KO.md/html`
- `DIAGNOSTIC_MODE_KO.md/html`
- `SECURITY_MODEL_KO.md/html`
- `config\role_networks.example.xlsx`
- `config\mock_scenarios\*.json`

HTML 설명서는 빌드 중 `tools\generate_doc_html.py`가 Markdown 원본에서 자동 생성합니다. 문서를 수정했다면 빌드 전이나 검증 전 아래 명령으로 직접 생성해볼 수 있습니다.

```powershell
python .\tools\generate_doc_html.py
```

빌드 스크립트는 PyInstaller가 만든 EXE를 ZIP에 넣기 전에 파일이 읽기 가능한 상태인지 확인하고, 압축 과정에서 일시적인 파일 잠김이 발생하면 재시도합니다. Windows 보안 검사나 백신이 새 EXE를 잠시 잡는 경우를 줄이기 위한 처리입니다.

## 10. 개발 작업 순서

요구사항이 들어오면 아래 순서로 처리하는 것을 권장합니다.

1. 요구사항이 사용자 기능인지, 개발/운영 편의 기능인지 구분합니다.
2. 관련 파일을 찾습니다.
3. 기존 테스트를 확인합니다.
4. 코드를 작게 수정합니다.
5. 관련 테스트를 추가하거나 수정합니다.
6. `.\tools\validate.ps1`를 실행합니다.
7. 문서가 바뀌어야 하면 `USER_GUIDE_KO.md` 또는 이 문서를 갱신합니다.
8. 로컬 git 커밋을 만듭니다.

## 11. git 기록 방식

이 프로젝트는 로컬 git으로 롤백 지점을 남기는 방식으로 관리합니다.

현재 상태 확인:

```powershell
git status --short --branch
git log --oneline -n 5
```

변경사항 확인:

```powershell
git diff
```

커밋 예시:

```powershell
git add .
git commit -m "Add developer guide"
```

되돌릴 때는 먼저 어떤 커밋으로 돌아갈지 확인하고, 작업 중인 변경사항이 있는지 반드시 확인해야 합니다.

## 12. 초급 개발자가 자주 헷갈릴 수 있는 부분

### `user`와 Role network는 같은 뜻이 아닙니다.

ACL의 `user`는 “현재 이 Role을 받은 사용자 IP”라는 의미입니다. Role의 실제 네트워크 대역을 뜻하지 않습니다.

### `any`는 전체 대역입니다.

`any`는 `0.0.0.0/0`처럼 모든 IP를 의미합니다.

### HTML Access Check는 보고서 안의 데이터로만 판단합니다.

HTML은 WLC에 다시 접속하지 않습니다. 이미 보고서에 들어있는 ACL/Alias 데이터만 사용합니다.

### Role network Excel의 export 기본값은 실행 방식별로 다릅니다.

GUI에서는 사내 Role 대역표를 선택하면 내부용 보고서에 실제 대역을 표시합니다. CLI는 자동화/외부 검증 흐름을 고려해 기본적으로 저장하지 않으며, 내부 보관용으로 반드시 넣어야 한다면 `--export-local-role-networks` 옵션을 명시적으로 사용해야 합니다.

### `show user-table`은 참고용입니다.

현재 접속한 사용자 수와 관측 VLAN/Network를 알 수 있지만, Role의 공식 네트워크 대역이라고 단정하면 안 됩니다.

## 13. 새 기능을 넣을 때 문서도 같이 바꿀 기준

아래 중 하나라도 해당하면 문서를 같이 수정합니다.

- GUI 화면에 새 입력값이나 버튼이 생김
- HTML 보고서에 새 표, 버튼, 컬럼이 생김
- Excel 시트나 컬럼이 바뀜
- 보안 정책이나 저장 정책이 바뀜
- Access Check 판정 기준이 바뀜
- 배포 ZIP 구성물이 바뀜

사용자에게 보이는 기능이면 `USER_GUIDE_KO.md`, 개발자만 알아도 되는 구조 변경이면 `DEVELOPER_GUIDE_KO.md`를 수정합니다.

## 14. 빠른 설명용 요약

동료에게 짧게 설명해야 한다면 이렇게 말하면 됩니다.

```text
이 프로그램은 Aruba WLC에 접속해서 SSID-Role-ACL-Alias 정보를 자동 수집하고,
운영자가 보기 쉬운 HTML/Excel 보고서를 만드는 도구입니다.

collector.py가 장비에서 명령어 결과를 가져오고,
aos8_parser.py가 그 텍스트를 구조화하고,
report.py가 HTML/Excel을 만들고,
acl_evaluator.py가 HTML Access Check 판정 데이터를 준비합니다.

GUI에서 사내 Role 대역표를 선택하면 내부용 보고서에 Role 대역과 WLC 비교 상태가 표시됩니다.
CLI는 보안 기본값을 유지해 `--export-local-role-networks`가 없으면 Role network Excel 값을 보고서에 저장하지 않습니다.
Access Check 이력은 기본적으로 보고서에 저장하지 않습니다.
```
