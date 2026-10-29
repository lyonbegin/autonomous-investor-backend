# Railway 20개 서비스 중지 진행기록 — 2026-10-29

프로젝트 `AUTONOMOUS-INVESTOR` / production. 사용자 요청: 기존 20개 배포만 중지하고 공통 편집기 `investment-n8n-native-editor`, `investment-shared-n8n-studio`는 유지. 서비스/볼륨 영구 삭제 금지.

## 1차 Windows CLI 실행 확인

- `railway 5.46.0`, `python3 railway_stop_20_services_fixed.py --execute` 실행
- 01. `tradingview-collector-cron` — CLI `COMMAND OK`. Railway 최근 배포 상태 `REMOVED` 확인.
- 02. `tradingview-horizon-v3-cron` — CLI `COMMAND OK`. Railway 최근 배포 상태 `REMOVED` 확인.
- 03. `tradingview-corporate-bond-cron` — CLI `COMMAND OK`. Railway 최근 배포 상태 `REMOVED` 확인.
- 04. `macro-collector-cron` (ID `66329211-ad39-40d4-beb32a4ce494`) — CLI `Service not found`로 실패. **중지 확인 불가**. Railway environment 목록에는 나타나지만 개별 서비스 조회에서는 `Service not found in this project`, 최근 배포 조회는 빈 목록. 코드 원본도 백업 미확보. 이는 정상 중지의 근거가 아님.
- 05~20. 원 스크립트가 실패 즉시 중단해 아직 중지 명령 미실행.
- 유지할 공통 편집기 2개: Railway 최근 배포 `SUCCESS` 확인.

## 안전한 재개

Windows PowerShell에서 이미 생성된 `railway_stop_20_results.json`은 변경/삭제하지 말고 같은 폴더에서 **수정된** `railway_stop_20_services_resume.py --execute --resume` 실행. 스크립트는 기존 성공 1~3을 건너뛰고 4에 대하여 동일 ID의 404만 `unresolved_service_not_found`로 남긴 뒤 5~20을 계속한다. 일반적인 오류는 그대로 중지한다.

수정 스크립트 시뮬레이션: 기존 3개 성공 이력 + 4번 예외 + 16개 성공 = 최종 **19개 CLI 성공, 1개 미확인**. 시뮬레이션이며 실제 5~20 배포 상태를 의미하지 않음.

**중요:** `railway down`은 최신 성공 배포를 제거하며 서비스/스케줄 설정을 삭제하지 않는다. 3개 Cron의 `*/5 * * * *` 스케줄은 Railway 설정에서 여전히 확인되었다. 이후 자동 작업/배포가 다시 생성되지 않는지 별도 확인해야 한다. GitHub 자동 배포 또한 추후 재기동시킬 수 있다.

## 완료 기준

1. Railway의 최신 배포 목록에서 20개 모두 실행 중 배포 `SUCCESS`가 없음을 확인.
2. `macro-collector-cron`의 실제 존재/배포/스케줄, 원본 코드 회수 여부를 해결.
3. 편집기 두 개는 계속 `SUCCESS`이고 저장/화면이 유지되는지 확인.
4. 영구 볼륨 8개와 비밀값은 삭제·노출하지 않았음을 확인.
5. 추후 자동배포 및 Cron 재실행 여부 검사.

관련: [22개 서비스 복구 자료](README.md) · [전체 서비스 ID](inventory.json).
