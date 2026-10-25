# n8n 10개 운영 시나리오 실행 센터

## 구성

- n8n/docker-compose.yml: n8n Community + PostgreSQL + Redis + 큐 Worker 자체 호스팅.
- n8n/workflows/scenarios/: 각 시나리오별 n8n JSON 10개. Manual Trigger → POST Start → Wait → GET Status.
- app/alpha_nodes/scenario_simulator.py: **합성 이벤트 기반** 시뮬레이션, SQLite 감사 이벤트 저장.
- app/alpha_nodes/scenario_api.py: 인증을 요구하는 시나리오 시작·상태·이벤트 API.
- investment_studio/src/ScenarioConsole.tsx: 화면에서 클릭하여 실행 단계, 가동 플로우, 노드별 입출력 확인.
- investment_studio/src/InvestmentStudio.tsx: 기존 12개 엔진 137개 함수 + 제어 노드 3개 편집 기능 유지.

## 중요한 실행 범위

**시나리오 10개는 실제 주식/브로커 거래가 아니라 구조 검증용 합성 이벤트**입니다. 12개 네이티브 엔진을 실행하거나 시장에서 데이터를 가져오지 않으며 수익률을 생성하지 않습니다. n8n 10개 JSON은 시나리오 백엔드 작업을 시작하고 조회하는 실제 n8n 구성 파일이지만, 전체 10개 운영 플로우가 실제 서비스와 모두 연결됐다는 뜻은 아닙니다.

## 자체 n8n 실행

n8n 폴더에서 N8N_DB_PASSWORD, N8N_REDIS_PASSWORD, N8N_ENCRYPTION_KEY를 환경변수로 설정한 뒤 docker compose up -d를 실행합니다. 주소는 http://127.0.0.1:5678 입니다. Cloud 가입은 없으나 내부 관리자 계정은 설정해야 합니다. PostgreSQL과 Redis를 사용하며 워크플로 실행은 큐 Worker가 처리합니다.

중요: 제공된 Docker Compose에는 Python 백엔드 컨테이너가 포함되지 않습니다. n8n 네트워크에서 내부 DNS 이름 invest-backend:8000으로 기존 FastAPI 서버가 접근 가능해야 합니다. 배포 환경에 맞게 네트워크와 내부 도메인을 연결해야 합니다.

n8n에서 n8n/workflows/scenarios 폴더의 JSON을 가져온 다음 두 HTTP 노드에 HTTP Header Auth Credential을 지정합니다. 헤더 이름은 Authorization, 값은 Bearer + 서버의 ALPHA_NODE_API_KEY 입니다. 인증키를 JSON 파일이나 브라우저 코드에 넣지 않습니다.

## API

GET /api/v1/alpha/scenarios
GET /api/v1/alpha/scenarios/{scenario_id}
POST /api/v1/alpha/scenarios/{scenario_id}/runs?interval_ms=240
GET /api/v1/alpha/scenarios/runs/{run_id}
GET /api/v1/alpha/scenarios/runs/{run_id}/events?after=0

모든 API는 ALPHA_NODE_API_KEY Bearer 인증을 요구합니다. SCENARIO_DB_PATH 기본값은 /tmp/autonomous_scenario_runs.sqlite3 입니다. 실험 기록을 보존하려면 영속 볼륨에 지정하세요. 프로세스 재시작 후 진행 중이던 작업은 interrupted 상태로 처리합니다.

## React 실행

기존 FastAPI 서비스를 localhost:8000에서 실행한 뒤, investment_studio에서 npm install, npm run dev를 실행합니다. Vite 서버측 Proxy용 INVESTMENT_STUDIO_BACKEND_URL과 INVESTMENT_STUDIO_API_TOKEN을 설정하면 http://127.0.0.1:5177에서 시나리오 화면과 엔진 노드 편집 화면을 선택할 수 있습니다. 실제 프로덕션은 사용자 인증 세션을 처리하는 BFF를 추가해야 합니다.

## 검증의 한계

CI는 10개를 각각 API로 시작·완료·조회하고 이벤트·입력·출력·다음 플로우·인증을 검사하며 React TypeScript/Vite 빌드 및 기존 엔진 API 회귀검사를 수행합니다. n8n JSON 구조도 검사합니다. 이것은 Docker에서 n8n 10개를 실제 import/실행했다는 증거가 아니므로, 별도 n8n 통합 시험의 결과를 구분해야 합니다.

**실거래·모의거래 주문 실행 없음. Pine 변환 및 실제 네이티브 모델 결과 없음.**
