# AGENTS.md — AUTONOMOUS-INVESTOR Codex 규칙

사용자가 지정한 프로젝트 최상위 개발 지시서는 루트의 `CODEX_MASTER_INSTRUCTION_2026-10-27_ENHANCED.md`입니다. 작업 전에 해당 문서와 `docs/CODEX_PROJECT_HANDOFF.md`를 읽으십시오. 첨부 문서의 과거 서비스·테스트 기록은 현재 상태의 증거로 간주하지 않습니다. 이 파일은 첨부 AGENTS 제안본을 기존 파일이 없는 저장소에 적용한 것입니다. 이후 기존 파일을 무조건 덮어쓰지 말고 비교·병합하십시오.

## 프로젝트와 작업 원칙

- 프로젝트는 신규 생성 대상이 아니다. `lyonbegin/autonomous-investor-backend`와 Railway `AUTONOMOUS-INVESTOR`의 기존 기능을 전수 조사하고 보존한다.
- `main`을 포함한 모든 관련 브랜치를 조사하되 자동 일괄 병합·강제 push·원본 삭제를 하지 않는다. 통합 개발은 별도의 브랜치/워크트리에서 수행한다.
- **12개 투자 엔진 전부 필수:** `app/core/integrations.py`의 `SPECS` 원본을 기준으로 엔진과 저장소/버전을 검증한다. 소스 존재·설치·실행·통합 성공을 명확히 구분한다.
- **노드 UI는 n8n 원본 에디터**를 사용한다. n8n을 흉내 낸 React Flow 편집기를 새로 만들지 않는다. 기존 `InvestmentStudio.tsx`는 무단 삭제하지 않고 별도 레거시 DAG 기능으로 분류한다.
- n8n 실제 실행, Python 합성 10개 시나리오, 12엔진 연구 DAG, PAPER, 실거래는 각각 별개의 상태로 보고한다.
- TradingView·AlphaForge는 기능 참고 대상으로 취급한다. 라이선스/약관/저작권/데이터 출처를 준수하고 Pine `indicator()`와 `strategy()`를 구분한다.
- Python/FastAPI, PostgreSQL, Redis, n8n DB/credentials, Railway, React, 수집기, 전략/에이전트 감사 기능을 보존한다.
- **실거래, 운영 DB 스키마/데이터 변경, 인증 해제, 비밀 회전, 파괴적 삭제 및 production 배포는 승인과 되돌리기 계획을 전제로 한다.** 사용자 승인 없이 수행하지 않는다.
- 공개 UI는 최소한의 GET 및 안전한 합성 시나리오만 허용한다. n8n/실거래/전략 승인/에이전트 변경은 서버에서 인증·인가해야 한다. 버튼 숨김은 보안이 아니다.
- 임시 n8n 프록시 비밀번호가 과거 대화에 노출되었으므로 보안 점검·교체가 우선이다. 평문/해시/토큰/쿠키를 문서/로그/커밋에 남기지 않는다.
- 최근 확인된 크론 이슈는 Horizon 런타임 오류, 회사채 `database is locked`/타임아웃이며, 거시경제는 2026-10-27 정상 수집 기록이 있다. 현재 상태는 다시 검증한다.
- 실행한 테스트의 실제 명령/결과/날짜/환경을 기록한다. 실행하지 않은 테스트를 성공으로 기록하지 않는다. 한국어로 보고한다.

## 작업 개시

1. `git status`, `git remote -v`, `git fetch --all --prune`, `git branch -a`, `git log --all --oneline --decorate -50`로 전수 조사.
2. 원본 마스터 지시서 17~25장 및 기존 1~16장을 함께 읽기.
3. `docs/BRANCH_INTEGRATION_MATRIX.md`, `docs/ENGINE_12_INVENTORY.md`, `docs/RAILWAY_SERVICE_INVENTORY.md`, `docs/N8N_WORKFLOW_INVENTORY.md`, `docs/KNOWN_ISSUES.md` 작성/갱신.
4. 변경 전에 source-of-truth 파일, API 계약, Railway 배포 브랜치, DB/볼륨 위험을 확인.
5. 먼저 테스트/스테이징 검증. production 안전성 확인 전에는 실제 주문 경로를 활성화하지 않기.
