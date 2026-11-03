# WF-01 N01→N02 실제 실행·전달 구현 보고 (2026-11-01)

## 코드 소유권

- 공통 모듈: `lyonbegin/shared-n8n-studio`
  - `server/node_run_store.py`: 범용 `node_runs` / `edge_transfers` 테이블, OUTPUT 원본 저장, 원본 워크플로 연결선 검사, 동일 세션·실행 ID·포트 검증, 단일 사용
  - `server/project_adapter_runtime.py`: 프로젝트가 배포 시 주입한 허용 실행 함수를 조회하고 바인딩 검증. 임의 사용자 Python 실행 불가
  - `server/studio_server.py`: N01 호환 실행 + 범용 실행 `POST /api/studio/nodes/execute`, `GET /api/studio/nodes/transfers`, `GET /api/studio/nodes/graph-state`, `GET /api/studio/nodes/history`
  - `playground/src/App.vue`: 노드 위 ▶ 실행, 상태·전달선 색상, 새로고침 시 저장 결과 표시
  - `playground/src/SharedNodeWorkspace.vue`: 다음 노드에서 앞 노드 OUTPUT 원본 확인, 수동 입력 override, 유효 INPUT 미리보기와 실행 결과 비교
- **주식 프로젝트**: `n8n/editor-adapter/investment_node_adapter.py`
  - `node_binding()` / `node_type()`: N01, N02 허용 타입·Python 함수·코드 버전
  - `execute_node01()`: 입력 수집 종류/제한 검사, 종류/페이지/정렬 설정 OUTPUT 반환
  - `execute_node02()`: N01 OUTPUT **전체 보존**, `page_size`와 `selected_count` 추가 및 업무 검증
  - `test_investment_node_adapter.py`: 전략·라이브러리 계약 테스트
- 투자 워크플로: `n8n/workflows/operations/WF01-latest-{strategy,library}-one.json`
  - N01 = 원본 `manualTrigger` 유지
  - N02 = 원본 `code` 유지, 기존 하드코딩 `max_pages=20,sort=updated_desc` 대신 `$input.all()` 입력 기반 코드로 수정
  - `studioPython` 바인딩은 주식 프로젝트가 정의

## 실제 실행 흐름

1. 노드 N01의 `▶ 실행` → UI는 모달을 띄우지 않음.
2. `POST /api/studio/node01/execute` → 허용된 프로젝트 `execute_node01`을 실행.
3. **같은 DB 트랜잭션에서** `node01_executions` (호환), `node_runs` (공통), `edge_transfers` (실제 N01→N02 연결선)에 OUTPUT 전체를 저장.
4. UI가 그래프 상태를 다시 읽어 N01 성공, N01→N02 데이터 준비/연결선 청색, N02 입력 준비로 표시.
5. N02 `⚙ 설정·이력` → SQLite에 저장된 N01 OUTPUT 전체를 읽기 전용으로 표시. 수동 수정 JSON은 **앞 노드 원본을 직접 변경하지 않고** N02 유효 INPUT에만 병합.
6. N02 `▶ 실행` → UI가 N02 대상으로 준비된 전송 이력을 조회해 source_run_id를 지정.
7. `POST /api/studio/nodes/execute` → 서버가 같은 브라우저 SID, 같은 워크플로, 실제 N01→N02 연결선과 아직 사용하지 않은 source_run_id 검증.
8. 원본 N01 OUTPUT 전체 + N02 수동 override → 프로젝트 허용 `execute_node02` 실행.
9. `node_runs`에 N02 INPUT/OUTPUT을 저장하고 N01→N02 전송을 CONSUMED로 변경, N02→N03의 새로운 전송을 READY로 저장.
10. 화면은 N02 실행 성공, N01→N02 사용 완료, N02→N03 입력 준비 표시. **N03은 실행하지 않음.**

### N01 실제 Python OUTPUT의 필드

```json
{
  "kind": "strategy",
  "page": 1,
  "max_pages": 3,
  "max_detail_success": 1,
  "sort": "recent_extended",
  "execution_mode": "ONE_NODE_ONLY",
  "tradingview_requested": false,
  "next_node_executed": false
}
```

### N02의 기본 OUTPUT

위 모든 필드를 보존하면서 `page_size: 50`, `selected_count: 0`을 추가. N02의 수동 입력 `{"page_size":25}`를 별도 버전으로 저장했다면 N02 OUTPUT은 `page_size:25`가 되며, N01 OUTPUT 원본은 보존됩니다.

## API

```http
GET  /api/studio/nodes/transfers?workflow=operations/WF01-latest-strategy-one.json&node_id=wf01-strategy-02
GET  /api/studio/nodes/history?workflow=operations/WF01-latest-strategy-one.json&node_id=wf01-strategy-02
GET  /api/studio/nodes/graph-state?workflow=operations/WF01-latest-strategy-one.json

POST /api/studio/nodes/execute
X-Studio-Node-Run: APPROVED
Content-Type: application/json

{
  "workflow": "operations/WF01-latest-strategy-one.json",
  "node_id": "wf01-strategy-02",
  "source_run_id": "<실제 N01 run_id>"
}
```

경고: 이 API는 **서버가 고정 허용한 프로젝트 함수만** 호출합니다. UI의 Python 코드/URL 초안을 수정하는 것만으로 실행 코드가 변경되거나 외부 요청이 시작되지 않습니다. 테스트용 브라우저 SID는 운영 계정 인증이 아닙니다.

## 범위와 검증

- Railway 투자 공통 에디터 Dockerfile: `n8n/Dockerfile.native-editor-gateway` — 공통 모듈 SHA 고정, `STUDIO_PROJECT_ADAPTER=investment_node_adapter`, 프로젝트 파일 직접 COPY.
- 실제 브라우저 테스트: `shared-n8n-studio/playground/tests/shared-node-edge-transfer-live.spec.js`: 전략/라이브러리 N01→N02 전송, 원본 유지, N02 재실행, N03 대기, 새로고침; 추가로 N02 수동 page_size 25→50 비교.
- 공통 저장소 테스트: `server/test_node_run_store.py` — 전송 경로·세션 격리·중복 사용 차단.
- 주식 저장소 테스트: `n8n/editor-adapter/test_investment_node_adapter.py`.
- **실제 TradingView 목록/Pine 원본 수집, 공식 n8n 엔진 전체 자동 실행, 실거래는 실행하지 않습니다.** N03의 기존 HTTP 경로는 여전히 실제 API와 맞추는 작업이 필요합니다.

## 사용자 테스트

전략: https://investment-n8n-native-editor-production.up.railway.app/?workflow=operations%2FWF01-latest-strategy-one.json

라이브러리: https://investment-n8n-native-editor-production.up.railway.app/?workflow=operations%2FWF01-latest-library-one.json

N01 위 ▶ 실행 → N02 입력 준비 → N02 위 ⚙ 설정·이력에서 원본 확인 → 닫기 → N02 위 ▶ 실행 → N03 입력 준비 → N02 위 ⚙ 설정·이력에서 실제 입력/출력 기록 확인.

실행이력은 브라우저별 SQLite에 저장되며 브라우저 세션이 다르면 조회할 수 없습니다.
