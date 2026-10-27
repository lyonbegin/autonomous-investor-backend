# AUTONOMOUS-INVESTOR 통합 인수인계

사용자가 지정한 최상위 개발 지시서는 루트 `CODEX_MASTER_INSTRUCTION_2026-10-27_ENHANCED.md`이다. 원본도 docs/CODEX_MASTER_ORIGINAL.md에 보존했다. 원격 main과 기존 work는 그대로 두고 `codex/full-system-integration-20261027`에서 개발한다. 신규 시스템을 생성하지 않았다.

## 첫 통합 현황표

| 구분 | 확인된 구현·경로 | 원본 브랜치 | 현재 증거·실행 여부 | 통합 조치·남은 일 |
|---|---|---|---|---|
| 12개 투자 엔진 | app/integrations, lab/bridges, core/integrations.py | integration-lab / investment-12-engine-workflow | 12개 설치/import/소규모 native demo 성공 L2 | lifecycle 격리·전체 시장 DAG 미완료 |
| Python 백엔드 | app/main.py, 서비스별 entrypoint | public-demo / TradingView / Quant | 122 tests 통과, 두 서비스 Docker 200/401/200 | 서버 인증 보존, 운영 바인딩 필요 |
| TradingView | core/tradingview.py, source_registry.py, browser_worker | tradingview-service | 소스 복원·Docker/API 검증; 운영 수집 미실행 | 실제 수집량·품질·증분 검증 필요 |
| Pine Script | strategy_spec.py, pine_visual.py, NativePineChartControl | quant-lab-control / public-frontend-react | 소스·프론트 빌드 성공 | 전체 라이선스·신호 동등성 미검증 |
| n8n 워크플로 | n8n/workflows 운영3+시나리오10 | real-worker / secure-selfhost / public-demo | 로컬 원본 n8n 큐 13건 DB 성공 L2 | 운영 DB·owner·native editor E2E 미검증 |
| React 프론트엔드 | investment_studio, public_frontend, frontend, public-frontend | UI 관련 4개 브랜치 | 빌드4개·Chromium tests4개 성공 | 기존 아이디어 화면 복원; legacy admin BFF 통합 필요 |
| 전략 에이전트 | operations_core.py, source_registry.py, quant_lab.py | strategy-registry-assignment-audit / TradingView / Quant | 로컬 F03 PAPER Lease 및 F05 감사 성공 | 실제 전략·시장·브로커 검증 미완료 |
| 10개 시나리오 | scenario_simulator + scenario_runtime | ten-scenario / control-plane | 합성 UI10개 + 실제 n8n queue10개 성공 | 내부 합성 상태와 실제 매매 분리 유지 |
| Railway 인프라 | 서비스별 Dockerfile, n8n/railway.*.toml | 여러 배포 브랜치 | 두 이미지 로컬 빌드·인증 smoke 성공 | 최신 운영 서비스 수/배포·스케줄 접근 차단 |
| 데이터베이스 | SQLite Ops/Quant/source/시나리오 + PG/Redis | service/ops/n8n | 별도 로컬 DB와 큐 실행 검증 | 운영 데이터/볼륨 미변경, backup 재조회 필요 |

## 조사와 유지 원칙

21개 원격 heads를 실제 fetch하고 공통 조상, diff, tree, 테스트·모듈 심볼을 비교했다. 공개 데모 계열 이력은 통합 기반으로 보존하고, 갈라진 최신 TradingView/Quant/public UI/API와 이전 어댑터·콜백 제어를 기능별 복원했다. 상세 SHA·채택·충돌은 BRANCH_INTEGRATION_MATRIX.md 및 integration/source-selections.json 참조.

두 scenario API는 경로·ID·실행 계약이 달라 기존 `/alpha/scenarios`를 보존하고 콜백 제어는 `/alpha/scenario-control`로 분리했다. n8n_scenarios의 별도 10개 생성기는 운영 13개 JSON을 덮어쓰지 않는다. 기존 React DAG/AlphaForge 데모도 삭제하지 않았고 원본 n8n 에디터로 오인시키지 않는다.

새 소스/Quant 관리 API는 서버에서 인증하며 public_api가 서버 전용 upstream 토큰을 전달한다. 공개 프론트에 secret을 넣지 않는다. 기존 공개 Caddy allowlist, 실제 거래 차단, 연구·훈련 승인 게이트를 유지한다.

## 증거와 다음 변경 대상

- ENGINE_12_INVENTORY.md: 정확한 12개 이름·refs·모듈·소규모 demo와 한계.
- N8N_WORKFLOW_INVENTORY.md: 13개 정의 ID와 별도 control-plane 계약.
- TEST_AND_DEPLOYMENT_PLAN.md / integration/VALIDATION_EVIDENCE.md: 실제 명령, 성공·실패·미실행, 재현·롤백.
- RAILWAY_SERVICE_INVENTORY.md: 과거 19개 서비스 단서와 현재 미검증 범위.
- KNOWN_ISSUES.md: 외부 접근·기존 시스템 미완료 사항.

다음 단계는 Railway 읽기 연결·네트워크 적용 이후 서비스/DB/workflow/cron을 재조회하고 staging E2E를 검증하는 것이다. 연구 DAG의 분산 lifecycle, 출처·라이선스·Pine 동등성, 수집 안정성, 실행 ID 상관관계는 후속 구현 범위다. 로컬 통합 검증 성공을 전체 시스템 완료·운영 정상·실거래 준비로 보고하지 않는다. Production 배포·DB 변경·자격증명 회전·외부 알림·실거래는 이번 작업에서 실행하지 않았다.

## 추가 구현·사용자 확인 결과

로컬 사용자 확인 단계는 `docs/REVIEW_READY.md`와 `/workspace/review/AUTONOMOUS_INVESTOR_REVIEW.pdf`를 참조한다. 12개 엔진의 소규모 검증용 독립 프로세스 lifecycle, 기존 공개/운영 UI 연결, 원본 n8n 입력·출력 브라우저 확인, 122개 Python 테스트와 13개 브라우저 항목을 완료했다. 기존 운영 화면 HTTP 접근도 재확인했다.
