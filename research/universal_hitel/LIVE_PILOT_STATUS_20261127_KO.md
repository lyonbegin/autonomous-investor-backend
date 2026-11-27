# TradingView 4,428 Strategy → HITEL Universal 실전 프로젝트 착수 기록

## 기준 및 실제 완료
- 확인일: 2026-11-27 KST
- 범용 API: https://github.com/lyonbegin/hitel-scribd-runner/blob/feature/hitel-universal-ai-ui-api-20261127/docs/HITEL_UNIVERSAL_AI_PUBLIC_API_GUIDE_KO.md
- 범용 엔진·watchdog·workflow 미수정. **공식 GitHub Contents 엔드포인트만 이용**.
- 원본: 이 주식 저장소 research/serial10/source_manifest.json + 9개 strategies_*.jsonl
- 4,428개 Strategy의 순번·고유 ID 무결성 확인; TradingView 목록 재수집 없음.
- 최초 실전 프로젝트: stocktv-research-pilot-20261127-0001-0003
- 프로젝트 설정: provider=hitel, task_id=stocktv-universal-20261127, batch_size=1, command=pause
- 주식 쪽 고정 입력: research/universal_hitel/generated/live_pilot/stocktv-research-pilot-20261127-0001-0003.json
- 프롬프트: research/universal_hitel/PROMPT_STOCK_RESEARCH_DETAILED_KO.md
- Universal 측 실제 프로젝트 GitHub Contents API 등록 커밋: 77385516dd6c1764c0db777d0cc24c7a8a494f99
- 원본 전략 ID: 02yfhjiz, 03zgCMqx, 04erUlJM
- 최초 mock API E2E 성공: https://github.com/lyonbegin/hitel-scribd-runner/actions/runs/45921769467
  - mock_completed=3 / 3, verified_ai_completed=0, watchdog success.
- **실제 AI 요청 발송 0건.** 인증되지 않은 프로젝트를 live로 시작하지 않았음.

## 실전 시작이 막힌 외부 조건
현재 서버 main의 chatgpt-android-relay/web/gh_oidc.py에는 TASK_PRODUCER_WORKFLOWS 등록이 다음 세 개뿐이다.
- stock-a: autonomous-investor-backend main / stock-a-task-isolated-chrome.yml
- stock-tv: autonomous-investor-backend main / stock-tv-task-isolated-research.yml
- scribd-18109: hitel-scribd-runner main / hitel-public-ai-corpus.yml

또한 task_worker_isolation.py의 VALID_TASKS는 stock-a/stock-tv/scribd-18109뿐이다.
Universal producer는 hitel-scribd-runner feature/hitel-universal-ai-ui-api-20261127 / universal-ai.yml이므로 현재 새 Task ID로 서명된 요청을 허용한다고 볼 수 없다. HITEL_ALLOW_LIVE=true 운영 설정도 확인되지 않았다.

사용자 요청은 외부 프레임워크 엔드포인트만 호출하는 것이므로, 권한 우회/기존 stock-tv Task ID 임의 재사용/서버 인증 검증 해제/기존 엔진 수정은 하지 않는다.

## 한 원본에 대한 AI 단계 (연구 설계)
1. 원본 ID/title/author/URL/미리보기 확인 및 공개 원문·코드·차트 접근 증거 구분
2. 자산 유형 주식/ETF/코인/선물/외환/옵션/불명과 A/B/미확인 분류 (차트 사용 종목 확인)
3. 전략 메커니즘, 인디케이터·설정값·진입·청산·손절·익절·포지션·시간봉 분해
4. 허용된 실제 AI 검색으로 외부 사례와 시장·날짜·링크 확보, 미검색·미검증은 별도 표기
5. 기존 87개 관계·34개 영역 분류표가 실제 제공되었을 때에만 근거 기반 매핑; 아니면 미확인
6. 지표/조건 조합으로 신규 전략 연구 가설, 실행 규칙, 위험통제, 검증 계획 제안
7. 원본 사실/추론/실증 미완료 엄격 분리, 외부 사실 미검증 데이터는 그 상태로 보존

## 다음 승인 후 실행 방식
1. HITEL 서버 운영자가 새 Task ID를 승인하고, Universal producer의 GitHub OIDC repo/ref/workflow와 전용 worker 및 HITEL_ALLOW_LIVE=true를 설정한 사실을 검증한다.
2. 기존 프로젝트의 변경 가능한 command만 start로 전환한다. **project_id/records/prompt/fields/provider 변경 금지**.
3. Universal workflow push가 기존 GitHub Actions에 등록되었는지 확인; 없을 때만 GitHub Actions dispatch 엔드포인트 1회 사용한다.
4. 첫 3건을 batch_size=1로 순차 진행하고 각각 원본 레코드 ID, 결과 검증, state/status, verified_ai_completed, CSV, 이벤트와 실제 job 증거를 확인한다.
5. 실제 AI 응답이 완료된 뒤에만 4,428개 전체를 12개의 적정 크기 project.json으로 나누어 순차 활성화한다. 외부 원본은 재조회하지 않는다.

## 아직 검증되지 않은 사항
- 실제 HITEL AI의 TradingView 사이트 접근/검색 가능 여부
- AI가 반환한 거래 사례의 실재 여부
- 기존 87개 관계 및 34개 체계의 매칭 (매핑 기준 입력 필요)
- 백테스트·Pine 동등성 검증
- 4,428개 대량 처리 실전 완료

주의: 범용 engine의 verified_ai_completed는 기술적 응답/형식 검증 수치이며 경제·거래 사례의 의미적 정확성까지 보장하지 않는다.
