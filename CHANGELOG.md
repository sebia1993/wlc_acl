# Changelog

이 문서는 저장소에 반영된 주요 변경을 사람이 확인하기 위한 기록입니다. GitHub Release 본문은 Actions에서 자동 생성하지만, 기능 범위와 문서 상태는 이 파일에도 맞춰 둡니다.

## 0.1.0 - 현재 자동 Release 라인

현재 구현된 주요 기능:

- 사내망 내부 공용 PC에서 실행하는 Streamlit 웹앱을 제공합니다.
- Python 설치가 없는 Windows PC에서도 실행할 수 있도록 Streamlit portable ZIP을 제공합니다.
- Streamlit 웹앱에서 WLC 접속 정보 입력, Role 대역 Excel 업로드, 진행 상태 표시, 결과 요약, 테이블 미리보기, xlsx/csv/html 다운로드를 제공합니다.
- Aruba AOS8 WLC에서 SSID, AAA Profile, 기본 Role, Role ACL, Alias 정보를 수집합니다.
- `show ip interface brief`와 `show user-table`을 이용해 Role 대역 추정 근거와 현재 관측 사용자 정보를 보고서에 표시합니다.
- Excel 보고서와 HTML 보고서를 생성합니다.
- HTML 보고서에서 Role별 ACL 보기, 주석 임시 저장, 주석 포함 HTML 저장, PDF 저장/인쇄, Access Check를 제공합니다.
- GUI에서 사내 Role 대역 Excel 파일을 선택해 내부용 비교 보고서를 만들 수 있습니다.
- CLI에서는 `--export-local-role-networks`를 명시한 경우에만 로컬 Role 대역을 보고서에 포함합니다.
- 안전 진단 모드는 민감정보를 마스킹한 HTML/JSON 진단 보고서를 생성합니다.
- Windows Release asset은 GUI/CLI와 Streamlit portable 웹앱을 함께 담은 통합 ZIP 하나로 배포합니다.
- 통합 ZIP에는 GUI exe, CLI exe, 한국어 문서, 내장 Python 웹앱, Role 대역 예제 Excel, mock scenario JSON이 포함됩니다.
- GitHub Actions는 PR에서 테스트/Windows 빌드/통합 ZIP 검증을 수행하고, main push에서 공개 Release와 SHA256 checksum을 생성합니다.

최근 안정성 개선:

- Streamlit 실행마다 날짜시간과 세션 구분값이 포함된 결과 파일명을 사용합니다.
- Streamlit 업로드 파일과 결과 파일은 서버 임시 작업 폴더에서 처리하고 다운로드 bytes만 세션에 보관합니다.
- Streamlit portable ZIP 검증에서 내장 Python, Streamlit 패키지, 앱 패키지, `start_webapp.cmd --smoke`, SHA256 sidecar를 확인합니다.
- 통합 Release ZIP 검증에서 `gui`와 `web` 실행 경로, 필수 문서/config, CLI smoke, 웹앱 smoke를 확인합니다.
- collect, diagnose, GUI 수집 결과 폴더가 같은 시간에 생성되어도 충돌하지 않도록 run directory 생성 방식을 개선했습니다.
- `enable password` 적용 실패를 조용히 무시하지 않고 수집 결과와 진행 이벤트에 기록합니다.
- Windows 배포 ZIP 검증에서 GUI/CLI exe, 문서, config, mock scenario, CLI `--help`, SHA256 sidecar를 확인합니다.

현재 제외된 항목:

- 코드서명, installer, MSIX, SmartScreen 평판 대응
- ClearPass/RADIUS 서버에서 동적 Role을 직접 조회하는 기능
- TCP/UDP 포트 번호 기반 service object 정밀 해석
- Streamlit 웹앱 자체 사용자 로그인/권한 관리
- macOS에서 Windows EXE를 직접 생성하는 공식 빌드 경로

## 문서 변경 원칙

기능, 실행 방법, 빌드 방법, Release asset, ZIP 내부 구조가 바뀌면 `README.md`, `RELEASE_NOTES.md`, `CHANGELOG.md`를 함께 점검합니다.

문서 예시는 샘플 값만 사용합니다. 사내 IP, 실제 장비명, 계정, 비밀번호, 실제 로그, 고객 정보는 기록하지 않습니다.
