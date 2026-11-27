# TradingView 실제 거래·논문 사례 수집: 마일스톤 및 사용자 보고 운영 규칙

기준일: 2026-11-27 KST. 기존 HITEL Universal 엔진/워치독/Actions 소스는 수정하지 않음.

## 1. 보고 단위 및 완료 정의
- 대상: 기존 확보한 TradingView Strategy 4,428개 중 개별 원본 `record_id`.
- **50개 원본마다** 누적 보고: 50, 100, 150, 200, ... 4,400개. 마지막 잔여 28개는 최종 완료 시 별도 보고.
- 같은 원본의 검색 2차·3차 패스나 중복 논문/사례는 완료 원본 수를 늘리지 않음.
- provider=hitel, 실제 AI 응답과 결과 필드 검증이 있는 경우만 완료 원본 후보로 인정. mock 제외.
- 한 원본의 `has_more=true`인 조사 회차는 조사 미완료이므로 50개 누적 완료에 포함하지 않음. 가장 마지막 검증된 조사 회차가 `has_more=false`인 원본만 1개로 집계.
- 사건/논문/사례 집계는 papers_json과 cases_json의 원문 근거를 갖춘 레코드 기준. 자동 타입 검사만으로 실증 진위가 보장되지는 않음.
- 4,428개 원본에 0건 사례인 경우도 검색 수행과 0건 확인이 유효하면 진행 완료로 인정하되 검색 미실행은 완료로 포장하지 않음.
- 사례 수에 상한이 없으므로 한 원본에 후속 조사가 남으면 후속 패스로 계속 확인.

## 2. 주요 실행 마일스톤 (기존 API 사건)
- project.started: 작업 시작/전체 원본수
- request.prepared: 전송 전 체크포인트/요청ID 기록
- request.accepted: HITEL 서버 작업 접수(job_id)
- batch.verified: 구조 검증된 AI 결과 증가
- project.pending: 후속 실행 대기
- heartbeat: 실행 중 상태 관측 (상시 타이머가 아님)
- project.paused: 중지
- project.blocked: 오류/무진전 차단 — 즉시 경고
- project.completed: 해당 범용 프로젝트 완료 — 전체 4,428개 완료와 혼동하지 않음
이벤트는 universal/state/{project_id}/events.json에서 event_id로 중복 제거. 상태와 원본별 검증 숫자는 state.json 및 results.csv에서 별도 확인.

## 3. 주식 브랜치에 보존한 구현
- case_milestone_monitor.py: **읽기 전용** 상태/이벤트 조회, 실제 HITEL 결과만 인정하고 고유 원본 50개 단위 보고 판정.
- case_event_api.py: 문서화된 GitHub Contents API만 사용하여 기존 project.json의 notifications 필드 변경(기존 blob SHA 조건), events.json 전송 상태 확인.
- case_webhook_wsgi.py: 주식 쪽에 마운트할 수 있는 HMAC-SHA256 서명 검증, 5분 시각 허용, event_id 중복 차단, SQLite 내구 저장 수신 핸들러. **코드만 커밋**, 서비스에 마운트·배포된 상태 아님.
- test_case_milestones.py / test_case_webhook.py: 오프라인 검증 케이스. 실제 시험 실행 전까지 통과했다고 말하지 말 것.

예시 (실행은 GitHub 연결 권한이 있는 환경에서):

    python research/universal_hitel/case_event_api.py events --project-id stocktv-cases-20261127-0001-p01-v2

    python research/universal_hitel/case_milestone_monitor.py --project-id stocktv-cases-20261127-0001-p01-v2 --last-reported 0

승인된 수신기 배포 뒤에만 notifications.webhook 적용:

    python research/universal_hitel/case_event_api.py configure --project-id stocktv-cases-20261127-0001-p01-v2 --channel webhook --acknowledge-receiver-ready --apply

위 configure는 Universal 원격 엔진을 고치지 않고 **프로젝트 설정만** GitHub Contents API로 갱신한다.

## 4. 외부 알림 연결의 실제 전제
- 공식 HITEL API v0.2는 notifications.channel=none/github_pr/webhook을 지원.
- webhook 모드에서 실제 URL·HMAC 비밀키는 범용 작업 저장소의 Secrets `HITEL_EVENT_WEBHOOK_URL`, `HITEL_EVENT_WEBHOOK_SECRET`에 운영자 권한으로 설정해야 함.
- 주식 수신기는 기존 서비스에 WSGI application을 `/api/stocktv/hitel-events`로 마운트하고 `HITEL_EVENT_WEBHOOK_SECRET`(양쪽 동일한 비밀)과 `STOCKTV_EVENT_DB_PATH`(영속 저장)을 주입해야 함. URL/secret/token을 공개 JSON이나 Git 커밋에 넣지 않음.
- HMAC 검증 및 중복 저장 후 응답 202는 수신기 접수만 의미하며 ChatGPT 대화 메시지 전달 성공을 뜻하지 않음.
- GitHub PR 알림은 승인된 열린 PR과 HITEL_NOTIFY_PR_ALLOWLIST가 요구됨. 확인 시점에 범용 저장소의 열린 PR이 0건이므로 미설정.
- 일반 대화창으로 임의 POST하는 공식 공개 엔드포인트는 가이드에 없음. ChatGPT Work 이벤트 기반 연결은 실제 지원 이벤트·수신 시험이 필요함.

## 5. ChatGPT 측 50개 보고 작업
- 주식 50개 누적 마일스톤에 도달할 때만 알리는 조건부 반복 작업을 ChatGPT 자동 실행 기능에 등록해 활성화.
- 정확히 50개 원본 처리 완료가 되는 순간 즉시 통지하는 웹훅이 **아닌**, 현재 지원하는 **1시간 단위 조건 확인**임.
- 보고에 사용되는 실제 프로젝트 결과가 없으면 완료 숫자를 만들어내지 않음.
- 중대한 장애는 50개 도달 전에도 별도 보고.
- 프레임워크 실서비스 Task ID/OIDC 권한이 미승인인 상태이므로 실제 AI 연구 자동 진전과 사용자 실전 알림 성공은 아직 미확인.

## 6. 현재 확인 상태
- 주식 사례용 등록 프로젝트: stocktv-cases-20261127-0001-p01-v2.
- provider=hitel, command=pause, batch_size=1.
- notifications.channel=none 유지. 모든 중요 이벤트 종류를 프로젝트 설정에 명시했지만, 외부로 보내지는 않음.
- 실제 AI 응답 0건; 기존 mock 3건은 주식 사례 실전 완료에 포함하지 않음.
- 수신기 코드 커밋 / 상태 조회 코드 커밋 / 조건부 ChatGPT 작업 생성까지 완료.
- 실제 외부 webhook 수신·서명 검증 배포·GitHub Secrets 연결·ChatGPT Work 이벤트 트리거는 미완료.
