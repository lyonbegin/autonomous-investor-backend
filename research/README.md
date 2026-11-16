# TradingView → ChatGPT 전담 금융 지식그래프 연구 (실행 준비판)

이 구성은 ChatGPT가 연구의 전 과정을 직접 수행하도록 하는 지시문과 한 건 단위 작업표를 제공합니다. GitHub Actions는 연구 대상 원본을 선택하고 작업지시 패키지를 생성·보관합니다. Python 검색기·Python 금융 판정기·Python 의미 검증기는 사용하지 않습니다.

## 확정된 입력 집계
2026-11-08 TradingView_Recursive_33890 원본 기준: Strategies 4,428 / Indicators 29,462 / 합계 33,890. 이 집계는 TradingView 전체 전수 확보를 뜻하지 않습니다. 신규 수집 항목의 description은 요약일 수 있고, Pine 전체 소스 확보와 다릅니다.

## 작업 분기
1. ChatGPT가 원본 TradingView 링크·가능하면 Pine 전체 코드·설명을 직접 확인한다.
2. 처음에 **주식 또는 코인의 추세만 예측하는 목적의 전용 전략/지표인지** 판단한다. 그렇다고 명확히 입증되면 TREND_ONLY로 분류해 별도 보관한다. 그 밖의 모든 것(비추세·복합·타 자산·미확정 포함)은 NEXT_RESEARCH로 넘긴다. 추세와 다른 경제적 구조가 섞여 있으면 건너뛰지 않는다.
3. ChatGPT가 승인된 10개 검색 출처에 집중하여 관련 논문·거래사례를 직접 검색한다. 제목/초록만 있으면 사례를 확정하지 않는다.
4. ChatGPT가 원문을 읽고 구체적 사례인지 구분한다: 실제 체결 / 교육용 거래 예제 / 백테스트 거래 명세 / 모델 연구 / 단순 이론 또는 미확인.
5. 확정된 거래사례를 기존 604개 출현 항목 기반, 고유 468종 + 승인된 확장 정의를 사용해 지식그래프로 구성한다. 구체적인 금융 개념을 Rule의 자유문장 하나로 뭉개지 않는다.
6. 별도 ChatGPT 대화에 **원문과 정답 없이 그래프만** 전달해 독립 복원한다.
7. 원문을 보는 비교 전용 ChatGPT가 원문과 복원 결과를 대조하고, 필요한 노드·속성·관계 및 필드값의 결손을 구체화한다.
8. 승인되지 않은 온톨로지 확장 후보를 무조건 정본에 합치지 않고, 다음 원본으로 진행할 때 미해결 결손도 보존한다.

## 현재 한계
이 브랜치의 GitHub Actions는 아직 작업지시 패키지만 생성합니다. HITEL Web2API 연동 문서가 제공되지 않아 ChatGPT 자동 호출과 응답 회수는 구현하지 않았습니다. 이에 PREPARED_ONLY를 AI 연구 완료로 계산하지 않습니다. 기존 HITEL 계정 로그인·세션 코드를 이 저장소에 복사하지 않습니다.

## 파일
- research/prompts/COMMON_KG_RESEARCH.md: 공통 지시문
- research/prompts/STAGE_TASKS.md: ChatGPT 단계별 지시
- research/queue/seed.jsonl: 최초 실제 원본 시드
- research/results/02yfhjiz.stage1.json: 첫 번째 원본에 대한 ChatGPT 실제 선별·검색 기록
- .github/workflows/kg-research-prepare.yml: 수동 작업 준비 GitHub Actions

대상 4,428건 전부는 현재 채팅의 원본 ZIP에 있습니다. GitHub에는 1차 시드만 반영되었으며, 아직 4,428건 전수 자동 실행이 아닙니다.
