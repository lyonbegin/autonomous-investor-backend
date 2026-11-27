# TradingView Strategy 사례 조사 — 실제 진행 현황 (2026-11-27 KST)

## 확정 범위
- TradingView 원본 4,428개(고유 ID·순서 검증됨)를 1개씩 조사한다.
- 논문과 논문 내부의 개별 실증/거래 사례를 별도 레코드로 수집한다.
- 현 단계는 외부 거래·실증 사례의 발견/근거 검증/보존만 수행한다.
- 지식 그래프, 신규 전략 생성, 87/34 전략 분류, Pine→Python, 백테스트 개발은 수행하지 않는다.

## 첫 번째 원본: 02yfhjiz
- TradingView: https://www.tradingview.com/script/02yfhjiz-Complex-Single-Trade-Strategy/
- 공개 설명: 단일 포지션, 일반/초기 추적/추적 손절, 네 번의 분할 익절. 전체 Pine 소스 실행 및 원본 전략 거래 내역 재현은 미수행.
- AI 수동 웹 근거 조사: 문헌/연구자료 4건, 그중 HTML 원문 읽은 자료 2건 및 초록·색인만 확인된 후보 문헌 2건.
- 원문 기반 실험/비교 레코드 14건: arXiv 2604.27150의 Table II·III 7개 대표 설정, QuantInsti Sim Yee Kai 2023의 주식/외환 출구 규칙 연구 7개 자료군/구체적 구간. **실계좌 체결 14건이 아님.**
- 사례 수 자체는 한도가 없지만, 현 단계에서 확인된 부분만 저장. has_more=true.
- 검증됨: 고유 case_id 14개, parent_paper_id 연결, paper_count/case_count/paper_case_count/후보수/CSV 열과 행 일치.
- 자료: evidence/02yfhjiz/first_pass_20261127_manual.json 및 first_pass_20261127_manual.csv
- 원문/차트 결과를 직접 확인하지 못한 수치와 PDF 테이블은 임의 추정 금지.
- 실조사 출처: https://arxiv.org/abs/2604.27150 / https://blog.quantinsti.com/optimizing-exit-conditions-project-sim-yee-kai/
- 추가 원문 확인: https://doi.org/10.3390/jrfm11030056 / https://doi.org/10.3390/jrfm19080554

## HITEL Universal API 실행 상태
- 등록 프로젝트: stocktv-cases-20261127-0001-p01-v2
- Universal API 실제 등록 커밋: a527c19cf96a1f92fccc7300bc4ca4b5209c6310
- project.json command=pause, provider=hitel; 실전 AI 요청 제출 0건.
- 등록 트리거 GitHub Actions: https://github.com/lyonbegin/hitel-scribd-runner/actions/runs/45926356355 — run/watchdog 성공이나 AI 완료는 아님.
- 신규 Task ID stocktv-universal-20261127에 대한 서버 생산자 OIDC 워크플로 allowlist와 실제 Chrome worker 등록이 확인되지 않아 안전하게 미활성화.
- 기존 범용 엔진/워치독 파일은 변경하지 않음.
- **상태 판단:** GitHub 등록 성공 + 첫 원본 ChatGPT 직접 조사 부분 완료. Universal 프레임워크의 실전 AI 자동 연구는 미개시.

## 다음 순서
1. 1번 원본 미확인 논문 2편의 실제 원문 표·사례 추가 확인 및 기존 14건 중복 제거.
2. 운영 승인 후 동일 API 프로젝트를 command=start로 활성화하고 실전 AI 실행·응답·저장 상태 검증.
3. 2번 원본 03zgCMqx PROP_Scalper_V2 FINAL, 3번 04erUlJM 순서로 진행.
4. 매 원본에 문헌(중복 제거)과 논문 내부 개별 사례(중복 제거)를 각각 보존.
5. 4,428개 자동 완주나 실전 검색 성공을 현재 입증한 것으로 표시하지 않음.
