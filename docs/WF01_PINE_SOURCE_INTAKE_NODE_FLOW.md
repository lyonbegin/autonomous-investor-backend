# WF-01 Pine Source Intake — n8n 실행 노드 명세

상태: FastAPI 등록/권리 검토 코드 작성, 실 n8n 연결·배포·종단간 검증은 미완료.

## 직렬 노드 및 조건 분기
01 Webhook / Manual Trigger: 원본·출처·권리 증빙 입력
02 Edit Fields: source_id, script_type, pine_version, source_code, author, source_url, rights_evidence 구조 검증
03 IF: 필수 필드 미충족 시 Stop And Error
04 HTTP Request: POST /api/v1/alpha/pine/sources; Bearer credential
05 IF duplicate=true: 기존 버전 확인 후 완료 / false: 신규 버전 추적
06 HTTP Request: GET /api/v1/alpha/pine/sources/{source_id}/versions/{version}
07 IF: sha256, version 확인 및 PENDING_REVIEW 검증
08 Human Review Queue: 작성자, 라이선스, 권리 범위 수동 확인
09 별도 검토자 키로 POST /sources/{source_id}/versions/{version}/rights-review
10 Switch: APPROVED / REJECTED / ERROR
11 APPROVED만 GET /sources/{source_id}/versions/{version}/conversion-input 후 WF-02 전달
12 REJECTED 또는 실패: WF-15 오류·감사 기록 및 작업 종료

## 상태와 불변 조건
- PENDING_REVIEW에서 변환 요청하면 HTTP 403.
- REJECTED도 HTTP 403. APPROVED는 변환 입력 읽기만 허가, PAPER 주문은 불허.
- 동일 source_id+sha256은 중복 등록, 다른 내용은 새 불변 버전.
- 동일 원본 버전에 중복 권리 결정은 HTTP 409.
- 검토자 키 미설정은 HTTP 503, 잘못된 키는 HTTP 403.
- 현재 잠금은 단일 프로세스용이며 다중 워커 경쟁은 추가 트랜잭션 처리가 필요.

## 검수 시나리오
U01 Indicator 등록, U02 Strategy 등록, U03 변환 보류/승인 분기
U10 사용자가 직접 노드 드래그·배치·연결·저장·새로고침 후 재조회
API/DB: 중복 1건, 버전 갱신, 원본 해시 대조, 권리 검토 전 차단, 거절/승인, 재승인 충돌
실행: n8n execution ID, node runData, Python Job ID, 감사 기록의 연결 검증
복구: SQLite 백업 후 재시작, 재조회, 실행 재진입/중복 이벤트 처리

## 현재 범위 제한
정식 Pine AST·의존성 해결·Python 변환·동등성 검증은 WF-02 별도 구현 대상.
승인키는 정식 n8n Credentials 또는 비밀 저장소에만 둘 것.
브라우저 편집기와 정식 n8n 런타임은 현재 분리되어 있으며 이 문서는 실행 성공 증거가 아님.