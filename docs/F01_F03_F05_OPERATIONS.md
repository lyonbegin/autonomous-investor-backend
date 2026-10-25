# n8n 실제 운영 플로우 F01 / F03 / F05

## 구현 범위

기존 n8n 10개 합성 시나리오와 12개 엔진 노드 편집기를 유지하며, F01/F03/F05의 실제 DB 상태 전이 및 API를 추가했다.

| 플로우 | 독립 n8n 트리거 | API 작업 | DB 출력 |
|---|---|---|---|
| F01 | 15분 주기, 수동, Webhook | POST /api/v1/ops/strategies/sync?refresh_live=true | Pine 전략 메타데이터·해시·원본, 변경 버전, 이벤트 |
| F03 | 1분 주기, 수동, Webhook | POST /api/v1/ops/assignments/allocate-one | PAPER 에이전트 독점 할당, Lease, Fencing Token, 이벤트 |
| F05 | 1분 주기, 수동, Webhook | POST /api/v1/ops/audit/reconcile | Lease 만료·이상 감사, HALTED, 이벤트 |

F05의 /api/v1/ops/audit/observations는 별도의 즉시 이벤트 접수 엔드포인트로, 전략 버전 불일치·오래된 Fencing Token·미승인 주문 관측을 검사한다. 실제 주문 실행 기능은 포함되지 않는다.

## F01 실제 소스 흐름

n8n Schedule → 기존 TradingView-service의 /scripts/live?sort=recent_extended&script_type=strategies → 해당 서비스의 /scripts/catalog 조회 → live 수집 결과와 카탈로그 dedupe → 소스 /scripts/{id}/source?version={source_version} 조회 → SHA256로 불변 버전 생성 → SQLite 전략 풀·Pine 아티팩트 보관 → F02 검토 대기

새 전략/새 버전은 절대 자동 승인하지 않는다. 소스가 비공개·보호·표시 불가면 INELIGIBLE; 전략 공개 Pine을 확보하면 PENDING_REVIEW. 사용권/정확성/독립 백테스트 검증의 근거 확인은 별도 운영자 승인 필요.

최신 수집 API 실패 시 HTTP 502와 SourceSyncFailed 이벤트를 반환하고 오래된 캐시를 최신 데이터처럼 취급하지 않는다. 저장된 메타데이터 조회를 위한 refresh_live=false 옵션도 제공하지만, n8n F01과 React F01 버튼은 true를 사용한다.

## F03 배정과 안전 원칙

승인된 Pine 전략(현재 사람의 증거 확인 기록) + IDLE PAPER 에이전트를 SQLite BEGIN IMMEDIATE 트랜잭션과 UNIQUE filtered index로 1:1 배정한다. 동일 전략 슬롯의 동시 배정 15회 레이스 테스트에서 단 하나만 성공한다. Lease 만료·장애가 발생해도 자동 재배정하지 않는다. F10 관련 계좌 대조 자료와 open_orders=0, flat=true 확인 후 명시적으로 RELEASED 처리한다.

이 단계에서 PAPER 에이전트에 전략이 할당된다는 것은 DB 배정 기록만 의미한다. 실제 NautilusTrader 상주 프로세스를 시작하거나 주문을 내지는 않는다. 실계좌 및 live 실행 모드는 API에서 거부한다.

## F05 감사

즉시 관측 이벤트 입력: event_id, event_type, assignment_id, strategy_version_id, epoch, payload. 동일 event_id+동일 payload는 멱등 응답, 다른 payload로 event_id를 재사용하면 409. 미승인 OrderIntent/OrderSubmitted/OrderFilled 관측과 전략 버전·Fencing 불일치는 CRITICAL 감사 기록과 트랜잭션 내 해당 할당의 HALTED 상태를 발생시킨다.

주기적 n8n 감사는 만료된 Lease를 HALTED로 만들고 audit_findings 및 ops_events에 기록한다. 이것은 수신한 이벤트/상태의 독립 감사이지만, **실제 증권사 서버의 주문·포지션 원장을 재조회하는 F10**까지 구현되었다는 뜻이 아니다.

## 설치와 진입점

두 Compose 파일을 함께 사용해 자체 n8n + Postgres17 + Redis + Queue Worker + FastAPI를 구축한다:

    cd n8n
    docker compose -f docker-compose.yml -f docker-compose.backend.yml up -d --build
    docker compose -f docker-compose.yml -f docker-compose.backend.yml exec -T n8n n8n import:workflow --separate --input=/srv/n8n-operation-flows

n8n에서 3개 워크플로의 HTTP Request 노드에 암호화된 HTTP Header Auth Credential을 연결하고, Authorization 헤더에 Bearer + ALPHA_NODE_API_KEY를 설정한 후 게시한다. n8n Cloud 가입은 필요 없지만 로컬 관리자 계정과 인증은 필수다.

환경변수:
- STRATEGY_OPERATIONS_DB_PATH=/data/strategy_operations.sqlite3
- ALPHA_TRADINGVIEW_BASE=내부 TradingView 서비스 주소(HTTPS)
- ALPHA_TRADINGVIEW_TOKEN=해당 서비스가 인증을 요구할 때만 지정
- ALPHA_NODE_API_KEY=내부 인증키(브라우저 및 버전관리 노출 금지)

React 운영 화면은 상단 '전략 풀 · 에이전트 · 독립 감사' 탭에서 전략 목록/검토 대기/에이전트 할당/감사 결과/이벤트 원장을 3초마다 읽는다. 기존 10개 시나리오 실행 및 12개 엔진 노드 편집 탭도 유지한다.

## 검증의 근거와 한계

- Python TestClient는 실물 SQLite CRUD, 전략 버전/원본 해시, Upstream mock adapter, 병렬 할당, Lease, 멱등 감사, HALT를 테스트한다.
- n8n CI는 Docker 실물 n8n/Redis/Postgres를 기동해 13개 워크플로를 가져와 게시하고 실제 Worker/Webhook을 호출한다.
- n8n F01에서 쓰는 TradingView 응답은 **명시적 로컬 HTTP 테스트 서버의 fixture**이므로 실제 TradingView 사이트 수집 성공을 증명하지 않는다.
- n8n F03은 CI에서만 test-only 근거로 전략을 승인한 뒤 PAPER DB 할당을 확인한다.
- n8n F05는 CI에서 만료시킨 Lease를 탐지하고 HALT하는 것을 확인한다.
- Chromium 테스트는 화면 버튼으로 수집/검토/할당/감사를 처리하고 기존 10개 합성 시나리오 회귀를 확인한다.

**미구현:** NautilusTrader PAPER 실전략 실행·브로커 연결·체결 대조·Pine v6 완전 컴파일·실제 11개 엔진 계산의 전체 End-to-End. 기존 n8n 노드 시스템은 실행을 오케스트레이션할 뿐 주문 주체가 아니다. 실거래는 계속 금지한다.
