# TradingView 4,428개 전략의 외부 실증·거래 사례만 수집하는 AI 지시문 v1

이번 단계의 유일한 목표는 입력된 TradingView Strategy 1개와 경제적·거래 규칙상 실제 관련성이 있는 **외부 실증 연구, 거래소 연구, 저자 공개 백테스트, 검증 가능한 실거래/모의거래·공개 체결 기록**을 가능한 한 많이 찾아 개별 사례로 저장하는 것입니다. 전략 설계, 신규 전략 개발, 지식 그래프, 87/34 전략 매핑, Python 코드 개발, 차트 작성, 수익성 예측은 절대 수행하지 마십시오.

## 원본 1개 조사
원본 record_id, title, URL, author, description_preview를 먼저 확인합니다. 접근 가능한 경우 TradingView 공개 원문에서 실제 전략의 매수·매도 신호, 손절·익절, 대상 시장, 파생 여부를 파악합니다. 원문 전문을 읽지 못했으면 미리보기 기반이라고 기록하고, 원본에 없는 코드를 짐작하지 마십시오. 원본은 사례를 찾기 위한 검색 단서이며, 결과에 입력 원본 이외의 가상의 거래 내역을 추가하지 않습니다.

## 외부 검색: 검색어와 자산·실제 거래 구조를 다양화
관련성 있는 여러 표현·동의어·상품명·지표·규칙으로 검색합니다. 학술 색인, 논문 원문·DOI, 거래소·공식 연구, 저자 백테스트, 공개 주문·체결 증거, 공개 소스코드 등 여러 채널을 이용합니다. 검색을 실행하지 못한 채널은 접근 실패 또는 SEARCH_NOT_EXECUTED로 분명히 기재합니다. 후보를 찾으면 가능한 원문 본문, 수식, 표, 그림, 실험 방법·데이터를 직접 열어 확인합니다. 검색 결과 요약만 보고 1차 근거 확인 완료라 하지 마십시오. 자료를 여러 경로로 찾았다면 DOI/제목/저자/연도를 기준으로 중복 제거합니다.

## 실제 사례 여부 AI 판정
각 자료가 **입력 원본과 동일한 Pine 전략을 직접 실행한 사례**인지, **동일 경제 메커니즘/매매 규칙을 실증한 독립 사례**인지, **지표만 유사한 약한 연관**인지를 구분합니다. 지표 이름만 비슷하거나 매매 규칙이 없는 일반 설명, 광고, 가상 수익 인증, 데이터·기간·근거가 없는 수익 주장은 확정 사례에서 제외하고 후보 또는 기각으로 보냅니다. '실제 사례'에는 자료의 실험·주문·검증 출처가 확인된 것만 두되, 증거 유형을 실주문 체결/브로커 기록, PAPER, 과거 시세 백테스트, 시뮬레이션, 논문 실증, 가격차 기회 관찰, 교육용 예제로 명확히 구분합니다. 논문 백테스트를 실계좌 매매로 표시하지 마십시오.

## 사례 건수: 최대한 많이, 미리 고정된 상한 없음
출처가 확인된 적합 사례는 1개든 수십 개든 가능한 만큼 독립적으로 반환하십시오. 목표 5건·10건·20건 등 임의의 상한을 만들지 마십시오. 한 번의 답변으로 끝나지 않으면 has_more=true로 표시하고 continuation_query에 이미 확인한 DOI·URL을 제외한 후속 검색 방향을 기록하십시오. 한 번에 출력 가능한 길이/전송 한계를 초과하지 말고 나머지는 다음 프로젝트/패스로 이어서 수집합니다. 찾지 못하면 cases_json은 []이며 근거 없이 사례를 만들어 숫자를 채우지 마십시오.

## 모든 사례의 구조 (cases_json 문자열 안의 JSON 배열)
각 항목은 다음 키를 빠짐없이 포함하십시오:
case_id, source_title, authors_or_organization, publication_year, source_type, original_url, doi, accessed_at_utc, full_text_opened, evidence_location(section/page/table/figure), exact_market_and_instruments, study_period, source_trading_rules, source_reported_outcomes, evidence_kind, relationship_to_tv_script(direct_same_script/independent_matching_mechanism/weak_related), ai_relevance_reason, evidence_status(primary_text_checked/abstract_only/unverified), uncertainty_notes.
원문에 없거나 확인하지 못한 값은 빈 문자열 또는 '미확인'으로 처리하고 사실을 만들어내지 마십시오. source_reported_outcomes는 논문의 주장 수치를 그대로 표시하고 자체 검증 실적이라고 하지 마십시오. 논문의 경제 메커니즘만 확인했다면 진입·청산 수치를 만들지 마십시오. weak_related는 확정 사례가 아니라 후보에 둡니다.

## 추가 출력 필드
- cases_json: 위 조건을 만족한 사례를 전부 담은 JSON 배열의 문자열
- candidate_cases_json: 원문 미확인·관계 약함·검증 대기 등 후보 배열의 문자열 (각 후보는 URL, 사유 포함)
- rejection_log_json: 허위/중복/광고/관계 없음 판정한 자료 배열의 문자열
- search_log_json: 실제 실행한 검색 채널/검색어/실행 시각/찾은 원문 URL/접근 상태/선택 또는 거절 이유 배열의 문자열. 실행하지 않은 검색을 실행했다고 보고하지 마십시오.
- case_count: cases_json 배열 개수와 정확히 일치하는 숫자
- candidate_count: candidate_cases_json 배열 개수와 정확히 일치하는 숫자
- has_more: 아직 접근해야 할 근거 출처나 다른 검색어가 충분히 남아있으면 true
- continuation_query: 후속 검색어/우선 출처/이미 조사한 중복 제외 사항
- research_status: SEARCH_EXECUTED_AND_ASSESSED / SEARCH_NOT_EXECUTED / PARTIAL_SOURCE_ACCESS 중 정확한 상태

형식: 상위 HITEL Universal 엔진이 요구하는 한 레코드당 동일한 key와 정해진 출력 fields만 포함하는 JSON rows. 입력 원본 record_id는 응답에서 바꾸지 않습니다. 1개 원본을 분석하고 사례가 0건이어도 그 사실을 사실대로 기록하십시오.