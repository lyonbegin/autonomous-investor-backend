# 주식 자동화 — 공통 n8n Studio 노드 작업 공간 사용법

## 노드 실행 버튼 UX (공통 v3)

- **노드 위 `▶ 실행`: 모달을 열지 않고 저장된 최신 INPUT으로 허용된 어댑터를 실행합니다. 캔버스가 보이는 상태로 노드가 실행 중/성공/실패 색상과 상태를 표시합니다.** 실행 기록은 서버 SQLite에 남습니다.
- **노드 위 `⚙ 설정·이력`: 사용자가 이 버튼을 명시적으로 눌렀을 때만 노드 작업 공간 모달을 엽니다.** 이때 저장된 실제 실행 OUTPUT과 수정 이력을 조회합니다.
- 모달의 `저장 후 ▶ 다시 실행`은 입력 편집 상황에서 명시적으로 실행 요청하는 별도 동작입니다. 새 모달을 열지 않습니다.
- 이 정책은 공통 UI 동작이며 ProcureFlow 등 실제 어댑터 미연결 노드의 ▶ 실행은 비활성화됩니다.
- 실제 Chromium 검증: https://github.com/lyonbegin/shared-n8n-studio/actions/runs/41229102100 (25/25 통과, Strategy/Library 모두 ▶ 클릭 후 모달 0개 확인).


> 문서 기준: 2026-11-01  
> 소비 프로젝트: `lyonbegin/autonomous-investor-backend` (브랜치 `feature/editor-wf01-canvas-20261029`)  
> **공통 모듈 소유 저장소**: https://github.com/lyonbegin/shared-n8n-studio  
> 공통 UI·서버 검증 커밋: `ae6653a8c4daae5d767c4d9c98b662ffc597a797`  
> 실제 브라우저 회귀: https://github.com/lyonbegin/shared-n8n-studio/actions/runs/41229102100 (25/25 통과)  
> **공통 기능 상세 계약**: https://github.com/lyonbegin/shared-n8n-studio/blob/feature/wf01-canvas-20261029/docs/SHARED_NODE_WORKSPACE_KO.md

## 1. 코드의 소유권과 사용 범위

주식 자동화 서비스는 공통 에디터 소스를 이 저장소에 복제하지 않습니다. `n8n/Dockerfile.native-editor-gateway`의 `SHARED_STUDIO_COMMIT`으로 공통 저장소를 clone·checkout하여 빌드합니다.

| 저장소 | 소유 기능 및 위치 |
|---|---|
| **shared-n8n-studio** | `playground/src/SharedNodeWorkspace.vue`: 입력 JSON·수정 이력·API URL/Python 실행 설정 초안·출력 비교 UI |
| **shared-n8n-studio** | `playground/src/App.vue`: 각 노드 위 `▶ 실행` / `⚙ 설정·이력` 컨트롤, 실행 상태 연결 |
| **shared-n8n-studio** | `playground/src/style.css`: 노드 위 버튼과 VueFlow 클릭/드래그 구분 |
| **shared-n8n-studio** | `server/node_workspace_store.py`: 노드별 SQLite 현재 버전과 이전 이력 |
| **shared-n8n-studio** | `server/studio_server.py`: 공통 노드 workspace REST API |
| **shared-n8n-studio (현행 예외)** | `server/wf01_node_executor.py`: 기존 WF-01 N01 전용 Python 입력 처리 함수. 공통화하지 못한 **투자 전용 호환 실행 어댑터**이며 향후 소비 프로젝트 측으로 이전해야 함 |
| **autonomous-investor-backend** | `n8n/workflows/operations/WF01-latest-strategy-one.json`, `WF01-latest-library-one.json`: 실제 투자 워크플로 데이터, 선택된 노드의 Python 바인딩 정보 |

**두 종류의 편집기 구분:** 이 문서의 공통 노드 작업 공간은 VueFlow 기반 독립 Studio UI입니다. 공식 n8n 2.x Vue 편집기/실행 엔진을 자동으로 바꿔 주거나 n8n에 노드 패키지를 설치하는 기능은 아닙니다. 실제 워크플로 전체 실행은 별도로 검증해야 합니다.

