# 주식 투자용 12개 엔진 노드 워크플로 — 실제 구현 명세

2026-10-25 · feature/investment-12-engine-workflow

## 범위

첨부된 ProcureFlow 워크플로 전수 분석의 P0 문제를 방지하기 위한 주식 투자 전용 구현입니다. 원본 AlphaForge 사이트를 REA로 분석한 결과라고 주장하지 않습니다.

**기존 12개 Python 엔진 원본 소스와 137개 기존 함수별 API는 수정/폐기하지 않았습니다.** NautilusTrader가 실제 거래의 단일 주체이며 나머지 11개 엔진은 네이티브 함수 노드를 제공하지만 본 브랜치에서 브로커 주문 제출은 금지되어 있습니다.

### 투자 기능 분해

- NautilusTrader:
  - nautilus.app.bridge.risk_config — 위험 엔진 설정
  - nautilus.app.bridge.execution_config — 실행 엔진 설정
  - nautilus.app.bridge.backtest_engine_config — 백테스트 엔진 설정
  - nautilus.lab.bridge.backtest_node — 백테스트 노드 구성, 현재 운영 실행은 비허용
  - nautilus.app.bridge.market_order / submit_order / submit_market_intent — 개별 함수 노드 목록에만 존재하며 본 워크플로에서는 실행 차단
  - orchestration.orchestration.runtime.plan_rebalance — TargetPortfolio → OrderIntent 계산. 주문 제출 아님
- TradingAgents: 시장 연구 및 토론
- FinRobot V2: 재무·공시 관련 분석
- RD-Agent: 연구 루프
- Qlib: 퀀트 모델·검증
- Chronos: 시계열 예측
- Stable-Baselines3: 정책 학습·추론
- Ray RLlib: 분산 정책 학습·추론
- vectorbt: 포트폴리오 생성 및 신호 백테스트
- FinRL-Trading: 자산 비중
- Riskfolio-Lib: 위험 모형·최적화
- PyPortfolioOpt: 포트폴리오 최적화
- TradingView 서비스와 Quant Lab 기존 기능 20개도 입출력 노드로 유지.

기존 엔진/오케스트레이션 래퍼 함수 117 + 서비스 API 함수 20 = 137개. 운영 제어 노드 control.identity, control.join, control.approval 세 개를 더해 팔레트 140개입니다. **함수 유형(operation_id)과 여러 개 배치 가능한 노드 인스턴스(id)는 분리합니다.**

## 실제 저장 구조

Backend:
- app/alpha_nodes/inventory.py — 실제 Python 기존 함수 시그니처 목록
- app/alpha_nodes/runtime.py — 네이티브 브리지 호출 및 주문 차단
- app/alpha_nodes/investment_flow.py — DAG 실행·저장·감사 로그
- app/alpha_nodes/investment_api.py — 새 워크플로 엔드포인트
- app/main.py — FastAPI 라우터만 추가
- investment_studio/ — 실제 API 노드 팔레트와 React Flow 편집기

SQLite:
- investment_workflows — 워크플로 ID/이름/최신·게시 버전
- investment_versions — 불변 워크플로 JSON 정의
- investment_runs — 시작 시점 버전·그래프 해시·멱등성 키·실행 상태
- investment_node_runs — 각 노드 입력·출력·상태·재시도 횟수
- investment_events — 실행/승인 이벤트

그래프 실행 도중 편집/게시를 변경해도 현재 실행의 snapshot_json은 변하지 않습니다.

## 실행되는 선과 병렬 합류

각 연결선은 source node ID, target node ID, target_input(native 함수 매개변수), output_path(parent 결과 JSON 경로), on_status(success / failed / any), optional, when(조건), transform(제한된 데이터 변환)을 보유합니다. 선은 순서처럼 보이는 UI 장식이 아니라 실제 데이터 전달 계약입니다.

제공 기능:
1. 순환/중복/존재하지 않는 노드·포트 연결 검증
2. 독립 루트의 실제 동시 실행 (기본 최대 3개, 설정 상한 6개)
3. ALL / ANY / QUORUM(n) / ALL_SETTLED 합류
4. 성공/실패 상태 및 데이터 비교 조건에 따른 분기
5. 한쪽 분기 실패 시 필요한 하위 노드만 건너뛰고 독립 노드 계속 실행
6. 최대 2회 재시도(제한된 안전 연산)
7. control.approval 노드에서 멈춘 후 인증된 API를 통한 승인·재개
8. 워크플로 신규 생성/수정 새 버전/조회/게시·고정/실행 이력
9. 실행 시 노드별 입력·출력·실패·부분 성공·이벤트 저장
10. 멱등성 키로 중복 실행 요청 대응

## 실제 API 경로

