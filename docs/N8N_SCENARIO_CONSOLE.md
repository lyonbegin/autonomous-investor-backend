# n8n 10개 운영 시나리오 실행 센터 — 실제 Worker 연동

## 이번 단계의 검증된 성과

- 독립 n8n 워크플로 10개를 공식 n8n 2.44.5 컨테이너에 실제로 import하고 publish함.
- 10개 POST Webhook 경로가 n8n DB에 등록됨.
- n8n Webhook → Redis Queue → Worker → 보호된 Python API → 합성 시나리오 엔진으로 전달.
- Webhook마다 실제 run_id를 n8n Respond to Webhook 노드가 돌려줌.
- 각 run의 이벤트를 SQLite에서 조회하여 10개 전부 completed, 모든 단계 기록 확인.
- n8n의 별도 PostgreSQL execution_entity 테이블에서 각 workflow ID별 success 1건씩 확인.
- React 화면에서 'n8n Worker 경유' 혹은 '직접 API 검사'를 선택할 수 있으며 실제 백엔드 상태를 220ms 단위로 polling.
- 공식 기록: https://github.com/lyonbegin/autonomous-investor-backend/actions/runs/40159462912

**매우 중요:** 실행 엔진 연결은 실물이지만 시나리오 내부 주문·시장 데이터·전략 계산은 시나리오별 사전 정의된 **합성 이벤트**입니다. 실제 12개 엔진 계산이나 TradingView Pine 컴파일, 브로커 주문·실체결을 수행한 것이 아닙니다.

## 파일과 분리된 책임

