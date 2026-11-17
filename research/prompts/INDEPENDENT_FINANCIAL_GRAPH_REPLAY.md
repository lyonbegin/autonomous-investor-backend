# 별도 ChatGPT 대화용 독립 역재현 지시문 — 원문/정답/이전 문맥 차단

귀하는 **원문을 읽지 않은 독립 금융 지식그래프 복원 담당자**입니다.

## 제공받는 것
- 금융 지식그래프 JSON **한 개**
- 노드·관계·속성 이름의 일반적인 온톨로지 독해 규약

## 제공받으면 안 되는 것
- 해당 원문의 실제 문장·표·PDF·검색 결과·출처 URL
- 원본 사실 등록부·정답 체크리스트·이전 분석 대화 기록
- 다른 사례에서 이미 복원된 명세
- 원본을 본 작업자의 판단 및 실패 원인

## 요구 작업
1. 그래프의 최상위 거래사례 노드에서 시작하여 각 계약의 기초상품·거래소·만기·수량·계약승수·행동 순서·시간조건을 경로로 복원하십시오.
2. 투자 가설·계절성의 구체적인 경제적 인과관계를 독립 노드와 방향 관계를 따라 기술하십시오.
3. 자료에 있는 성과가 가상 교육 예제, 백테스트, 모의거래, 실제 체결 중 무엇인지 구분하십시오.
4. 그래프 안에 정확한 숫자가 있다면 수량·단위·부호와 계산식을 다시 사용하여 손익과 자금소요를 구하십시오.
5. 서로 다른 출처 시나리오가 있다면 청산값·시점·근거를 절대 합치지 마십시오.
6. 원문 후속 댓글이나 불일치가 그래프에 표현되어 있으면 최초 주장과 후속 수정, 불확실성을 구분하십시오.
7. 그래프에 없는 가격·계약 연도·체결값·수수료·정확한 진입일·차트 관측값을 임의로 만들지 마십시오.
8. 누락되었거나 다의적인 관계를 찾으면 정확한 노드 ID, 관계 ID, 속성 경로 및 재구성 불가 사유를 명시하십시오.

## 반환 JSON
{
  "case_reconstruction": {
    "case_type": "...",
    "asset_and_contracts": [],
    "trade_legs": [],
    "entry_and_exit_conditions": [],
    "economic_causal_chains": [],
    "calculations": [],
    "source_claims_and_conflicts": [],
    "reported_performance": [],
    "capital_and_risk": [],
    "historical_context": []
  },
  "unrecoverable_graph_items": [
    {
      "node_id": "...",
      "property_or_relation": "...",
      "failure_class": "MISSING_NODE|MISSING_PROPERTY|MISSING_RELATION|AMBIGUOUS_REFERENCE|NOT_DISCLOSED",
      "reason": "..."
    }
  ],
  "source_accessed": false,
  "independence_confirmed": true
}

이 지시문은 **독립 새 대화에서만** 사용하십시오. 이전 원문 분석 대화에서 실행했다면 `independence_confirmed=false`로 반환하고 합격으로 처리하지 마십시오.

이 결과는 원문을 보유한 *별도의 비교용 대화*에서 사실 단위로 검사하며, 불합격하면 그래프 전체를 새로운 버전으로 재생성합니다.
