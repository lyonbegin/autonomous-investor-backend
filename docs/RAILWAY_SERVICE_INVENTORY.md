# Railway 서비스 인벤토리

현재 조회 상태: **미검증/접근 차단**. 최신 서비스 개수·환경·스케줄·볼륨을 확인했다고 보고하지 않는다. 아래 표는 첨부 지시서의 2026-10-27 과거 스냅샷 19개이며 `SUCCESS`는 당시 배포 상태뿐이다.

프로젝트: `155584dd-b4a4-416c-8f25-c24970c9007c`, production: `891ba96c-9d98-492d-9176-25481e256c60` (모두 재조회 필요).

| 과거 서비스명 | ID | 당시 배포 | 역할/브랜치 단서 |
|---|---|---|---|
| autonomous-investor-integrated | `02a6cadc-d059-45d5-b89f-618ebe6d611b` | SUCCESS | 통합 API 서비스 / `railway-integrated-deploy` |
| tradingview-collector-cron | `b07ee32b-315e-4da4-a703-cfe5889930e6` | SUCCESS | TradingView 정기 수집 `*/5 * * * *` |
| autonomous-investor-quant-lab | `530b6946-991c-4a67-b2e8-e90249ee515d` | SUCCESS | 퀀트 랩 / `quant-lab-control` |
| autonomous-investor-ui | `693151a6-18e0-4bc9-b5d7-d1a2869b341f` | SUCCESS | UI / `frontend-vite` |
| autonomous-investor-tradingview | `aae76a90-6237-4d0f-a3d0-621dbfe7f14f` | SUCCESS | TradingView 서비스 |
| autonomous-investor-public-D18a | `1b0c086f-8b94-4188-bc6d-6d6d167cb9bd` | SUCCESS | React 공개 프론트 / `public-frontend-react` |
| macro-collector-cron | `66329211-ad39-40d4-8cd4-beb32a4ce494` | SUCCESS | 거시경제 데이터 `15 */6 * * *` |
| autonomous-investor-tradingview-browser | `dce0b284-e16a-49c0-9bd4-6ca1e5136e76` | SUCCESS | 브라우저 수집기 |
| autonomous-investor-public-api | `382a3c15-b224-43c8-a890-6910d0003919` | SUCCESS | 공개 API / `public-platform` |
| investment-n8n-operations-ui | `d5028f56-c90e-40d7-bdcc-037c8c2220e9` | SUCCESS | 비로그인 읽기 + 합성 테스트 화면 |
| investment-n8n-worker | `d982a6d6-268b-4c29-892c-d475403d430d` | SUCCESS | n8n Worker |
| Redis | `1979d38a-942e-49df-959f-5a60625936e4` | SUCCESS | Redis 8.2 / 데이터 보존 |
| autonomous-investor-api | `99323fe2-606d-44b7-8c4a-1a672aab968a` | SUCCESS | `main` 기반 API |
| investment-n8n-native-editor | `6231df4a-7b0b-47be-9097-546472672763` | SUCCESS | **원본 n8n에 대한 인증 프록시** |
| investment-n8n-main | `06f6d322-17da-4ba9-be6a-88e6fb281446` | SUCCESS | n8n 메인, private 5678 포트 |
| tradingview-horizon-v3-cron | `30242c82-5bb3-4a93-856d-f20203bb6b4a` | SUCCESS | Horizon 크론 `*/5 * * * *` / 실행 오류 확인 필요 |
| Postgres | `d31addf0-389d-4cb7-9c67-002b65f68a30` | SUCCESS | PostgreSQL 18 / 데이터 보존 |
| tradingview-corporate-bond-cron | `6f240b92-5fdf-4b1e-8288-12349d3fab39` | SUCCESS | 회사채 ISIN prefix backfill `*/5 * * * *` |
| investment-n8n-ops-api | `0c1c0c69-6c16-41d5-abc7-cecc76036afa` | SUCCESS | Python 운영 API / 영속 볼륨 |

과거 볼륨: postgres-volume, redis-volume, investment-operations-data, quant-lab-data, tradingview-recovery-4gb-Jz6Z, tradingview-data. 현재 mount·용량·백업은 미확인.

현재 환경에서 Railway 도구/CLI/토큰 바인딩이 없었다. Git HTTPS read/fetch는 성공했다. 운영 UI와 n8n 게이트웨이 read-only HTTPS는 프록시 403으로 차단됐다. Git 인증을 Railway API 인증으로 간주하지 않는다.

필요한 후속 접근: Railway 프로젝트의 서비스 설정·배포·로그·스케줄·볼륨에 대한 읽기 권한, n8n 관리자 읽기 권한. 비밀값은 채팅에 입력하지 않고 안전한 환경 연결로 제공한다. 운영 변경은 별도 승인 이후만 가능하다.

재조회 후 서비스별 source.branch/image, Dockerfile, startCommand, 환경변수 **이름만**, private DNS, 포트, DB, 볼륨, cron, 마지막 성공/실패 시각, 실제 적재 건수를 기록한다. 통합 브랜치로 전체 production source를 일괄 변경하지 않는다.
