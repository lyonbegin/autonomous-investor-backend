# Chan 백금–금 계절성 스프레드: 현재 연구 결과표 (2026-11-18)

**판정:** 등록 사실·금융 노드 경로의 자동 가역성 PASS. 통과된 그래프에 사용된 노드·속성·관계 정의는 별도 승인 단계 없이 연구용 활성 온톨로지에 자동 반영되었습니다. 별도 ChatGPT 신규 대화 블라인드 검증, 원문 전체 전수 복원, 브로커 체결 검증은 아직 수행하지 않았으므로 **BLIND_PENDING_NOT_FULL_PASS** 상태를 유지합니다.

## 거래 구조

| 항목 | 현재 분석 | 한계 |
|---|---|---|
| 연구사례 | Ernie Chan의 백금·금 계절성 시장간 선물 스프레드 | 2006 원문 및 2007 후속 글 |
| 포지션 | Platinum PL 7월물 2계약 매수, Gold GC 6월물 1계약 매도 | 시점별 계약년도·체결가격 별도 |
| 기초 수량 | PL 2×50=100 트로이온스 / GC 1×100=100 트로이온스 | 수량 중립일 뿐 달러·변동성 위험 중립 아님 |
| 진입·청산 | 2월 말 진입, 4월 중순 청산 | 고정 날짜·정확한 체결시점 미공개 |
| 손익 계산 | 100×(PL 청산-진입) − 100×(GC 청산-진입) − 총비용 | 비용·당시 각 월물 실제 데이터 미확보 |
| 전략 이유 | 축제 이후 금 장신구 수요의 계절적 둔화, 백금 산업용 수요와 비교 | 경제적 설명이며 확정 차익이 아님 |
| 모델 분류 | 계절적 가격 괴리 가설, 공적분 기반 평균회귀와 구분 | 2007 후속 설명 |
| 거래 증거 | 2006년 paper trade와 2007년 real trading test를 저자가 자체 언급 | 독립 계좌·체결기록은 미확인 |

## 원저자 성과 보고 및 정정

| 항목 | 2006년 최초 발표 | 2007년 4월 저자 정정 | 구분 |
|---|---:|---:|---|
| 연간 평균 손익 | +$6,600 | +$3,064 | 저자가 최초 손익 그래프 계산 오류 인정 |
| 최고 연간 손익 | +$15,400 | +$7,320 | 발표 버전 차이 |
| 최저 연간 손익 | −$3,810 | −$540 | 발표 버전 차이 |
| 최대 보유 중 낙폭 | $10,910 (2000년 이후) | $4,860 (최근 7년) | 관찰기간과 방법이 달라 직접 동일 비교 금지 |
| 역사적 원장증거금 | $743 | 재확인 없음 | 2006 당시 저자 보고값, 현재 마진 아님 |
| 역사적 위험자본 | $11,653 | 재확인 없음 | $743 + $10,910 |
| 2007년 가정 거래성과 | — | 약 +$6,610 | 2월 26일 부근 진입·4월 19일 부근 청산 IF-TRADED 가정 |

## 자동 가역성과 온톨로지 채택

| 대상 | 결과 | 정확한 판정 |
|---|---:|---|
| Chan R7 전체 그래프 | 노드 78 / 관계 170 | 최신 활성 버전 |
| 원문 제거 금융 그래프 | 노드 70 / 관계 133 | 별도 신규 ChatGPT 대화의 결과는 아님 |
| 원문 등록 사실 대조 | **30/30** | 사례 사실목록 구조 복원 PASS |
| 방향성 루트 연결 | **70/70** | 금융 노드 단절 없음 |
| 필수 관계 제거 시험 | **11/11** | 삭제에 따른 결손 검출 |
| 이번 R7 관계 확장 | 7종 | 실제 그래프에서 검증된 신규 필요 관계 |
| 이번 R7 신규 노드·속성 후보 | 0종 | 기존 그래프 속성·유형 재사용 |
| Chan 개별 그래프 사용 정의 | 노드 유형 35 / 소속유형별 속성 200 / 관계명 73 | 기존 항목 포함, 모두 새 유형은 아님 |
| Chan+CME 활성 오버레이 | 노드 유형 54 / 소속유형별 속성 348 / 관계명 122 | 도메인·범위별 관계 시그니처 126종 |
| 별도 ChatGPT 신규 대화 독립 블라인드 | **미실행** | FULL_PASS 아님 |
| 원문 전체 문장·실거래 동일성 | **미검증** | 실제 수익 확정 불가 |

### 운영 파일
- 최신 상태: research/rebuild/CHAN-PL-GC/active.json
- 전체 그래프: research/rebuild/CHAN-PL-GC/round-7-root-connected-20261117.graph.json
- 원문 제거 입력: research/rebuild/CHAN-PL-GC/round-7-root-connected-20261117-graph-only-input.json
- 30/30 비교: research/rebuild/CHAN-PL-GC/round-7-root-connected-20261117-source-comparison-retry2.json
- 관계 제거 11/11: research/rebuild/CHAN-PL-GC/round-7-root-connected-20261117-mutation-checks.json
- 자동 반영 온톨로지: research/ontology/active-auto-extensions.json
- 자동 동기화 코드: research/ontology/sync-auto-adopted.mjs
- Actions 연결: .github/workflows/kg-ontology-auto-adopt.yml (설정 완료, 실행 검증 별도)
- Draft PR: https://github.com/lyonbegin/autonomous-investor-backend/pull/42

### 원문 URL
- https://epchan.blogspot.com/2006/11/trading-platinum-gold-seasonal-spread.html
- https://epchan.blogspot.com/2007/02/platinum-gold-spread-revisited.html
- https://epchan.blogspot.com/2007/04/recap-platinum-gold-spread-trade.html

**최종 판정:** AUTO_ADOPTED_FOR_RESEARCH_ONTOLOGY / SOURCE_FACT_COVERAGE_PASS / INDEPENDENT_BLIND_PENDING / ACTUAL_TRADE_NOT_PROVEN.
