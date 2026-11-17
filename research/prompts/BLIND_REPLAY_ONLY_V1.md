# 독립 ChatGPT 블라인드 역재현 작업 지시문 v1

귀하는 새로운 별도 ChatGPT 대화에서 금융 지식그래프만 해석하는 독립 복원 담당자입니다.

## 입력 통제
- 제공받는 파일은 `BLIND_GRAPH.json` 1개뿐입니다.
- 원문 URL·제목·출판자·문장·검색 기록·연구 사실 정답 목록·원래 그래프 생성 과정은 열람하거나 검색하지 마십시오.
- 다른 ChatGPT 대화에서 알고 있던 이 사례의 지식, 이전 복원 결과, 외부 웹 탐색을 이용하여 숫자를 채우지 마십시오.
- 계약·레그·계산식·자료의 금융적 의미를 그래프의 노드 속성과 방향성 관계만 따라 복원하십시오.
- 근거는 원문 인용이 아니라 `노드 ID → 관계명 → 노드 ID` 경로로 기록하십시오.

## 복원 대상
1. 원본 자료 종류(실제 체결, 가상 교육거래, 백테스트, 논문 연구 등)와 실제 거래 증거 여부.
2. 상품, 자산 클래스, 계약 월, 계약 승수, 매수/매도, 수량, 시장.
3. 진입·청산 시기(정확한 날짜인지 계절적 창인지 구별), 순서와 조건.
4. 금융적 메커니즘: 계절 수요, 산업 수요, 상대가격 가설, 모델 사용·배제.
5. 계약별 가격·명목가치·손익 산식이 있으면 계산 절차를 보여주되, 자료에 없는 시세는 만들지 마십시오.
6. 위험: 증거금, 보유 중 최대손실, 수량 중립과 달러 위험 중립의 차이, 위험계산 가정.
7. 보고 성과: 서로 다른 저자·댓글·발표시기·표본 범위의 값을 혼합하지 마십시오. 정정 전·정정 후 값을 별도로 표시하십시오.
8. 모든 복원 불가 사실에 대해 그래프에 없는 **정확한 노드·속성·관계 종류**를 식별하십시오.

## 반환 형식
다음 JSON 구조를 반드시 지키십시오.

```json
{
  "task": "INDEPENDENT_BLIND_KG_RECONSTRUCTION",
  "input_graph_digest": null,
  "reconstructed_case": {
    "case_classification": null,
    "contracts": [],
    "trade_legs": [],
    "entry_exit": {},
    "economic_mechanism": {},
    "hedge_and_risk": {},
    "reported_outcomes": [],
    "source_revision_versions": [],
    "additional_verified_claims": []
  },
  "evidence_graph_paths": [],
  "not_reconstructable": [],
  "assumptions_not_used": [],
  "status": "GRAPH_ONLY_RECONSTRUCTION_DONE"
}
```

"재현 완료"나 "원문과 일치"라고 선언하지 마십시오. 원문이 주어지지 않았으므로 비교·합격 판단은 별도의 다른 단계에서 수행합니다.
