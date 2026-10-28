# Railway 서비스 보관 후 개선 백로그 — 2026-10-29

범위: AUTONOMOUS-INVESTOR production 22개 서비스. 이번 문서는 실행 계획 및 인수인계; 모든 작업은 미실행이며 현행 2개 공통 편집기를 유지.

## P0. 재구축 가능성 확보 — 서비스 정지/삭제 전에 필수

| ID | 대상 | 필요한 조치 | 완료 기준 | 위험 / 롤백 |
|---|---|---|---|---|
| P0-1 | macro-collector-cron | Railway Function 코드를 수동 복구해 GitHub에 보관. 현재 Railway Function API가 Service not found 응답 | 원본 TS 소스 SHA 및 1회 드라이런 결과 확보 | 원본 미확보 상태에서 제거 금지 |
| P0-2 | Postgres | 일관성 pg_dump 및 복구 전용 DB로 리허설 | 테이블/핵심 n8n workflows/credentials 메타데이터 복원 확인 | 비밀키 별도 보안 보관 |
| P0-3 | Redis | RDB/AOF 및 큐 상태 백업, 작업 유실 정책 수립 | 큐 복구 및 중복 주문 방지 확인 | 재가동 후 중복 실행 가능성 |
| P0-4 | TradingView, Quant, Ops 볼륨 | 모든 8개 볼륨 사용 상태 점검, SQLite WAL 포함 일관성 백업 | 아카이브·해시·파일 검증/복원 시험 | 마운트만 분리해도 데이터 영속 여부 별개 |
| P0-5 | 모든 Railway 서비스 | 변수 이름뿐 아니라 secrets의 재발급 위치·권한·키 순환 문서화 | 누락 없이 새 환경 기동 가능, GitHub에 값 미기록 | sealed secrets는 읽기 불가 |
| P0-6 | 20개 중지 후보 | 지원되는 완전중지·스케줄 중단 방법 확인, 두 편집기 헬스 검증 | Railway 실행 인스턴스 0, Cron 비활성, CPU/RAM 0과 DB 데이터 보존 검증 | sleepApplication은 자동 재기동될 수 있음 |

## P1. 절감액 상위 서비스 성능 개선 (중지 중 개발 가능)

| ID | 서비스 | 현재 관찰 | 개선 작업 | 수용 기준 |
|---|---|---|---|---|
| P1-1 | autonomous-investor-tradingview | 4.5GB 평균 RAM, 0.95 vCPU, 24h API 24,595건 | 요청 캐시·TTL, 중복 수집 방지, API/SQLite 연결 계측, 빈번한 스키마 초기화 제거 | 수집 결과 정확도 유지, 5xx 및 database locked 감소, 동일 부하 RAM/CPU 비교 |
| P1-2 | autonomous-investor-integrated | 2.25GB RAM, 24h 공개 HTTP 4건 | 분석 라이브러리 지연 import, 워커 격리 및 idle 종료, 로딩 측정 | 12개 엔진 동작 유지, 대기 RAM 절감, 엔진별 테스트 PASS |
| P1-3 | autonomous-investor-tradingview-browser | 1.11GB RAM, 하루 4.07GB 수신 / 0.87GB 송신, 요청 46,218건 | Playwright HTTP 경량 요청 대체, context 재사용, 브라우저 필요 작업 분기, 캐시·동시성 제한 | TradingView 파싱 정확도 유지, 수신량/RAM 절감, 브라우저 누수 없음 |
| P1-4 | tradingview-corporate-bond-cron | 최근 database is locked / timeout 관찰 | 제한된 단위 작업, 재시도·백오프, DB 쓰기 큐 직렬화 | 매주 재실행 안정, 수집 누락 0 |
| P1-5 | tradingview-horizon-v3-cron | 과거 과도한 처리 시간/Crash | 한 번에 처리하는 큐 배치 제한, 작업 시간 상한, 중복 진행 방지 | 5분 작업이 다음 스케줄 전에 완료 |

## P2. 중복 서비스 및 공통 편집기 정리

- investment-n8n-source-editor: 원본 n8n 2.x 편집기 복원용 가치 vs 현재 공통 편집기 기능 비교. 의존 참조 0건 확인 후 정리.
- investment-n8n-preview-runtime: 고정 2.7.2 버전 미리보기. 기존 페이지와 50종 노드/샌드박스에서 실제 사용 여부 확인.
- investment-n8n-operations-ui: 운영 관리(시나리오·전략·에이전트) 기능은 새 공통 편집기에 아직 완전 이전되었다고 볼 수 없음. 이전 후 정리.
- autonomous-investor-ui / autonomous-investor-public-D18a: 사용자 라우팅·기능 차이를 비교해 단일 진입점 설계.
- investment-n8n-native-editor와 investment-shared-n8n-studio: **서로 다른 SQLite 볼륨을 유지**하며 공통 패키지는 GitHub shared-n8n-studio 한 곳에서 관리. 버전 태그를 사용.

## P3. 재기동·실사용 인수 테스트

1. 데이터 불변성: DB·파일 해시 및 워크플로 수가 복구 전후 동일.
2. API: /health, Strategy/TradingView 읽기, 권한 통제, 외부 네트워크 오류 처리.
3. n8n: Postgres 연결, Redis 큐, main/worker 정합성, 13개 워크플로 조회/편집.
4. 공통 UI: 빈 배경 왼쪽 Pan, Shift 선택, 노드 이동·연결·설정, 서버 DB 저장/재접속/버전 복원.
5. 브라우저 수집: 백필과 원본 Pine 스크립트 데이터의 저작권·재배포 조건, 저장 용량, 중복 방지.
6. 분석 엔진: TradingAgents, FinRobot, RD-Agent(Q), Qlib, Chronos, SB3, RLlib, vectorbt, FinRL, Riskfolio-Lib, PyPortfolioOpt, NautilusTrader 각각 import/실행/리소스 격리.
7. 주문: PAPER만, 실행 제한 및 수동 승인 전 LIVE 차단. 비밀값 복원·실거래 사용은 별도 승인.

## 중지/재개 기록 양식 (변경시마다 복사하여 사용)

| 시점(KST) | 서비스 ID | 작업자 | 변경 종류 | 이전 상태 | 이후 상태 | 볼륨 백업 위치/체크섬 | 검증 | Rollback |
|---|---|---|---|---|---|---|---|---|
| 미실행 | 20개 중지 후보 | — | 기록만 | Railway production 기준 | 변경 없음 | 별도 백업 미확인 | 해당 없음 | 해당 없음 |

참조: [전체 복구 문서](README.md), [서비스 목록](services.csv), [설정 스냅샷 1](deployment-config-01.json), [설정 스냅샷 2](deployment-config-02.json).
