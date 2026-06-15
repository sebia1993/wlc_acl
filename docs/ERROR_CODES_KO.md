# WLC Role ACL Collector 오류 코드

이 문서는 외부 개발자에게 원본 로그 없이 전달 가능한 오류 코드 기준입니다.

## 기본 원칙

- 오류 코드는 `WLC-영역-번호` 형식입니다.
- 진단 리포트에는 원본 장비 출력, 실제 IP, 호스트명, 계정, 비밀번호를 저장하지 않습니다.
- 문제 분석 시에는 `primary_code`, `stage`, `command_id`만 먼저 전달합니다.

## 코드 표

| 코드 | 단계 | 의미 | 현장 확인 |
| --- | --- | --- | --- |
| OK | DGN-COMPLETE | 차단 이슈 없이 진단 완료 | 추가 조치 없음 |
| WLC-ENV-001 | DGN-BOOT | 실행 환경 초기화 실패 | EXE 위치, 보안 정책, 백신 확인 |
| WLC-INP-001 | DGN-INPUT | 입력값 오류 | protocol, port, timeout, WLC 주소 확인 |
| WLC-NET-001 | DGN-NET | 연결 timeout | 라우팅, 방화벽, SSH/Telnet 활성화 확인 |
| WLC-NET-002 | DGN-NET | connection refused | 포트 오픈 여부와 프로토콜 확인 |
| WLC-NET-003 | DGN-NET | 네트워크 경로 불가 | 로컬 PC 라우팅, VPN, ACL 확인 |
| WLC-AUTH-001 | DGN-AUTH | 인증 실패 | ID/PW, 계정 잠금, 로그인 권한 확인 |
| WLC-AUTH-002 | DGN-AUTH | enable password 실패 | enable password 필요 여부 확인 |
| WLC-PRM-001 | DGN-PROMPT | 프롬프트 탐지 실패 | 배너, paging, timeout 확인 |
| WLC-CMD-001 | DGN-CMD | 필수 설정 출력 없음 | `show configuration effective` 권한 확인 |
| WLC-CMD-002 | DGN-CMD | 명령 timeout | timeout 증가, paging 해제 확인 |
| WLC-CMD-003 | DGN-CMD | 명령 거부 또는 권한 없음 | 계정 command authorization 확인 |
| WLC-CMD-004 | DGN-CMD | Role/Alias 세부 명령 일부 실패 | 해당 Role/Alias 명령 권한 확인 |
| WLC-PRS-001 | DGN-PARSE | 설정 파싱 실패 | AOS8 WLC 여부와 출력 완전성 확인 |
| WLC-PRS-002 | DGN-PARSE | Alias 파싱 일부 불완전 | Alias 수동 검토 필요 여부 확인 |
| WLC-RPT-001 | DGN-REPORT | 출력 폴더 쓰기 실패 | Documents 등 로컬 쓰기 가능 폴더 선택 |
| WLC-RPT-002 | DGN-REPORT | 리포트 생성 실패 | 파일 잠금, 경로 길이, 권한 확인 |
| WLC-SEC-001 | DGN-SEC | 마스킹 self-test 실패 | 리포트 외부 공유 금지, 도구 재배포 |
| WLC-MOCK-001 | DGN-MOCK | mock 서버 시작 실패 | 포트 충돌, 로컬 방화벽 확인 |
| WLC-MOCK-002 | DGN-MOCK | mock 시나리오 오류 | JSON 형식과 필수 command 확인 |
| WLC-UNK-001 | DGN-UNKNOWN | 미분류 오류 | 안전 진단 리포트만 공유 |

## 전달 예시

```text
primary_code: WLC-CMD-001
stage: DGN-CMD
command_id: configuration_effective
raw_output_saved: false
```
