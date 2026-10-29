# AUTONOMOUS-INVESTOR Railway 22개 서비스 복구·개선 자료

> 스냅샷: 2026-10-29 / Railway production / 서비스 22개 / 영구 볼륨 8개.
> 사용자 요청: 공통 편집기 2개만 유지하고 다른 20개는 중지. **이번 작업에서는 문서와 함수 소스 백업만 수행했으며 20개 중지/삭제는 미실행.**
> 금액은 기존 최근 24시간 사용량을 30일로 환산한 *추정치*이며 Railway 청구액이 아닙니다.

## 1. 현재 유지 대상 (2)

- [investment-n8n-native-editor](https://investment-n8n-native-editor-production.up.railway.app/): 실제 주식 공통 편집기. 데이터 볼륨 investment-shared-studio-drafts (/data).
- [investment-shared-n8n-studio](https://investment-shared-n8n-studio-production.up.railway.app/): 공통 모듈 검증 전용. 데이터 볼륨 shared-n8n-studio-demo-sqlite (/data).

## 2. 전체 22개 서비스와 GitHub 소스

| 번호 | Railway 서비스 | 계획 | GitHub 브랜치 또는 컨테이너 이미지 | Cron | 연결 볼륨 | 월 추정(USD) |
|---:|---|---|---|---|---|---:|
| 1 | investment-n8n-native-editor | 유지 | [feature/engine-run-inspector-20261029](https://github.com/lyonbegin/autonomous-investor-backend/tree/feature/engine-run-inspector-20261029) | — | investment-shared-studio-drafts | $1.03 |
| 2 | investment-shared-n8n-studio | 유지 | [feature/engine-run-inspector-20261029](https://github.com/lyonbegin/autonomous-investor-backend/tree/feature/engine-run-inspector-20261029) | — | shared-n8n-studio-demo-sqlite | $0.08 |
| 3 | autonomous-investor-api | 중지 요청 / 미실행 | [main](https://github.com/lyonbegin/autonomous-investor-backend/tree/main) | — | — | $0.45 |
| 4 | autonomous-investor-integrated | 중지 요청 / 미실행 | [railway-integrated-deploy](https://github.com/lyonbegin/autonomous-investor-backend/tree/railway-integrated-deploy) | — | — | $21.98 |
| 5 | autonomous-investor-public-api | 중지 요청 / 미실행 | [public-platform](https://github.com/lyonbegin/autonomous-investor-backend/tree/public-platform) | — | — | $1.25 |
| 6 | autonomous-investor-public-D18a | 중지 요청 / 미실행 | [public-frontend-react](https://github.com/lyonbegin/autonomous-investor-backend/tree/public-frontend-react) | — | — | $0.38 |
| 7 | autonomous-investor-quant-lab | 중지 요청 / 미실행 | [quant-lab-control](https://github.com/lyonbegin/autonomous-investor-backend/tree/quant-lab-control) | — | quant-lab-data | $0.97 |
| 8 | autonomous-investor-tradingview | 중지 요청 / 미실행 | [tradingview-service](https://github.com/lyonbegin/autonomous-investor-backend/tree/tradingview-service) | — | tradingview-recovery-4gb-Jz6Z | $64.87 |
| 9 | autonomous-investor-tradingview-browser | 중지 요청 / 미실행 | [tradingview-service](https://github.com/lyonbegin/autonomous-investor-backend/tree/tradingview-service) | — | — | $13.09 |
| 10 | autonomous-investor-ui | 중지 요청 / 미실행 | [frontend-vite](https://github.com/lyonbegin/autonomous-investor-backend/tree/frontend-vite) | — | — | $0.64 |
| 11 | investment-n8n-main | 중지 요청 / 미실행 | [feature/secure-selfhost-deployment](https://github.com/lyonbegin/autonomous-investor-backend/tree/feature/secure-selfhost-deployment) | — | — | $3.67 |
| 12 | investment-n8n-operations-ui | 중지 요청 / 미실행 | [feature/n8n-upstream-source-railway-20261027](https://github.com/lyonbegin/autonomous-investor-backend/tree/feature/n8n-upstream-source-railway-20261027) | — | — | $0.35 |
| 13 | investment-n8n-ops-api | 중지 요청 / 미실행 | [feature/secure-selfhost-deployment](https://github.com/lyonbegin/autonomous-investor-backend/tree/feature/secure-selfhost-deployment) | — | investment-operations-data | $1.49 |
| 14 | investment-n8n-preview-runtime | 중지 요청 / 미실행 | 이미지 docker.n8n.io/n8nio/n8n:2.7.2 | — | — | $2.42 |
| 15 | investment-n8n-source-editor | 중지 요청 / 미실행 | [feature/n8n-native-editable-test-20261028](https://github.com/lyonbegin/autonomous-investor-backend/tree/feature/n8n-native-editable-test-20261028) | — | — | $4.75 |
| 16 | investment-n8n-worker | 중지 요청 / 미실행 | [feature/secure-selfhost-deployment](https://github.com/lyonbegin/autonomous-investor-backend/tree/feature/secure-selfhost-deployment) | — | — | $4.18 |
| 17 | macro-collector-cron | 중지 요청 / 미실행 | Railway Function (별도 소스) | 15 */6 * * * | — | 미계측 |
| 18 | Postgres | 중지 요청 / 미실행 | 이미지 ghcr.io/railwayapp-templates/postgres-ssl:18 | — | postgres-volume | $1.44 |
| 19 | Redis | 중지 요청 / 미실행 | 이미지 redis:8.2 | — | redis-volume | $0.34 |
| 20 | tradingview-collector-cron | 중지 요청 / 미실행 | Railway Function (별도 소스) | */5 * * * * | — | $0.38 |
| 21 | tradingview-corporate-bond-cron | 중지 요청 / 미실행 | Railway Function (별도 소스) | */5 * * * * | — | $0.45 |
| 22 | tradingview-horizon-v3-cron | 중지 요청 / 미실행 | Railway Function (별도 소스) | */5 * * * * | — | $0.46 |

**GitHub 구조:** 15개 서비스가 하나의 [lyonbegin/autonomous-investor-backend](https://github.com/lyonbegin/autonomous-investor-backend)에 서로 다른 브랜치로 연결되어 있고, 공통 Vue 편집기 원본은 별도 [lyonbegin/shared-n8n-studio](https://github.com/lyonbegin/shared-n8n-studio) 저장소에 있습니다. 4개 Railway Function과 3개 이미지 서비스는 위 GitHub 브랜치만으로 재현할 수 없습니다.

## 3. 복구 자료 링크

- [원본 Railway 서비스 ID, 볼륨 ID, 브랜치, 배포 상태: inventory.json](inventory.json)
- [스프레드시트로 열 수 있는 서비스별 목록: services.csv](services.csv)
- [Dockerfile, 시작 명령, 헬스체크, 도메인, 환경변수 이름: deployment-config-01.json](deployment-config-01.json)
- [나머지 서비스 배포 설정: deployment-config-02.json](deployment-config-02.json)
- [Railway Function 실행 원본 백업](functions/)
- [향후 개선 백로그](IMPROVEMENT_BACKLOG.md)

## 4. Railway Functions: 실제 GitHub 백업 가능 범위

| Railway Function | 실행 소스 확보 | 위치 |
|---|---|---|
| tradingview-collector-cron | 성공 | [TS 원본](functions/tradingview-collector-cron.ts) |
| tradingview-horizon-v3-cron | 성공 | [TS 원본](functions/tradingview-horizon-v3-cron.ts) |
| tradingview-corporate-bond-cron | 성공 | [TS 원본](functions/tradingview-corporate-bond-cron.ts) |
| macro-collector-cron | **실패: Railway 서비스 조회 오류** | 복구할 코드 미확보. 중지·삭제 전 별도 회수 필요 |

## 5. 영구 볼륨: GitHub에는 저장되지 않는 실제 데이터

| 볼륨 | 할당 크기(MB) | 현재 연결 | 중요 주의 |
|---|---:|---|---|
| tradingview-recovery-4gb-Jz6Z | 4096 | autonomous-investor-tradingview /data | DB·파일 일관성 백업 필요 |
| tradingview-data | 1024 | 미연결  | 미연결이더라도 삭제 금지 |
| quant-lab-data | 1024 | autonomous-investor-quant-lab /data | DB·파일 일관성 백업 필요 |
| shared-n8n-studio-demo-sqlite | 512 | investment-shared-n8n-studio /data | 유지 대상 편집기 SQLite 보존 |
| investment-shared-studio-drafts | 512 | investment-n8n-native-editor /data | 유지 대상 편집기 SQLite 보존 |
| redis-volume | 50000 | Redis /data | Redis RDB/AOF 확인 |
| postgres-volume | 50000 | Postgres /var/lib/postgresql/data | PostgreSQL pg_dump 필요 |
| investment-operations-data | 1024 | investment-n8n-ops-api /data | DB·파일 일관성 백업 필요 |

**볼륨 할당 크기와 실제 사용 용량은 다릅니다.** 볼륨이 남아 있으면 서비스 컨테이너가 멈춰도 저장 요금은 발생할 수 있습니다.
**GitHub 보존만으로는 DB 데이터를 복원하지 못합니다.** Postgres 논리 덤프, Redis 스냅샷, SQLite 일관성 백업, TradingView 데이터 파일, 환경변수의 실제 값 및 sealed secrets를 별도 보안 백업으로 확보해야 합니다.
환경변수 **이름만** deployment-config 파일에 보관했습니다. 패스워드와 토큰 값은 GitHub에 올리지 않았습니다.

## 6. 상호 의존성과 재기동 계획

1. 투자 n8n main 및 worker는 Postgres와 Redis 큐의 영향을 받으므로, 신규 작업 차단·큐 비우기 후 마지막에 DB를 중지합니다.
2. TradingView Cron 작업들은 autonomous-investor-tradingview API를 호출하고, API는 별도 TradingView 브라우저 수집기를 이용합니다. 수집 API와 Cron은 개별 중지·재기동 계획이 필요합니다.
3. 퀀트 분석은 TradingView / Integrated 서비스의 설정 의존성이 있으므로 복구 시 연결을 재검증합니다.
4. 복구 시작: 저장 볼륨·환경변수 → Postgres/Redis → n8n worker/main → 투자/TradingView API → 분석 UI → Cron 마지막. 실거래 기능은 PAPER 모드 검증 전에 열지 않습니다.
5. 두 공통 편집기는 자체 SQLite 볼륨을 사용하지만 실시간 n8n 실행과는 별도이며, 실제 주문/API 실행 통합은 미완료입니다.

## 7. 중지 요청을 지금 수행하지 않은 이유

완전히 중지된 컨테이너는 실행 RAM·CPU를 소비하지 않지만, Railway serverless 절전은 외부 요청/스케줄에 의해 다시 깨어날 수 있습니다. 현재 연결 도구에서는 비파괴적인 일시중지 또는 scale-to-zero를 보장하는 동작을 제공하지 않습니다. 서비스 영구 삭제는 도메인, 설정, 배포 트리거를 제거하며 이 자료만으로 자동 복구되지 않습니다.
**따라서 이번 기록 시점에 22개 모두 기존 상태이며, 서비스 중지·삭제·DB 종료·볼륨 삭제를 실행하지 않았습니다.** 완전 중지를 수행하려면 복구 백업 및 지원되는 중지 방식을 먼저 검증해야 합니다.

## 8. 비용 및 최적화 우선순위

- 이전 실측 기준 21개 약 $124.66/30일, 유지 2개 $1.11/30일, 나머지 이론상 $123.55/30일. **실제 절감 확정액 아님**; macro-collector-cron은 사용량 조회 실패.
- 1순위: autonomous-investor-tradingview (메모리 4.5GB 및 반복 수집/API·SQLite 잠금).
- 2순위: autonomous-investor-integrated (평균 2.25GB 상주 메모리; 분석 엔진 지연 로딩/독립 워커).
- 3순위: autonomous-investor-tradingview-browser (Playwright Chromium 상주/HTTP 호출 경량화).
- 구형 n8n source-editor, preview-runtime, operations-ui의 의존성을 비교하고 완전 대체 후 정리.
- 정확한 추적 작업과 재가동 테스트 기준은 [IMPROVEMENT_BACKLOG.md](IMPROVEMENT_BACKLOG.md) 참조.

## 9. 재검증 체크리스트

- [ ] 22개 현재 Service ID, GitHub branch HEAD 및 실제 배포 commit SHA 대조
- [ ] 4개 Railway Function 중 macro 코드 원본 회수
- [ ] 8개 볼륨 중 실제 데이터 백업 및 복구 리허설
- [ ] 각 서비스 비밀 환경변수 안전 보관·재발급 절차 마련
- [ ] 외부 webhook 및 cron 재시작 시 중복 실행 차단
- [ ] UI 유지 2개가 기존 투자 API·Postgres·Redis 정지 상태에서도 작동하는지 확인
- [ ] 정식 중지 후 Railway 서비스 상태와 비용 재계측
- [ ] GitHub 문서 PR 검토 후 최종 소스 기준 확정
