# n8n 투자 워크플로: 10개 시나리오 실시간 검사

현재 범위: 자체 호스팅 n8n Queue Mode + Python 합성 상태 전이 API + React Flow 실시간 관찰 화면. **실제 매매 및 12개 원본 엔진의 종단간 호출을 수행하지 않습니다.** n8n Sustainable Use License 때문에 본 도커 환경은 개인/내부 관리 테스트에 한정합니다.

## 1. 로컬 Docker 배포

Docker Compose와 Python 3.13을 준비한 별도 Linux/macOS 개발 머신에서:

~~~bash
git switch feature/n8n-scenario-control-plane
cp n8n_scenarios/.env.example n8n_scenarios/.env
python -c 'import secrets; [print(secrets.token_urlsafe(48)) for _ in range(4)]'
~~~

.env의 POSTGRES_PASSWORD, N8N_ENCRYPTION_KEY, ALPHA_NODE_API_KEY, INVESTMENT_SCENARIO_CALLBACK_KEY 네 값을 서로 다른 충분히 긴 랜덤 값으로 변경합니다. 절대로 Git에 커밋하지 않습니다.

~~~bash
python n8n_scenarios/build_workflows.py
docker compose -f n8n_scenarios/compose.yml --env-file n8n_scenarios/.env up -d --build postgres redis api n8n n8n-worker studio
~~~

http://127.0.0.1:5678 에서 n8n 초기 소유자 관리자 계정을 등록합니다. **n8n Cloud 계정은 필요 없습니다.** n8n v2는 워크플로 import 후 publish를 해야 production Webhook이 활성화됩니다. CLI의 DB 변경은 n8n 재시작 후 적용되므로 다음처럼 진행합니다.

~~~bash
docker compose -f n8n_scenarios/compose.yml --env-file n8n_scenarios/.env stop n8n n8n-worker
docker compose -f n8n_scenarios/compose.yml --env-file n8n_scenarios/.env --profile bootstrap run --rm n8n-import
docker compose -f n8n_scenarios/compose.yml --env-file n8n_scenarios/.env up -d n8n n8n-worker
~~~

n8n Web UI에서 Investment QA 01~10 워크플로가 게시·활성화됐는지 확인합니다.

## 2. 실행 화면

- 시나리오 검사 화면: http://127.0.0.1:5177
- n8n 내부 편집기: http://127.0.0.1:5678
- FastAPI OpenAPI: http://127.0.0.1:8000/docs

화면에서 10개 중 하나를 클릭하고 실행 엔진 n8n 실제 워크플로를 선택한 뒤 시나리오 실행 버튼을 누릅니다.

실행 이벤트는 백엔드 SQLite에 저장되고 0.5초마다 폴링되어 각 노드 대기/실행/성공/실패 표시, 이벤트와 입력/출력, 에이전트/포지션/현금/예약/검증 Job 상태가 변경됩니다.

내부 시험 모드는 정확히 같은 Python 상태 전이를 별도 스레드에서 재생합니다. **n8n 호출이 없으며 n8n 실행 성공으로 보고하지 않습니다.** 두 모드의 run.engine 및 event.origin은 API로 독립적으로 확인됩니다.

## 3. 10개 시나리오

1. 전략 신규 발견과 검증 후 Agent C 할당
2. 기존 v2 거래 중 최신 v3 업데이트·승격
3. Agent A/B 계좌 자금 중복 요구
4. 100주 중 60주 부분체결과 중복 주문 차단
5. Nautilus/Qlib/RLlib 검증 작업 3개 동시 대기·거래 유지 (합성 논리적 동시 진행)
6. 성과 이탈 감사·전략 정지·새 후보 생성
7. 주문 미확정 TIMEOUT과 브로커 상태 대조
8. Worker 장애·fencing token·Agent C 인계
9. 최신 Pine 문법 변환 실패 시 기존 버전 보존
10. 전략 RETIRE 후 가상 Paper 청산·에이전트 해제

각 실행은 내보낸 n8n JSON에 Webhook 1개 + 각 단계별 HTTP Request 노드를 포함합니다. Generator와 Backend는 동일한 scenario_catalog.py를 참조하므로 단계가 다르게 구현될 가능성을 줄입니다.

## 4. 내부 검사 API

브라우저는 ALPHA_NODE_API_KEY를 직접 수신하지 않습니다. Vite 프록시가 서버 측 환경 변수로 Authorization 헤더를 넣습니다.

