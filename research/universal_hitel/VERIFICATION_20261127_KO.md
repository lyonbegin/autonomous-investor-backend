# HITEL Universal AI 외부 API 연동 — 실제 검증 기록 (2026-11-27)

## 1. 작업 범위
기존 HITEL Universal 프레임워크 내부 파일과 워크플로를 수정하지 않고, 주식 저장소 브랜치의 API 소비자만 개발했다.
- 주식 저장소: lyonbegin/autonomous-investor-backend
- 작업 브랜치: feature/stocktv-web2api-fresh-reset-20261121
- 소비자 코드: research/universal_hitel/stocktv_universal_client.py
- 오프라인 시험: research/universal_hitel/test_client.py
- 한국어 매뉴얼: research/universal_hitel/README_KO.md
- 4,428건 분할 사전 점검: research/universal_hitel/generated/project_plan_4428.json

## 2. 원본 검증
기존 연구용 Strategy 원본 JSONL 9개 파일을 GitHub에서 읽어 전수 대조:
- 총 4,428건, 고유 TradingView ID 4,428건, 순번 1~4,428 연속.
- 제목 슬러그 없는 정상 링크 형식 /script/{id}/ 포함 475건 발견. 소비자 URL 검증에만 두 형식을 허용하도록 수정.
- 400개씩 분할하면 12개 project.json 계획. 프로젝트당 UTF-8 JSON 추정 최대 275,945바이트, 10건당 프롬프트 최대 8,773자. 문서 제한 850,000바이트와 24,000자를 모두 통과.
- 원본은 공개 제목·URL·작성자·설명 미리보기이다. Pine 코드나 상세 전문이 확보되었다고 주장하지 않는다.

## 3. 실제 GitHub Contents API 프로젝트 시험
대상 GitHub: lyonbegin/hitel-scribd-runner
브랜치: feature/hitel-universal-ai-ui-api-20261127
프로젝트 ID: stocktv-pilot-20261127-0001-0003

- 주식 브랜치에 실제 첫 3개 원본의 pilot JSON 및 UTF-8 BOM CSV 저장.
- Universal의 문서화된 프로젝트 파일 경로에 pause/mock 설정 등록: 커밋 1d1c53c9452f9a11dbfdecd931ca28bd5ae6a1c7.
- 동일 프로젝트 command만 start로 변경: 커밋 f8a9c3b625b34f446016854c9afde4e9417f1dcc.
- 등록 push run: https://github.com/lyonbegin/hitel-scribd-runner/actions/runs/45921735657 (success).
- 활성화 push run: https://github.com/lyonbegin/hitel-scribd-runner/actions/runs/45921769467 (run=success, watchdog=success).
- 최종 상태: state.status=complete, provider=mock, total=3, mock_completed=3, verified_ai_completed=0, no_progress=0, batches=2.
- results.csv: 원본 ID 02yfhjiz / 03zgCMqx / 04erUlJM 각 1행 저장.
- events.json: project.started, batch.verified 2회, project.completed.
- Universal engine.py Blob SHA: d2c9626508492627a09641bf5cd5dfcace2442e9.
- Universal watchdog.py Blob SHA: adfe47ed3df333214ca3c304edc125c14ee782b5. 두 파일 모두 변경하지 않음.

## 4. 이 검증으로 아직 입증되지 않은 사항
- 실제 AI 응답 0건. mock은 어떠한 주식 연구 결과도 입증하지 않는다.
- HITEL_ALLOW_LIVE 승인과 새로운 주식 AI Task ID에 대한 HITEL 서버 측 OIDC/워크커 권한은 미확인.
- 4,428건 전체 실전 등록·순차 완료, ChatGPT Web 검색, 외부 거래 사례 사실 검증은 미실시.
- 5분/10분 상시 워치독이 새 Universal에 존재한다는 주장은 하지 않음.
- 이전 주식 전용 연구 결과 및 Scribd 완료 원본은 삭제·변경하지 않음.

다음 단계는 운영자가 승인한 새 Task ID와 라이브 권한 확인 후, 기존 Universal API에 새로운 project_id로 2~5건 실전 smoke를 등록·실행하는 것이다. 엔진 수정이나 별도 주식 전용 Chrome/Actions 실행기 생성은 필요하지 않으며 수행하지 않는다.