- n8n/docker-compose.yml: 로컬 n8n, PostgreSQL 17, Redis, Queue Worker 5 concurrency.
- n8n/docker-compose.backend.yml: 선택적인 Python FastAPI 내부 백엔드(127.0.0.1:8000)와 SQLite 영속 볼륨.
- n8n/workflows/scenarios/*.json: 10개 import용 JSON. Manual Trigger + Webhook Trigger + HTTP Start + Respond + Wait + HTTP Read.
- n8n/scripts/render_ci_workflows.py: CI에서만 무작위 Bearer 토큰을 임시 JSON에 삽입. 토큰이 Git에 포함되지 않음.
- n8n/scripts/run_real_n8n_e2e.sh: 컨테이너 설치→10개 워크플로 import/publish→실제 webhook/DB 검증.
- n8n/scripts/verify_real_worker.py: 실제 /dispatch API를 이용해 10개 run_id를 수신하고 상태 및 이벤트 검증.
- app/alpha_nodes/n8n_gateway.py: n8n 사용 모드에서 실제 webhook 호출. n8n이 없으면 503, 오류면 502; 직접 API 모드로 자동 대체하지 않음.
- app/alpha_nodes/scenario_simulator.py: 실제 투자 엔진 호출 없이 결정적 합성 이벤트를 SQLite에 저장.
- investment_studio/src/ScenarioConsole.tsx: 상황을 선택해 시작, 각 플로우 상태와 실제 단계 결과를 볼 수 있음.

## 로컬 전체 설치

자체 Docker Engine과 Docker Compose가 있는 Linux/데스크톱 개발 환경에서 다음 두 compose 파일을 함께 사용합니다.

~~~bash
cd n8n
export N8N_DB_PASSWORD='replace-with-long-unique-password'
export N8N_REDIS_PASSWORD='replace-with-another-long-secret'
export N8N_ENCRYPTION_KEY='replace-with-fixed-32-or-more-random-characters'
export ALPHA_NODE_API_KEY='replace-with-long-api-service-secret'
docker compose -f docker-compose.yml -f docker-compose.backend.yml up -d --build
~~~

관리자 접근: n8n은 http://127.0.0.1:5678, FastAPI는 http://127.0.0.1:8000. n8n Cloud 계정은 필요 없지만 로컬 n8n 관리자 계정 설정은 필수입니다. localhost 주소를 공용 인터넷에 직접 노출하지 마세요.

## 10개 워크플로 실제 가져오기 및 활성화

~~~bash
cd n8n
docker compose -f docker-compose.yml -f docker-compose.backend.yml exec -T n8n \
  n8n import:workflow --separate --input=/srv/n8n-workflows
~~~

n8n Editor에서 10개 workflow 각각의 `내부 시나리오 API 시작`과 `상태·노드 실행 결과 조회` HTTP Request 노드에 동일한 **HTTP Header Auth Credential**을 설정해야 합니다. 헤더 이름은 `Authorization`, 값은 `Bearer <ALPHA_NODE_API_KEY>`입니다. 10개 워크플로 모두 편집 내용을 저장하고 게시합니다. CLI로 일괄 게시하는 경우 다음 명령을 사용하고 서버를 재시작합니다.

~~~bash
for n in $(seq -w 1 10); do
  docker compose -f docker-compose.yml -f docker-compose.backend.yml exec -T n8n \
    n8n publish:workflow --id=autonomousScenario$n
done
docker compose -f docker-compose.yml -f docker-compose.backend.yml restart n8n worker
~~~

CLI 게시만으로는 HTTP 인증 자격 증명이 생기지 않습니다. 반드시 관리자 UI에서 암호화된 Credential을 생성·연결하고 저장해야 합니다. 인증 토큰을 원본 Git JSON에 직접 넣지 마세요.

## React 운영 화면

~~~bash
cd investment_studio
npm install
INVESTMENT_STUDIO_BACKEND_URL=http://127.0.0.1:8000 \
INVESTMENT_STUDIO_API_TOKEN="$ALPHA_NODE_API_KEY" npm run dev
~~~

접속: http://127.0.0.1:5177. `10개 운영 시나리오 실행`을 열어 시나리오를 고르고 `n8n Worker 경유`를 선택한 뒤 실행하세요. Webhook → 실제 n8n Worker → Python 실행에서 받은 run_id로 진행률·10개 플로우 상태·노드별 입출력을 확인할 수 있습니다. n8n 설정이 없으면 n8n 모드는 비활성화되며 직접 API 모드를 사용할 수 있습니다.

## 인증된 검사 API

~~~
GET  /api/v1/alpha/scenarios
GET  /api/v1/alpha/scenarios/infra
GET  /api/v1/alpha/scenarios/{scenario_id}
POST /api/v1/alpha/scenarios/{scenario_id}/dispatch?interval_ms=160    # n8n webhook 경유
POST /api/v1/alpha/scenarios/{scenario_id}/runs?interval_ms=160        # direct simulator
GET  /api/v1/alpha/scenarios/runs/{run_id}
GET  /api/v1/alpha/scenarios/runs/{run_id}/events?after=0
~~~

전부 `Authorization: Bearer $ALPHA_NODE_API_KEY`가 필요합니다. 백엔드의 `N8N_INTERNAL_WEBHOOK_BASE`는 `http://n8n:5678` 또는 내부 허용 호스트/HTTPS 주소입니다. n8n 공개 포트 대신 로컬/내부 DNS를 사용합니다.

## 실제 테스트

GitHub Actions `.github/workflows/n8n-scenarios.yml`의 `actual-n8n-queue-worker` 작업이 Docker 4개 컨테이너와 Python API 서버를 띄우고 10개 JSON을 가져온 뒤 등록 Webhook을 검증합니다. 이 검사에서는 CI 임시 API 토큰을 생성한 후 n8n Node HTTP 인증 헤더에 주입하고, 테스트가 종료되면 컨테이너·DB를 폐기합니다. PostgreSQL `execution_entity`에서 10개 성공 실행을 직접 확인합니다.

## 남은 일

1. 실제 F01 전략 증분 수집·F02 적격성 심사·F03 Lease·F04 Nautilus 상주 거래 등 10개 운영 플로우를 실제 서비스 이벤트와 연결.
2. 장시간 Worker 큐의 진짜 백테스트 실행과 감사/거버넌스 정합성 및 장애 복구 검증.
3. n8n 운영자 인증·Webhook 자격증명·외부 포트 보안·백업·개인정보/민감 로그 마스킹 강화.
4. 12개 엔진의 실데이터 종단간 수행과 거래 위험/컴플라이언스 승인. 현재 실제 주문은 금지.

실환경 배포/실거래는 이번 작업에서 수행하지 않았습니다.
