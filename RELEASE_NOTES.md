# Release Notes 운영 규칙

이 파일은 저장소에 커밋하는 릴리즈 준비 점검 문서입니다. 실제 GitHub Release 본문은 `.github/workflows/release.yml`에서 main push 시 한국어로 자동 생성합니다.

## Release 전 문서 점검

GitHub에 push하거나 Release를 준비하기 전에 아래 문서를 함께 확인합니다.

- `README.md`: 설치, 실행, 빌드, 배포 파일, 폴더 구조, 제한사항
- `RELEASE_NOTES.md`: Release 설명 규칙과 asset 계약
- `CHANGELOG.md`: 구현된 변경과 미구현/제외 항목 구분

문서에는 사내 IP, 실제 장비명, 계정, 비밀번호, 실제 로그, 내부망 정보, 고객 정보를 넣지 않습니다. 예시는 `192.0.2.10`, `10.10.10.0/24`, `sample_controller` 같은 샘플 값만 사용합니다.

## GitHub Release 본문에 포함되는 정보

자동 Release notes에는 다음 정보가 들어가야 합니다.

- 변경 커밋 목록
- 기준 커밋 SHA
- 브랜치명
- 실행한 검증 명령
- 실행한 빌드 명령
- 산출물 파일명
- SHA256 파일명
- SHA256 checksum
- 변경 파일 목록

## Release Asset 계약

GitHub Release에는 아래 두 파일을 업로드합니다.

- `wlc-role-acl-collector_vYYYY.MM.DD-HHMMSS_windows.zip`
- `wlc-role-acl-collector_vYYYY.MM.DD-HHMMSS_windows.zip.sha256`

ZIP 내부에는 아래 파일이 포함되어야 합니다.

- `WlcRoleAclCollectorGUI.exe`
- `WlcRoleAclCollectorCLI.exe`
- `USER_GUIDE_KO.md`, `USER_GUIDE_KO.html`
- `DEVELOPER_GUIDE_KO.md`, `DEVELOPER_GUIDE_KO.html`
- `ERROR_CODES_KO.md`, `ERROR_CODES_KO.html`
- `DIAGNOSTIC_MODE_KO.md`, `DIAGNOSTIC_MODE_KO.html`
- `SECURITY_MODEL_KO.md`, `SECURITY_MODEL_KO.html`
- `config/role_networks.example.xlsx`
- `config/mock_scenarios/*.json`

ZIP과 `.sha256` 파일은 Release asset입니다. 저장소에는 커밋하지 않습니다.

## 검증 기준

Release 전에 다음 검증이 통과해야 합니다.

```powershell
python -m pytest -q
python -m compileall -q src tests tools
python -m pip check
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\validate.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_windows_gui_exe.ps1
python .\tools\verify_release_package.py --dist .\dist --smoke-cli
```

로컬 macOS에서 PowerShell 또는 Windows EXE 검증을 실행할 수 없으면 GitHub Actions `windows-latest` 결과를 기준으로 확인합니다.

## 작성하지 않을 내용

- 실제 WLC 주소, 장비명, 사용자명, 비밀번호
- 회사 내부 Role 대역표 원본 내용
- 실제 `show` 명령 출력
- 고객명, 사이트명, 운영망 식별자
- 아직 구현하지 않은 installer, MSIX, 코드서명 기능
