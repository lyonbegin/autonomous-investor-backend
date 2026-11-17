# 거래사례 반복 역재현 운영 기록 — 2026-11-17

## 공통 처리 원칙
지식그래프 생성 → 원문/출처 식별정보 분리 → 그래프 전용 입력에서 금융 사실 역복원 → 원문 사실등록부 대조 → 불합격 시 해당 그래프 버전을 폐기 대상으로 기록하고 전면 재구성. 기존의 실제 소스는 삭제하지 않음. 원문에 미공개된 조건·실제 거래기록·가격자료를 만들어 완성으로 표시하지 않음.

**검증 합격 기준은 2개입니다.**
(A) 선정 사실에 대한 그래프 재현: 동작·경제 원인·계약·손익을 금융 경로로 복원.
(B) 별도의 새로운 ChatGPT 문맥에서의 원문 없는 완전 블라인드 역복원과 원문 전체 감사.
두 번째는 아직 자동 실행되지 않음. (A) 통과를 FULL_PASS라고 부르지 않음.

## 1. CME 백금-금 교육용 스프레드
- **공식 원문**: https://www.cmegroup.com/education/courses/understanding-futures-spreads/understanding-intermarket-spreads-platinum-and-gold
- R1 압축형 **불합격**: 계약 승수, 경제 인과관계, 손익 계산 등 상세 요소 누락.
- R2 62노드/91관계 **불합격**: 자동차 수요의 원인→백금 가격→스프레드와 증거금 상계 구조가 서술형으로만 존재.
- R3 67노드/105관계 15/15: 첫 선택 사실 통과. 이후 원문 범위를 재확대해 추가 11개 정보 결손 발견. R3 **재불합격**.
- R4 104노드/174관계 **불합격**: 사례 노드로부터 77개 금융 노드 중 23개가 방향성 그래프 경로로 도달 불가.
- R5 104노드/190관계, 출처 제거 후 금융 77노드 전부 사례 경로에서 도달. 첫 복원은 25/26, 보석/투자 용도 읽기 누락을 **그래프 수정이 아닌 복원 해석 규칙 개선**으로 바로잡아 26/26.
- 실제 거래가 아닌 **교육용 산식 예제**. PL April 2계약×50oz, GC April 1계약×100oz, 원문 가정 손익 +$5,570. 배경 경제·시장 구조는 실제 주문 체결 근거가 아님.
- 파일: `research/rebuild/CME-PL-GC/round-5-rebuilt.graph.json` · `round-5-graph-only-input.json` · `round-5-source-comparison-retry2.json` · `active.json`.

## 2. Chan 계절성 PL-GC 연구
- 원문 2006: https://epchan.blogspot.com/2006/11/trading-platinum-gold-seasonal-spread.html
- 후속 2007-02: https://epchan.blogspot.com/2007/02/platinum-gold-spread-revisited.html?m=1
- 수정 보고 2007-04: https://epchan.blogspot.com/2007/04/recap-platinum-gold-spread-trade.html?m=1
- R1 84노드/109관계: 최초 25개 원문 사실의 장부를 구성. 후속 위험 관련 댓글 2건의 추가 정보 발견으로 **재검증 불합격**.
- 브랜치의 기존 R2 40노드/57관계는 따로 보존하며, 위험·계절 인과관계의 서술형 압축이 남아 있음; `round-2-existing-failure-audit.json`.
- 새로운 R3(`round-3-source-risk-full.graph.json`) **95노드/126관계**, 출처 제거 후 62노드/84관계. 선정 사실 **27/27** 복원.
- **오류주입 8/8 검출**: 계절 진입창, 공적분 배제, 저자 정정 보고기간 연결, 2006년 중간최대손실+증거금 계산, 댓글 작성자 귀속, 계약 승수 등 연결 오류를 의도적으로 주입.
- *중요*: 저자 2006년 평균 +$6,600과 2007년 수정 보고 평균 +$3,064는 **다른 시점·표본 범위의 원문 주장**으로 별개 노드에 남음. 원래 수익 차트를 저자가 잘못 계산했음을 명시. 개별 과거 체결은 미확인.
- *위험*: 2PL/1GC는 100oz/100oz 수량만 일치; **달러 금액과 위험 중립을 보장하지 않음**. 독자의 504일 ATR 댓글 계산 0.87은 1PL/1GC이며 실제 2PL/1GC로 단순 환산하면 약 1.74. 두 비율은 공분산이 없으므로 실제 스프레드 변동성으로 취급하지 않음.
- 파일: `research/rebuild/CHAN-PL-GC/round-3-source-risk-full.graph.json` · `round-3-risk-graph-only-input.json` · `round-3-risk-source-comparison.json` · `round-3-risk-graph-mutation-checks.json` · `active-risk-research.json`.

## 3. 서로 다른 사례의 금융적 관계
- 파일: `research/cross_case/CME_CHAN_PL_GC_shared_hedge_and_differences.graph.json`, **14개 노드/16개 관계**.
- 두 사례 모두 선물 2PL:1GC, 100troy oz 맞춤이라는 물리 수량 원칙을 공유하나, 거래 계절·계약 만기·가격관계·경제적 이유가 다름.
- CME 교육용 단발 손익과 Chan 역사적 백테스트 평균을 성과 우열로 직접 비교하거나 합치지 않음.
- 위험 차원(수량·달러 금액·가격변동성·상관)을 독립 개념으로 유지.

## 현재 활성 상태 및 미해결
- CME: 선택한 26개 사실에 대한 그래프 복원 일치 / 전체 원문 전수 감사와 독립 새 ChatGPT 블라인드 재현 **미완료**.
- Chan: 선택한 27개 사실에 대한 그래프 복원 일치 / 원시 가격, 차트 원본, 실제 체결 확인, 독립 새 ChatGPT 블라인드 재현 **미완료**.
- HITEL Web2API 연동 지침이 아직 제공되지 않아 GitHub Actions의 새 대화 생성 및 독립 연구 요청 전송을 구축했다고 주장할 수 없음.
- 모든 신규 금융 온톨로지 유형은 원래 604건 출현 및 기존 v7 정의와 중복 심사 전까지 제안 상태로 유지.

합격을 선언할 때는 반드시 `SOURCE_FACT_SCOPE_PASS`와 `INDEPENDENT_BLIND_PASS`를 따로 표시합니다. 중간 실패로 전체 연구를 중단하지 않고 다음 버전으로 계속 재구성합니다.
