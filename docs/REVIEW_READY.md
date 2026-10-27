# 바로 확인할 수 있는 통합 검증 결과

관측: 2026-10-27T22:22:32+09:00. 기존 구현 통합을 이어서 진행했으며 로컬 실행·브라우저 검증을 완료했다. 운영 배포나 전체 실시장 투자 시스템 완료를 의미하지 않는다.

## 사용자 확인 자료

- `/workspace/review/AUTONOMOUS_INVESTOR_REVIEW.pdf`: 14쪽, 실제 화면과 결과. 명령 입력 없이 열어서 확인.
- `/workspace/review/AUTONOMOUS_INVESTOR_REVIEW.html`: 이미지가 내장된 오프라인 HTML. 외부 서비스 연결 없이 결과 확인.
- `/workspace/review/`: 화면 PNG, 엔진 실제 실행 JSON, n8n DB 성공 이력, 브라우저 검증 JSON.

## 이번에 추가로 완성한 로컬 기능

- 기존 SPECS/probe/DEMOS를 재사용해 12개 엔진의 독립 프로세스 시작·정지·상태·오류·검증 API를 연결했다. 각 엔진의 실제 import, 기존 native demo, 종료, 새 PID로 재시작을 전부 확인했다.
- 시작/데모 시간 제한, 12GiB 주소 공간·180초 CPU 제한, 강제 종료, 비밀 환경변수 비전달을 구현했다. 로컬 manager는 하나의 API 프로세스가 소유한다. 기존 DAG handle/job을 분산시키는 작업은 포함하지 않는다.
- 기존 investment_studio에 한국어 엔진 상태 화면을 추가했다. 원본 n8n 링크·기존 DAG 화면은 유지했다. 공개 모드에서는 시작/정지/검증 버튼을 제공하지 않으며 백엔드 API는 인증을 요구한다.
- 기존 public_frontend를 로컬 공개 API·수집/전략/에이전트 DB에 연결했다. 별도 review mode는 자체 작성 SYNTHETIC 자료라고 표시한다. 보유하지 않은 수익률/검증 결과를 생성하지 않는다.
- 실제 n8n 로그인 후 원본 노드 6개·연결선·성공 실행 이력·노드별 실제 입력과 출력을 브라우저로 확인했다. 설정 영역은 캡처에서 마스킹했다.
- n8n 반복 검증의 DB 재사용 문제를 수정했다. 매 실행 별도 DB 경로를 사용하고, 기존 Compose 프로젝트/점유 포트를 감지하면 건드리지 않는다. worker readiness도 별도로 확인한다.

## 확인 결과

| 대상 | 결과 | 범위 |
|---|---|---|
| Python suite | 122 passed / 2 deprecation warnings | 인증·동시성·시나리오·원본 DAG + 실제 Nautilus worker·timeout·secret 비전달 |
| 12개 엔진 | 12/12 native demo, stop, restart 성공 | CPU의 기존 소규모 demo; 실시장 연구 전체 DAG 아님 |
| 브라우저 | 13개 검증 항목 통과 | 로컬 실제 API/DB + 원본 n8n + 기존 운영 화면 읽기 |
| n8n | 시나리오 10종 + F01/F03/F05 3종 success 기록 | 별도 로컬 n8n Main/Worker/Redis/PostgreSQL, fixture 입력 |
| Caddy | Valid configuration | 엔진 조회 GET만 공개 allowlist에 추가, 관리 POST 제외 |
| TypeScript/Vite | operator/public 빌드 성공 | 기존 4개 앱 빌드도 이전 단계에서 확인 |
| 기존 운영 HTTP | 공개 200, 상태 200, 원본 게이트웨이/REST/API 익명 401 | 읽기만 수행, 운영 설정·DB·주문 변경 없음 |

## 현재 실행 상태와 재현

로컬 검증 API(8000), 소스 API(8002), 공개 API(8006), operator UI(5177), public UI(5178), 원본 n8n(5678), Redis/PostgreSQL 및 12개 native worker를 실제 실행 상태로 유지했다. 이 포트들은 내부 검증용이며 사용자에게 localhost preview URL로 제공하지 않는다. 프로세스는 snapshot 복원 후 다시 시작해야 한다.

세션 상태와 로컬 개발 전용 자격증명은 `/workspace/.onboarding/user-review-20261027-v2/`에 권한 제한하여 저장했다. source checkout, 캡처, 보고서, zip에는 포함하지 않는다. 같은 manifest가 있으면 시작 helper는 기존 프로세스 정보를 덮어쓰지 않는다.

`n8n/scripts/run_real_n8n_e2e.sh`는 독립 프로젝트/비점유 포트/별도 DB를 사용한다. 확인한 세션을 보존하려면 N8N_E2E_RETAIN=1 및 새 N8N_E2E_STATE_DIR을 지정한다. 중복 프로젝트/기존 서비스가 있으면 실패해야 한다. `scripts/start_review_ui.py`는 이 세션의 키를 서버에서 읽어 기존 두 UI를 실행한다. `scripts/verify_review_browser.mjs`는 실제 데이터 응답으로 13개 항목을 확인한다.

## 운영 검증의 경계

기존 운영 화면은 실제로 HTTP 200으로 열렸고 공개 레지스트리 36개 전략·49개 버전·에이전트 0개와 브로커 미연결 상태를 읽었다. n8n 게이트웨이는 익명 접근에 401이다. 직접 Chromium HTTPS는 관리 CA 신뢰 경로 문제로 실패했으며 TLS를 끄지 않았다. 관리 CA로 hostname/TLS를 검증하는 읽기 전용 로컬 프록시로 기존 실제 UI를 렌더링했다. 이것은 이번 코드를 운영에 배포한 증거가 아니다.

Railway 관리 권한, 운영 n8n owner/credentials/DB, Horizon·macro·회사채 최신 적재, 실제 시장 전 엔진 DAG, Pine 원본과의 신호 동등성은 여전히 미검증이다. Production 배포·운영 DB 변경·비밀 회전·실거래는 수행하지 않았다.

## 브라우저 검증 목록

- 통과: 기존 운영 화면과 실제 로컬 API 연결
- 통과: 12개 실제 엔진 상태와 Nautilus 시작·정지·네이티브 검증 UI
- 통과: 브라우저에서 원본 n8n Worker 경유 시나리오 10개 완료
- 통과: 기존 공개 화면 /strategies 실제 API·데이터 표시
- 통과: 기존 공개 화면 /agents 실제 API·데이터 표시
- 통과: 기존 공개 화면 /ideas 실제 API·데이터 표시
- 통과: 기존 공개 화면 /scripts 실제 API·데이터 표시
- 통과: 기존 공개 화면 /markets 실제 API·데이터 표시
- 통과: 공개 전략 검색 필터
- 통과: 인증 후 원본 n8n 에디터에서 실제 6개 노드·연결선 표시
- 통과: 원본 n8n 인증된 실행 이력 API
- 통과: 원본 n8n 성공 실행의 노드별 실제 입력·출력 (연결 설정 영역 마스킹)
- 통과: 기존 운영 URL 브라우저 읽기 확인 (관리 CA로 TLS 검증하는 읽기 전용 프록시 경유, 통합 변경 미배포)