기존 API:
- GET /api/v1/alpha/projects
- GET /api/v1/alpha/modules
- GET /api/v1/alpha/operations
- POST /api/v1/alpha/modules/{engine}/{source}/{module}/{function}/execute

신규 API:
- GET /api/v1/alpha/investment/node-types
- GET /api/v1/alpha/investment/node-types?engine=nautilus
- GET /api/v1/alpha/investment/examples
- POST /api/v1/alpha/investment/workflows/validate
- POST /api/v1/alpha/investment/workflows
- GET /api/v1/alpha/investment/workflows
- GET /api/v1/alpha/investment/workflows/{workflow_id}?version=2
- PUT /api/v1/alpha/investment/workflows/{workflow_id}
- POST /api/v1/alpha/investment/workflows/{workflow_id}/versions/{version}/publish
- POST /api/v1/alpha/investment/workflows/{workflow_id}/runs
- GET /api/v1/alpha/investment/runs/{run_id}
- GET /api/v1/alpha/investment/runs/{run_id}/events
- POST /api/v1/alpha/investment/runs/{run_id}/nodes/{node_id}/approve

예시 입력: 2개 독립 노드가 값을 출력하고 ALL 합류 노드가 두 값을 수신합니다.

~~~json
{
  "name":"병렬 투자 연구 합류",
  "nodes":[
    {"id":"a","operation_id":"control.identity","arguments":{"value":10}},
    {"id":"b","operation_id":"control.identity","arguments":{"value":20}},
    {"id":"merge","operation_id":"control.join","join":"ALL"}
  ],
  "edges":[
    {"id":"e1","source":"a","target":"merge","target_input":"left","output_path":"result.value"},
    {"id":"e2","source":"b","target":"merge","target_input":"right","output_path":"result.value"}
  ]
}
~~~

POST workflows 결과로 workflow_id를 수신하고 POST workflows/{id}/runs 본문 {"mode":"dry_run","background":false}를 호출하면 노드별 JSON 결과를 받습니다. 승인 노드는 별도 API를 사용해야 후속 노드가 재개됩니다. 위 예시는 거래/수익률 시뮬레이션이 아닌 DAG 연결 검증용 데이터입니다.

## React 편집기 실제 연결

investment_studio/ 에서 설치 후 빌드합니다.

~~~bash
cd investment_studio
npm install
npm run build
~~~

Backend는 Python 3.13과 기존 requirements 준비 후 다음과 같이 실행합니다.

~~~bash
export ALPHA_NODE_API_KEY="server-side-private-token"
export INVESTMENT_FLOW_DB_PATH="/persistent/volume/investment_flows.sqlite3"
uvicorn app.main:app --host 127.0.0.1 --port 8000
~~~

별도 터미널:

~~~bash
cd investment_studio
INVESTMENT_STUDIO_BACKEND_URL="http://127.0.0.1:8000" \
INVESTMENT_STUDIO_API_TOKEN="$ALPHA_NODE_API_KEY" npm run dev
~~~

개발 UI http://127.0.0.1:5177. 실제 API 서버에서 140개 타입을 읽고, 개별 배치/연결/포트 필드 매핑/합류 옵션/JSON 입력을 편집하고 저장·게시·실행·결과·승인 내역을 확인합니다. 서버 토큰을 VITE_* 환경변수나 브라우저 코드에 넣지 않습니다. 프로덕션은 인증 세션을 검증하는 백엔드 게이트웨이가 별도로 필요합니다.

## 검증 범위와 한계

검증: 기존 12개 프로젝트 노출, 137 함수 엔드포인트, 병렬 동시 시작, ALL/ANY/QUORUM/ALL_SETTLED, 조건 분기, 선택 실패, 독립 분기, 데이터 포트, 버전·게시·멱등성, 승인 후 재개, Nautilus 주문 차단, 실제 plan_rebalance 네이티브 래퍼 테스트, React TypeScript 빌드.

아직 미구현/미검증:
- TradingView Pine 완전 Python 변환, Nautilus 전략 실행 동일성
- Nautilus 실거래 브로커 연결/주문 및 체결 이벤트, 계좌 포지션 대조·비상정지
- 11개 모델의 실제 시세·훈련/추론 종단간 검증 및 최종 포트폴리오 실행 정책
- 분산 내구 큐, Worker 재시작 뒤 자동 이어하기, native 객체 핸들의 다중 프로세스 영속성
- 완전한 타임아웃/취소/서킷 브레이커/운영자 RBAC·전자 승인 서명·정기 스케줄
- REA 원본 AlphaForge의 픽셀·행동 단위 검증 및 일치성
- Railway 현재 배포 및 계좌 거래 (수행하지 않음)

**현재 연구 실행 허용 범위는 제한된 read-only 운영 함수이며 137개를 무조건 호출하지 않습니다. 실거래 주문 경로는 계속 금지입니다.**