~~~bash
export ALPHA_NODE_API_KEY="$(grep '^ALPHA_NODE_API_KEY=' n8n_scenarios/.env | cut -d= -f2-)"
SCENARIO_SMOKE_MODE=n8n python scripts/smoke_n8n_scenarios.py
# 실제 n8n Webhook → HTTP Request callback이 10개 시나리오 모두에서 일어났는지 검사
SCENARIO_SMOKE_MODE=n8n python scripts/smoke_n8n_scenarios.py 4
# 특정 시나리오만 검사
~~~

동일한 REST API를 직접 호출할 수 있습니다.

~~~bash
curl -H "Authorization: Bearer $ALPHA_NODE_API_KEY" http://127.0.0.1:8000/api/v1/alpha/scenarios/catalog

curl -X POST -H "Authorization: Bearer $ALPHA_NODE_API_KEY" -H "Content-Type: application/json" \
  -d '{"scenario_id":4,"engine":"n8n"}' \
  http://127.0.0.1:8000/api/v1/alpha/scenarios/runs

# 위 응답의 run_id 대입
curl -H "Authorization: Bearer $ALPHA_NODE_API_KEY" \
  http://127.0.0.1:8000/api/v1/alpha/scenarios/runs/RUN_ID

curl -H "Authorization: Bearer $ALPHA_NODE_API_KEY" \
  'http://127.0.0.1:8000/api/v1/alpha/scenarios/runs/RUN_ID/events?after=0'

curl -H "Authorization: Bearer $ALPHA_NODE_API_KEY" \
  http://127.0.0.1:8000/api/v1/alpha/scenarios/runs/RUN_ID/verify
~~~

GET: /health, /catalog, /runs, /runs/{id}, /runs/{id}/events, /runs/{id}/verify.
POST: /runs, /runs/{id}/cancel.
Private n8n callback only: POST /internal/runs/{id}/steps/{step_id}, X-Scenario-Callback-Key required.

## 5. n8n 연결 메커니즘

- Python API가 고유 run_id를 만들고 내부 n8n Webhook으로 트리거를 발행합니다.
- 10개 n8n JSON 각각에 별도 POST Webhook이 있습니다.
- 실제 n8n HTTP Request 노드가 같은 run_id의 다음 step_id를 Backend private callback으로 보냅니다.
- Backend는 단계 순서·인증·금융 합성 상태 불변조건을 검사하고 실행 결과를 SQLite에 원자적으로 기록합니다.
- 동일 단계 중복 콜백은 한 번만 반영하고, 건너뛴 단계는 409로 거부합니다.
- 마지막 단계가 끝나면 6개 전역 불변조건과 시나리오별 후조건을 검증합니다.
- 실거래 송신 수 live_orders_sent가 0인지 강제 검증합니다.

## 6. 중요한 기술·보안 한계

n8n 2.x는 보통 표현식에서 환경변수 접근을 차단합니다. 이 **로컬 관리자 전용 테스트 환경에서만** 워크플로 콜백 키를 전달하기 위해 N8N_BLOCK_ENV_ACCESS_IN_NODE=false를 설정했습니다. 이 경우 워크플로 편집자는 n8n의 다른 환경변수에도 접근할 수 있으므로 외부 사용자에게 편집 권한을 주거나 이 설정을 공개 서버에 그대로 배포하면 안 됩니다. 추후 n8n Header Auth Credential을 엄격하게 관리한 뒤 환경변수 접근 차단을 다시 활성화해야 합니다.

n8n 기본 PostgreSQL/Redis는 n8n 작업 실행 큐에 사용합니다. 거래 원장, 이벤트 정렬, 에이전트 할당 잠금까지 제공되는 것은 아닙니다. 또한 시나리오의 자금·주문·계좌 값은 전부 합성 이벤트이며 실제 시장 가격이나 NautilusTrader 실주문이 아닙니다.

n8n 워크플로 JSON을 생성하고 Python/React 테스트가 통과했다고 해서 self-host n8n 설치·실행이 검증됐다고 주장하지 않습니다. 실제 워크플로 증거는 SCENARIO_SMOKE_MODE=n8n 검사에서 run.events[].origin이 모두 n8n으로 확인되는 경우에만 성립합니다.

여전히 미완료인 항목: F01~F10 상주 운영 서비스의 실제 이벤트 버스, 원본 Pine 범용 컴파일, 실데이터 12개 엔진 실행, 장시간 Worker 내구성, 실제 브로커 주문·체결·계좌 위험 및 감사 원장, 외부 사용자 대상 n8n 임베딩 라이선스 검토.