## 2. 현재 연결된 테스트 페이지

- Strategy N01: https://investment-n8n-native-editor-production.up.railway.app/?workflow=operations%2FWF01-latest-strategy-one.json
- Library N01: https://investment-n8n-native-editor-production.up.railway.app/?workflow=operations%2FWF01-latest-library-one.json

처음에는 WF-01의 N01(수집 종류 선택)만 서버의 검증된 Python `execute_node01`을 실행합니다. TradingView의 원본 크롤링이나 n8n 전체 흐름, 실제 거래를 실행하는 것은 아닙니다. 다른 노드 위 실행 버튼은 어댑터 연결 전까지 비활성화됩니다.

## 3. 노드 단위 작업: 화면에서 따라하기

1. Strategy 또는 Library 테스트 페이지를 엽니다.
2. 캔버스에서 N01 노드 위의 **`⚙ 설정·이력`**을 눌러 공통 노드 작업 공간을 엽니다. 오른쪽 Inspector를 열지 않아도 됩니다.
3. `① INPUT JSON`에 실행 입력을 입력합니다. 예: `{"ui_selection":"strategy","requested_detail_limit":1,"max_pages":3}`.
4. **`설정 버전 저장`**을 누릅니다. 이전 입력과 실행 설정은 SQLite `node_workspace_revisions`에 저장되어 덮어쓰지 않습니다.
5. **`저장 후 ▶ 다시 실행`**을 누릅니다. 허용된 N01 Python 실행 함수만 호출합니다. 실제 실행 기록은 별도 `node01_executions`에 저장됩니다.
6. `④ 실제 실행 결과`의 `output_json`, `status`, `duration_ms`를 확인합니다.
7. INPUT JSON의 `max_pages` 값을 `3`에서 `1`로 바꿔 다시 저장·실행합니다.
8. `⑤ 이전 실행과 출력 비교`에서 `max_pages: 3 → 1`이 나타나는지 확인합니다. 두 번의 성공 실행 기록이 있어야 합니다.
9. `② 입력·실행 설정 수정 이력`에서 이전 버전을 선택해 불러오고, 복원된 값을 저장하면 새로운 버전 번호가 생성되는지 확인합니다.
10. 페이지를 새로고침하고 같은 노드에서 입력과 수정 이력이 유지되는지 확인합니다.

**예상 출력 일부** (Python 함수가 만드는 실행 설정, TradingView 수집 데이터가 아님):

```json
{
  "kind": "strategy",
  "page": 1,
  "max_pages": 1,
  "max_detail_success": 1,
  "sort": "recent_extended",
  "execution_mode": "ONE_NODE_ONLY",
  "tradingview_requested": false,
  "next_node_executed": false
}
```

## 4. API URL·Python 코드 수정 방법 — 즉시 실행 아님

노드 위 **설정·이력 → ③ API·Python 실행 설정(초안)**에서 `kind=http`을 선택하여 HTTP method·URL을 수정하거나, `kind=python`을 선택하여 module·function·Python 코드 초안을 수정합니다.

- `설정 버전 저장`은 새 초안과 변경 이유(notes)를 저장하고 버전을 증가시킵니다.
- 저장한 새 URL이나 Python 문자열은 **실행에 적용되지 않으며**, `code_execution_approved:false`입니다.
- 실제 N01을 다시 실행하면 기존에 서버에 등록·검증된 `execute_node01`만 실행됩니다. 입력값 변경으로 출력은 달라질 수 있지만, 편집된 코드가 실행되는 것이 아닙니다.
- 실제 실행 코드 또는 API의 변경이 필요하면 **공통 UI를 바꾸는 수정인지, 투자 프로젝트 어댑터를 바꾸는 수정인지** 구분해 해당 소유 저장소에서 변경합니다. 소스 커밋·코드 해시·권한·입출력 스키마를 검증한 뒤 새 버전을 배포하고 워크플로의 허용 바인딩을 갱신합니다.
- 자격증명, 토큰, 거래키 등은 입력 JSON/설정 초안에 붙여 넣지 않습니다.

