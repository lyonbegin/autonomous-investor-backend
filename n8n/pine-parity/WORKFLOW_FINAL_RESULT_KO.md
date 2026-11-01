# WF-02 노드 흐름과 별도 차트 검증 페이지 연결

## 화면 배치 · 2026-11-01

1. **노드 흐름 작업 화면**: https://investment-n8n-native-editor-production.up.railway.app/?workflow=operations%2FWF02-chart-parity-first-stage.json
2. **좌우 50:50 차트 비교 페이지**: https://investment-pine-parity-review-production.up.railway.app/

**차트는 노드 화면에 상시 노출하지 않습니다.** WF-02에 있는 `▶ 전체 검증 흐름 실행`으로 원본 Pine/실제 TradingView CSV/원본 차트 PNG를 입력해 주식 전용 Python 검증 서비스를 실행합니다. 서버가 실행 ID, Python SVG, Pine 원문, CSV, Python 생성 코드 및 단계별 trace를 보존하고 나면 **마지막 08 최종 확인 노드**의 `↗ 차트 결과 보기` 버튼이 나타납니다.

버튼을 눌러 `https://investment-pine-parity-review-production.up.railway.app/?run=<실제_run_id>`를 새 탭에 열어 해당 **동일 실행**의 TradingView 원본 이미지(왼쪽), Python SVG(오른쪽), 차트 오버레이와 수치 비교를 봅니다. 새로고침 시 마지막 실행 ID를 서버 API로 다시 확인한 뒤에만 버튼을 복원합니다.

## 코드 소유권

| 변경 위치 | 담당 |
|---|---|
| `n8n/workflows/operations/WF02-chart-parity-first-stage.json` | 주식 프로젝트가 입력 필드, 실행 서비스 URL, 마지막 검증 노드, 결과 URL과 단계를 등록 |
| `n8n/pine-parity/server.py` | 프로젝트 전용 Pine/TV CSV 검증 API, 정확한 공유 에디터 Origin 허용 CORS, 결과 원본 보관 |
| `n8n/pine-parity/engine.py` | 실제 제한형 Pine 변환 및 Python 차트 렌더링 |
| `n8n/pine-parity/index.html`, `app.js` | **별도 페이지** TradingView 원본↔Python 시각 비교 |
| `shared-n8n-studio/playground/src/WorkflowRunPanel.vue` | **공통 컴포넌트** — 프로젝트가 정의한 폼/파일 입력을 렌더링. 주식 규칙은 직접 포함하지 않음 |
| `shared-n8n-studio/playground/src/App.vue` | 공통 실행 표시·마지막 노드의 아티팩트 URL 버튼·실행 복원 |
| `shared-n8n-studio/playground/src/investment-adapter.js` | 주식 워크플로 선택 목록 연결. 향후 이것도 프로젝트 데이터로 이전 가능 |

일반 n8n Code/HTTP/IF 노드 카탈로그는 추가하지 않았습니다. 외부 Python 검증 서비스가 실제 단계를 실행하며 공통 VueFlow는 그 **실행 trace를 시각화**합니다. **공식 n8n 엔진에서 기존 WF-02 JSON을 8개 노드로 직접 실행하는 것과는 별개**입니다.

## 구현 범위와 미구현

- 실제 Python 계산, SVG 렌더링, TV CSV 수치 비교, 비교 결과와 실행 ID 저장, 별도 화면 링크: 구현
- 전체 전략 검색·원본 Pine 자동 확보·TradingView 로그인 차트 자동 적용 및 실제 스크린샷/시세의 자동 수집: **미구현**, 현 시점에서는 실제 TradingView 자료를 사용자가 입력
- 지원 가능한 Pine은 이동평균 교차의 제한형 v5/v6 subset. 전면 문법 변환·시각적 자동 PASS는 **미구현**
- CSV 플롯 값이 없거나 이미지가 원본으로 검증되지 않았으면 **최종 동등성 PASS가 되지 않습니다**
- 합성 데이터로 수행하는 GitHub Actions 테스트는 배포 연결과 작업 동작 검증이며, 실제 TradingView 전략 확보 성공 근거로 사용하지 않습니다.
