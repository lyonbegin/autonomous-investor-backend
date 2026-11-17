# ChatGPT 단계별 지시 템플릿

## T1_FIRST_GATE
입력: TradingView URL, 목록 메타데이터, 실제 이용 가능한 Pine 원본.
명령: "주식 또는 코인 추세만을 예측하는 전용 전략/지표인지 판단하십시오. 그렇다는 근거가 충분할 때만 TREND_ONLY로 분류하십시오. 그 외 모두 NEXT_RESEARCH로 진행하십시오. 원본 코드 확인 여부와 근거 문장을 밝혀 주십시오."
출력: classification, reason, source_access_status, next_action.

## T2_SEARCH
입력: NEXT_RESEARCH인 전략 1개, 원본 설명/코드, 검색 출처 목록.
명령: "검색은 귀하가 직접 하십시오. 우선 등록된 10개 출처를 살펴보되 관련성이 낮은 출처는 미검색 이유를 적으십시오. 거래구조·상품·경제원리·수학모형·손익기법의 동의어까지 검색하고, 논문 제목/DOI/공식 URL/원문 가능 여부/해당성 근거를 반환하십시오. 관련 논문이 동일한 매매전략임을 가정하지 마십시오."
출력: 검색어, 확인한 검색 출처, 후보 테이블, 중복·미확인 구분.

## T3_CASE_DISCOVERY
입력: 검색 후보와 실제 접근 가능한 각 원문.
명령: "단순 가격 예측·모델 논문인지, 실제 체결·교육용 완전 예제·명시적 백테스트 거래사례인지 분류하십시오. 계약/종목, 관찰시점, 조건, 레그, 수익과 출처를 가능한 한 직접 확인하십시오. 단순 이론을 실제 체결로 바꾸지 마십시오."
출력: case_type, original_source_evidence, disclosed_trade_elements, missing_items.

## T4_GRAPH_BUILD
입력: 한 사례의 원문, 원문 사실 목록, 604 기반 온톨로지 및 `research/ontology/active-auto-extensions.json` 자동 반영 정의.
명령: "모든 구체적 금융 개념을 독립 식별자가 있는 적절한 노드, 상세 속성, 의미 있는 방향 관계로 만드십시오. 기존 온톨로지 개념을 우선 적용하고 누락이 있다면 증거와 함께 확장안을 제시하십시오. JSON 노드·속성·엣지·소스 근거를 반환하십시오."
출력: graph, provenance, unrepresentable_facts, ontology_extension_candidates.

## T5_BLIND_RECONSTRUCT
입력: 그래프 JSON 및 독해용 온톨로지 정의만. ***원문 절대 제공 금지.***
명령: "이 지식그래프만 보고 어떤 거래/연구 사례인지, 자산·상품·모델·수식·판단조건·레그·행동·결과·원문 주장 여부를 완성된 명세로 역복원하십시오. 그래프 밖 지식으로 세부 숫자를 메우지 마십시오."
출력: reconstructed_case, unresolvable_from_graph.

## T6_COMPARE_AND_REPAIR
입력: 원문 기준 사실과 T5의 블라인드 복원 명세. **T5 세션과 별개**.
명령: "원문과 복원 결과를 항목별로 비교하십시오. 각 실패에 대해 누락 노드 ID, 부족한 속성명/값, 빠진 관계 유형/방향, 원문 정보 미추출·미공개 여부를 구별하고 수정안을 작성하십시오. 수정해도 동일한 근거가 유지되는지 검토하고 다시 T4→T5를 수행하도록 지시하십시오."
출력: failure_matrix, graph_patch_proposal, ontology_extension_proposal, full_reversibility_status.

## 반드시 중단할 상황
- 로그인이 필요한 원문을 읽지 못할 때: SOURCE_UNAVAILABLE, 임의 사실 추출 금지.
- 기존 문맥에서 블라인드 세션이 오염되었을 때: RECONSTRUCTION_CONTAMINATED, 새로운 세션에서 재실행.
- 원문 실행 요소가 공개되지 않았을 때: SOURCE_NOT_DISCLOSED. 가역성 결함과 구분.
- 같은 응답을 여러 번 중복 제출할 위험이 있을 때: 전송 성공 여부 확인 전 재전송 금지.


## T7_REBUILD_LOOP (필수)
입력: 직전 SOURCE_COMPARE 결과의 FAIL 항목, 원문 fact register, 기존 604/v7 온톨로지, 신규 정의 후보.
명령: "결손 유형을 SOURCE_NOT_ACQUIRED / SOURCE_NOT_DISCLOSED / EXTRACTION_MISSING / ONTOLOGY_MISSING / MODELING_WRONG / RECONSTRUCTION_WRONG / ORIGINAL_CONFLICT로 판정하십시오. 재모델링이 필요하면 이전 그래프를 폐기 대상으로 표시하고, 누락된 금융 의미가 복원되도록 전체 지식그래프를 다시 생성하십시오. 새로운 독립 ChatGPT 대화에 그래프만 제공해 역재현하고, 원문 비교 단계로 돌아가십시오. 원문에 공개한 모든 필수 사실이 독립 복원되기 전에는 완료하지 마십시오."
출력: 다음 그래프 전체 버전, source-redacted graph input, 복원 결과, 원문 차이, 신규 온톨로지 확장 및 자동 반영 결과, 다음 반복 상태.
**자동 반영:** 원문 사실 전수 복원 + `case` 루트에서 모든 금융 노드 접근 성공이면 실제 그래프에 사용된 노드·속성·관계 정의를 별도 승인 없이 연구용 활성 오버레이에 반영합니다. 중복 용어는 합치고, 정본 604개 정의를 파괴하지 않습니다. 독립 신규 ChatGPT 블라인드 재현이 미실행이면 전체 `FULL_PASS` 표시는 계속 금지합니다.
합격: SOURCE_FACT_COVERAGE_PASS + INDEPENDENT_BLIND_REPLAY_PASS 둘 다 통과. 이외에는 REBUILD_REQUIRED 또는 SOURCE_BLOCKED; 성공으로 보고 금지.
