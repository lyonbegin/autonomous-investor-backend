# 주식 TV → HITEL Universal AI: 외부 GitHub API 소비자 매뉴얼

기준: 2026-11-27 / 상태: 주식 저장소 쪽 API 클라이언트(범용 엔진은 변경하지 않음)

## 1. 변경하지 않는 프레임워크

공식 가이드:
https://github.com/lyonbegin/hitel-scribd-runner/blob/feature/hitel-universal-ai-ui-api-20261127/docs/HITEL_UNIVERSAL_AI_PUBLIC_API_GUIDE_KO.md

- 프레임워크 저장소: lyonbegin/hitel-scribd-runner
- 프레임워크 브랜치: feature/hitel-universal-ai-ui-api-20261127
- API 기본 URL: https://api.github.com/repos/lyonbegin/hitel-scribd-runner
- GitHub Pages는 정적 UI이며, 실제 등록·실행·결과 조회는 GitHub REST Contents/Actions API이다.
- Universal engine.py, watchdog.py, notifications.py, universal-ai.yml 및 기존 Scribd 데이터·세션·브랜치를 변경하지 않는다.
- 이전 주식 전용 Chrome/Actions/연구·복구 코드는 새 경로에서 호출하지 않는다. 과거 결과는 삭제하지 않는다.

## 2. 이미 보유한 TradingView 자료를 입력으로 사용

- 원본: research/serial10/source_manifest.json (TV-STRATEGY-4428-SOURCE-20261108-v1)
- 9개 파일: research/serial10/sources/strategies_0001_0500.jsonl부터 strategies_4001_4428.jsonl까지.
- Strategy 4,428개를 재수집하지 않고 순서대로 읽어 CSV와 Universal 프로젝트 JSON으로 변환한다.
- order, TradingView id → record_id, title, url, author, description_preview를 원본 그대로 유지한다.
- description_preview는 전체 설명 전문 또는 Pine 코드가 아니다. 33,890개 Strategy+Indicator 전체 자료와 혼동하지 않는다.
- AI 지시문은 주식·ETF·코인만 A, 선물·외환·옵션은 B, 증거 부족은 미확인으로 출력한다. 검색과 거래 사례를 지어내지 않도록 요청한다.

## 3. 주식 저장소에 구현한 소비자 전용 파일

- stocktv_universal_client.py: prepare / register / activate / dispatch / status / export.
- test_client.py: 네트워크를 사용하지 않는 입력·중복·권한 안전 검사.
- README_KO.md: API 사용 명령, 권한, 한계.

| 명령 | 의미 | 실행 안전 장치 |
|---|---|---|
| prepare | 기존 JSONL → UTF-8 BOM CSV + 분할 project.json | 전체 command=pause, 실전 AI 전송 없음 |
| register | 기존 프로젝트 GET 후 새 ID만 GitHub Contents PUT | 기존 자료 덮어쓰기 거부, pause 필수 |
| activate | project.command만 start로 변경 | 기존 파일 blob SHA 조건, live 권한 확인 인수 필수 |
| dispatch | Actions runs 확인 후 명시적 1회 POST | 활동 중인 실행/동일 handoff 차단; 5xx 자동 재POST 금지 |
| status | 프로젝트·state 조회 | verified_ai_completed와 mock_completed 구분 |
| export | complete와 건수, 원본 ID 수량 검증 후 CSV 저장 | 미완료 파일을 성공 결과로 내보내지 않음 |

GitHub API에서 사용:
- GET/PUT /contents/universal/projects/{project_id}/project.json
- POST /actions/workflows/universal-ai.yml/dispatches
- GET /actions/workflows/universal-ai.yml/runs?branch={branch}
- GET /contents/universal/state/{project_id}/state.json
- GET /contents/universal/state/{project_id}/results.csv
- 선택 이벤트: GET /contents/universal/state/{project_id}/events.json

승인된 GH_TOKEN은 사용자가 제공한 환경 변수로만 전달하고 코드, Git, UI, 로그에 포함하지 않는다.
주식 저장소 자신의 GITHUB_TOKEN이 다른 저장소에 쓰기 권한을 가진다고 가정하지 않는다.

## 4. 로컬 오프라인 변환과 시험

작업 디렉터리는 lyonbegin/autonomous-investor-backend 저장소 루트이다.

    python -m unittest discover -s research/universal_hitel -p 'test_client.py' -v

