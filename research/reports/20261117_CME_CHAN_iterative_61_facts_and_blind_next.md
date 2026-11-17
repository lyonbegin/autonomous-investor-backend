# 금융 지식그래프 반복 재생성 · CME/Chan 심화 감사 (2026-11-17)

## 연구목표와 엄격한 범위
TradingView 원본과 실제 금융사례에서 출발한 ChatGPT 연구 엔진의 지식그래프가 **원문 금융 사실을 역으로 재구성**해야 한다. 실패 시 이전 그래프를 패치로 은폐하지 않고 **불합격 이력에 남기고 새로운 완전 그래프 버전을 생성**해 다시 대조한다.

본 보고서는 두 CME 공식 HTML 자료에서 선정한 금융 사실 37개, Ernie Chan 원문/저자 댓글에서 선정한 금융 사실 24개에 대한 결과다. 세 자료의 이미지 원본 전수 복원이나 독립 새 ChatGPT 블라인드 대화는 수행하지 않았다. 원시 거래체결·시세 미확보를 완료로 표시하지 않는다.

## I. CME 백금·금 — 동일 진입, 서로 다른 공식 결과

### 공식 자료
- [CME 강의](https://www.cmegroup.com/education/courses/understanding-futures-spreads/understanding-intermarket-spreads-platinum-and-gold): 3월 2일 진입, 3월 30일 청산; 사례 연도 미기재; 청산 PL 1056.40 / GC 1244.20, 예제 총손익 **+$5,570**.
- [CME 2017 기사](https://www.cmegroup.com/education/articles-and-reports/spread-trading-opportunities-with-precious-metals): 2017-03-02 진입, 2017-03-30 청산, PLJ7/GCJ7; 청산 PL 971.40 / GC 1233.60, 예제 총손익 **−$1,870**.

공통: PL 2계약 매수(50oz/계약), GC 1계약 매도(100oz/계약), 같은 진입가격 988.40/1231.90 USD/oz. **같은 실제 거래라고 간주하거나 한 결과로 정리하지 않는다.**

기사에는 금 청산가격이 1231.90→1233.60으로 **상승**했으나 두 금속이 하락했다는 설명이 있다. 원문 표와 서술 충돌을 `EvidenceConflict`로 보존했다. 원문에서 사용한 `Liquidate GSR @` 표기(금-은 비율을 연상시키는 레이블)도 출처 표기 이상으로 기록했다.

기사의 약 8% 스프레드 확대는 `−243.50→−262.20`으로 계산한 약 **7.68%**와 숫자가 정확히 같은 게 아니라 *반올림한 주장*으로 관계를 분리했다. 58% 마진 상계는 **당시 기사 자료**에서만 인용하며 `2×$1,600+$4,250=$7,450`, `$7,450×(1−0.58)=$3,129`로 복원했다. 이를 현재 증거금이라고 하지 않는다.

### 반복 결과
| 단계 | 결과 | 다음 수정 |
|---|---|---|
| R1→R3 단일 강의 사례 | 15/15 선정 사실 복원, 독립 블라인드 미실행 | 다른 CME 공식 자료의 다른 결과를 발견 |
| R4 두 출처 분기 그래프 | 19/23 복원 | 경제적 원인 2, 증거금 입력 1, 기사 약 8% 1 누락 |
| R5 전면 스냅샷 재생성 | **23/23** 금융 사실 복원 | 전체 문서의 시장구조 배경 감사 |
| R6 확대 그래프 | **37/37** 선정 금융 사실 복원 | 본문 전체/차트 전수·새 독립 ChatGPT 블라인드 남음 |

R6는 **148 노드, 302 관계**이며, 독립 입력용 자료에서는 원문 문서·문단 노드 16개를 제거한 금융 노드 132개·관계 197개를 사용했다. 신규 14개 사실에는 시장 간/캘린더 스프레드 구별, 레깅 위험·세 가지 감소 수단, 금의 안전자산 수요, 2015년 이후 가격관계, 2016년 CME GC/PL 거래량과 2017-08-21 미결제약정이 포함된다.

관련 산출물:
- [R6 전체 그래프](../rebuild/CME-PL-GC/round-6-expanded.graph.json)
- [R6 원문 차단 그래프](../rebuild/CME-PL-GC/round-6-redacted-for-blind.json)
- [R6 금융 그래프 복원](../rebuild/CME-PL-GC/round-6-broad-graph-only-reconstruction.json)
- [37건 대조](../rebuild/CME-PL-GC/round-6-37-fact-comparison.json)
- [현재 별도 분기 상태](../rebuild/CME-PL-GC/active-multisource.json)

## II. Chan 2006 PL/GC 계절성 스프레드 — 작성자 댓글 반영

원문: [Ernie Chan, Trading a platinum-gold seasonal spread](https://epchan.blogspot.com/2006/11/trading-platinum-gold-seasonal-spread.html). 현 환경에서 직접 HTML 열기는 429 제한이 있었고, **정확한 원문 URL의 검색 색인 본문 및 저자 댓글**로 분석했다. 따라서 직접 원문 전체 댓글 페이지 접근 검증을 완료한 것으로 표시하지 않는다.

구조: **7월 PL 2계약 매수 / 6월 GC 1계약 매도**. 매년 **2월 말 무렵** 진입, **4월 중순 무렵** 청산. 정확한 날짜나 원시 체결가 없음. 저자 주장 평균 연간 +$6,600(1995년 이후), 최선 +$15,400, 최악 −$3,810, 최초 보고 증거금 $743. 2006년 백테스트와 모의거래 성공은 작성자 보고이지 독립 실거래 체결 증거가 아니다.

후속 댓글에 등장하는 **2001년 최대낙폭 $10,910(2000년 이후 조사)**와 **최대 필요자금 $11,653=$743+$10,910**을 초기 증거금과 구분했다. **수량 100oz 대 100oz의 일치는 달러 중립/위험 중립을 보장하지 않는다**는 작성자 수정도 저장했다. 2007년 댓글의 금 1계약 $6,650, 백금 2계약 $12,260 발언은 자산가치 단위/자릿수 의심이 있어 임의로 수치를 교정하지 않았다.

| 단계 | 결과 | 다음 수정 |
|---|---|---|
| 기존 v7 단일 그래프 | 작성자 후속 발언의 위험 설명 7가지 결손 | 원문 사실부터 재구성 |
| Chan R2 | 20/24 | 출처 작성일, 1995년 이후, 선행 문헌, 2000년 이후 최대낙폭 기간 표현 결손 |
| Chan R3 | **24/24** | 원문 전수 및 독립 새 ChatGPT 블라인드 남음 |

R3는 **60 노드, 112 관계**. 인용된 Jerry Toepke의 2006년 SFO 글은 본문을 입수한 것으로 표시하지 않고 **서지 참조**로만 유지했다. 2006년 'paper trade'와 2007년 'real trading test' 발언은 불분명한 적용 범위를 `EvidenceConflict`로 기록했으며 실제 체결 확정으로 변환하지 않았다.

관련 산출물:
- [Chan R3 전체 그래프](../rebuild/CHAN-SEASONAL-PL-GC/round-3-rebuilt.graph.json)
- [Chan R3 블라인드 입력](../rebuild/CHAN-SEASONAL-PL-GC/round-3-source-redacted.graph.json)
- [Chan R3 재구성](../rebuild/CHAN-SEASONAL-PL-GC/round-3-graph-only-reconstruction.json)
- [24건 대조](../rebuild/CHAN-SEASONAL-PL-GC/round-3-24-fact-comparison.json)
- [현재 상태](../rebuild/CHAN-SEASONAL-PL-GC/active-author-comments.json)

## III. 사례 간 지식그래프 관계

[Chan–CME 비교 그래프](../cross-case/CHAN_CME_platinum_gold_knowledge_graph.json)에 제안 관계 9개: 기초상품/2:1 계약비율의 공통점과, 만기월(Chan 7월 PL·6월 GC vs CME 4월), 진입 시기, 경제적 원인(금 장신구 계절성 vs 자동차 백금 수요), 성과 증거(저자 백테스트 vs 교육용 가상 손익), 역사적 증거금 기준을 분리했다.

## IV. 신규 온톨로지 후보

[v10 변경 정의](../ontology/v10-CME-CHAN-source-reversibility-delta.json)에 **노드 7종·속성 8종·관계 10종**을 신규 *후보*로 분리했다. v7/v8/v9 기존 후보를 재사용하며, 604개 출현 항목을 덮어쓰거나 승인 없이 정본 수량에 합하지 않는다. 완전한 과거 5개 사례 회귀검사 전에는 Canonical 승인 금지.

## V. GitHub Actions / ChatGPT 작업 전달

- [독립 블라인드용 ChatGPT 지시문](../prompts/INDEPENDENT_FINANCIAL_GRAPH_REPLAY.md)
- [GitHub Actions 준비 워크플로](../../.github/workflows/kg-blind-replay-prepare.yml)

두 사례 중 하나를 선택해 **원문 제외 그래프와 독립 ChatGPT용 지시문만으로 작업 패키지를 생성**한다. **현재는 `PREPARED_ONLY`**이며 HITEL의 실행/문서 전송·응답 수신 규약을 확보하지 않아 ChatGPT 새 대화를 자동 호출하지 못한다. 이를 FULL_PASS나 완료로 보고하지 않는다.

## 다음 합격 조건
독립 ChatGPT 대화에서 그래프만으로 거래구조와 출처 내 충돌을 복원하고, 비교 전용 대화가 37/24건뿐 아니라 추가로 확인한 모든 중요 금융 사실까지 대조해야 한다. 실패라면 그래프 버전을 폐기 대상으로 표시하고 전체를 다시 생성한다. 원문 자체에 없는 체결·시세나 설정 수치를 만들어 넣어 합격해서는 안 된다.