## 5. REST API 계약

```http
GET /api/studio/nodes/workspace?workflow=operations/WF01-latest-strategy-one.json&node_id=wf01-strategy-01
GET /api/studio/nodes/workspace/revisions?workflow=operations/WF01-latest-strategy-one.json&node_id=wf01-strategy-01
PUT /api/studio/nodes/workspace
Content-Type: application/json
```

PUT 예제 (실제 요청 본문):

```json
{
  "workflow": "operations/WF01-latest-strategy-one.json",
  "node_id": "wf01-strategy-01",
  "expected_revision": 0,
  "input_json": {
    "ui_selection": "strategy",
    "requested_detail_limit": 1,
    "max_pages": 1
  },
  "execution_draft": {
    "kind": "python",
    "python_module": "wf01_node_executor",
    "python_function": "execute_node01",
    "notes": "입력 제한 범위 테스트"
  }
}
```

저장 응답의 `workspace.revision`이 증가하고, 같은 브라우저의 `/revisions`가 이전 버전을 보관합니다. 다른 탭에서 먼저 저장했으면 HTTP 409 `NODE_WORKSPACE_REVISION_CONFLICT`. `expected_revision`은 실제 GET에서 읽은 값을 넣어야 합니다(예제에서는 첫 저장이므로 0). 이 API는 **노드 실행 API가 아닙니다.**

기존 허용 N01 실행용 내부 테스트 인터페이스는 `POST /api/studio/node01/execute`이고, 유효한 노드 ID와 `X-Studio-Node-Run: N01` 등 검사 조건이 있습니다. 투자 프로젝트의 서버 전용 실행기이므로 일반적인 다른 노드의 실행 API로 사용하면 안 됩니다.

## 6. 업그레이드/테스트/롤백

배포 Dockerfile: `n8n/Dockerfile.native-editor-gateway`의 `SHARED_STUDIO_COMMIT`을 **검증된 공통 저장소 커밋**으로 갱신합니다. 코드를 소비자 저장소에 복사해 따로 수정하지 않습니다.

```sh
# 이 저장소 루트에서, 별도 테스트 환경 기준
docker build -f n8n/Dockerfile.native-editor-gateway -t investment-shared-editor:test .
```

배포 전에 `shared-n8n-studio`의 `server/test_studio_server.py`, `playground/tests/shared-node-workspace-live.spec.js`, `playground/tests/wf01-node01-python.spec.js`를 포함한 검증 결과를 확인해야 합니다.

회귀 증거: https://github.com/lyonbegin/shared-n8n-studio/actions/runs/41229102100 (25/25 Playwright pass). **공통 모듈의 입력·수정 이력·N01 시범 실행**에 관한 검증이며, TradingView 실데이터 수집·프로덕션 n8n 전체 실행 테스트는 아닙니다.

롤백은 Dockerfile에서 직전 검증된 커밋으로 되돌려 재배포합니다. 기존 SQLite 볼륨을 임의 삭제/초기화하지 않습니다. 새 DB 테이블은 이전 버전과 별도로 보존되며, 브라우저 세션 쿠키를 잃으면 다른 세션의 초안을 자동으로 이어 볼 수 없습니다.

## 7. 타 프로젝트와 공통 모듈의 책임 구분

- **공통 개선 요청:** 노드 위 버튼, 수정/복원 UX, JSON diff, 공통 저장 이력, HTTP 규약 개선 → `shared-n8n-studio`.
- **투자 프로젝트만 변경:** TradingView API URL의 실제 검증, Pine 수집/버전 DB, 전략/라이브러리 선택 함수, 실제 Python 실행 어댑터와 권한 → `autonomous-investor-backend`.
- **미완료:** 공통 범용 Python/HTTP runner registry, 임의 코드/URL 승격·승인 워크플로, 공식 n8n 실행기 자동 연결, TradingView 실크롤링.

**수정된 API URL/Python 코드를 단순 저장한 것으로 동작 코드가 교체됐다고 보고하지 않습니다.**
