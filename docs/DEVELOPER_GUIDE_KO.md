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
- Role network Excel 세션 전용 로드
- 기본 보안모드에서 Role network Excel 값과 Access Check 이력 미저장

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
- Role network Excel 선택
- 수집 시작 버튼 처리
- 백그라운드 스레드에서 수집 실행
- 완료 후 HTML/Excel 열기 버튼 활성화
- 오류 발생 시 메시지 박스 표시

주의할 점:

- GUI가 멈추지 않도록 수집 작업은 별도 스레드에서 실행합니다.
- 비밀번호는 파일에 저장하지 않습니다.
- Role network Excel 경로와 내부 대역은 run.log에 남기지 않습니다.

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
- 보안모드에서 민감 데이터 export 차단

중요한 보안 기본값:

```python
export_local_role_networks=False
access_history_enabled=False
```

이 기본값 때문에 Role network Excel을 선택해도 기본 HTML/Excel에는 내부 대역이 저장되지 않습니다.

### `acl_evaluator.py`

HTML Access Check의 판단 로직을 준비하는 파일입니다.

지원하는 Source/Destination 형태:

- `any`
- `user`
- `host 10.1.1.1`
- `network 10.1.1.0 255.255.255.0`
- `range 10.1.1.10 10.1.1.20`
- `alias 이름`

판정 결과:

- `Allowed`
- `Blocked`
- `Allowed with NAT/Special Action`
- `Implicit deny`
- `Conditional`

주의할 점:

- Service object의 실제 TCP/UDP 포트까지 완전 해석하지는 않습니다.
- Alias가 IP 범위로 해석되지 않으면 warning을 표시합니다.

### `role_networks.py`

사용자가 선택한 Role network Excel을 읽고 검증합니다.

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
dist\WlcRoleAclCollectorGUI_v0.1.0.zip
```

ZIP에는 다음 파일이 포함됩니다.

- `WlcRoleAclCollectorGUI.exe`
- `USER_GUIDE_KO.md`
- `DEVELOPER_GUIDE_KO.md`
- `config\role_networks.example.xlsx`

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

### Role network Excel은 기본 보고서에 저장되지 않습니다.

보안모드 기본값 때문입니다. 내부 보관용으로 반드시 넣어야 한다면 CLI의 `--export-local-role-networks` 옵션을 명시적으로 사용해야 합니다.

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

보안상 Role network Excel과 Access Check 이력은 기본적으로 보고서에 저장하지 않습니다.
```