실제 AI를 전송하지 않고 처음 3개만 합성(mock) 시험용으로 준비:

    python research/universal_hitel/stocktv_universal_client.py prepare --pilot 3 --chunk-size 3 --batch-size 2 --prefix stocktv-pilot-20261127 --provider mock --output research/universal_hitel/generated/pilot

전체 4,428개를 데이터 크기 제한에 맞게 분할 준비:

    python research/universal_hitel/stocktv_universal_client.py prepare --chunk-size 400 --batch-size 10 --prefix stocktv-study-20261127 --provider mock --output research/universal_hitel/generated/mock

위 생성 결과는 모두 pause 상태이다. 850,000바이트 프로젝트 크기, 24,000자/배치 프롬프트, 배치 1~50건 검사를 수행한다. 생성 데이터는 이 주식 저장소 안에서만 관리하고, 승인된 한 프로젝트만 프레임워크 API에 등록한다.

## 5. 오직 엔드포인트로 등록·실행·결과 읽기

    python research/universal_hitel/stocktv_universal_client.py register --project-file research/universal_hitel/generated/pilot/stocktv-pilot-20261127-0001-0003.json

등록은 pause로 이루어지고 AI 전송은 하지 않는다. 이후 mock QA를 승인한 경우:

    python research/universal_hitel/stocktv_universal_client.py activate --project-id stocktv-pilot-20261127-0001-0003

활성화 PUT은 GitHub push 트리거로 universal-ai.yml을 시작할 수 있다. 실행 목록을 먼저 확인하고, 실행되지 않았다는 사실을 충분히 확인한 후에만 추가 명시적 dispatch:

    python research/universal_hitel/stocktv_universal_client.py dispatch --project-id stocktv-pilot-20261127-0001-0003 --confirm-dispatch

    python research/universal_hitel/stocktv_universal_client.py status --project-id stocktv-pilot-20261127-0001-0003

    python research/universal_hitel/stocktv_universal_client.py export --project-id stocktv-pilot-20261127-0001-0003 --output research/universal_hitel/generated/pilot/mock-result.csv

POST 204는 작업 접수만 의미한다. Actions success도 특정 프로젝트의 실제 AI 연구 완료를 뜻하지 않는다.

## 6. 실제 HITEL 연구 실행 조건

1. Universal 엔진이 동작하는 hitel-scribd-runner 저장소에 새 주식 연구용 HITEL Task ID의 GitHub OIDC 생산자 권한과 서버 라우팅, AI Chrome 워커가 승인된 상태여야 한다.
2. 운영자가 HITEL_ALLOW_LIVE=true 활성화를 승인한 상태여야 한다. 이전 stock-tv Task가 다른 생산자 저장소에서도 허용된다고 추정하지 않는다.
3. 기존 mock 프로젝트를 hitel로 덮어쓰지 않고 새 project_id로 생성한다.
4. 준비 시 --provider hitel --task-id 승인된ID --pilot 3 옵션으로 실제 AI 등록 파일을 만들되 기본은 pause.
5. 승인 이후에만 activate --confirm-live-authorized를 통해 시작.
6. 첫 2~5건의 AI 응답, verified_ai_completed, CSV, 중복 방지와 재개를 실제 확인한 후 10건으로 확대.
7. 4,428개 전량은 분할 프로젝트를 하나씩 등록·활성화한다. 별도 오케스트레이터/엔진/워치독을 만들지 않는다.

## 7. 한계 및 성공 기준

- 신규 실제 AI 권한, 브라우저 접근, 4,428개 전체 처리, 33,890개 전체 원장 처리는 현재 이 소비자 코드 커밋만으로 완료되지 않는다.
- 현 Universal 검증기는 JSON key·행수·순서·필드 타입만 확인한다. 거래 사례 사실 확인과 Pine 코드 검증은 자동 보장되지 않는다.
- 기존 범용 watchdog는 실행 종료 후 후속 Actions 연결 방식이며 독립적인 5분 상시 cron 워치독이 아니다. depth 20, no_progress 3의 한계를 존중한다.
- 완료 판정: provider=hitel, status=complete, verified_ai_completed=total, results.csv 원본 record_id 검증을 모두 만족할 것.
- provider=mock은 mock_completed만 증가한다. 실제 AI 완료 건수로 보고하지 않는다.
- GitHub Artifact의 보관 기한과 영구 백업은 별개이다.

이 구현은 프레임워크를 수정하거나 재배포하지 않고 오직 문서화된 GitHub REST 엔드포인트만 소비한다.
