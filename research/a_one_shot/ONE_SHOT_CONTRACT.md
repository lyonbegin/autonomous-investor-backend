# A그룹 TradingView 자동연구: 1원본 = 1질문 = 1최종 JSON (2026-11-19 개정)

## 확정 제어 흐름
GitHub Actions가 **이미 확정된 A그룹 공식 순번**의 1번 → 2번 → 3번을 읽습니다. A/B 재분류, 무작위 순서, 건너뛰기 금지입니다. 현재 저장소에는 1,814개 전부의 공식 순번 원장이 없으므로 임의로 원장을 생성하지 않습니다.

**한 원본당 HITEL `POST /integrations/v1/public/chat` 딱 한 번**으로 다음을 AI에게 일괄 지시합니다.

1. 해당 TradingView Strategy/Indicator의 실제 공개 내용, Pine 전체 코드 확보 상태, 종목/시간봉/신호·위험·경제적 구조를 확인합니다.
2. 제공된 기존 **87개 전략**, 추가 **12개 전략**, **StrategyIndicator 23,885 연결** 및 실제 온톨로지 정의와 관계를 확인합니다. 미제공·미확보 정의를 꾸미지 않습니다.
3. 관련된 경제적 연구 사례를 **0~N개** 탐색합니다. 5~6개를 강제로 만들지 않으며 실제 거래·교육 예제·백테스트·모델 연구·미확인을 구별합니다.
4. **각 관련 사례별** 출처별 사실 목록 및 경제적 추론을 분리하고, 금융 노드/상세 속성/방향 관계/다중 거래 레그/계약단위가 포함된 전체 지식그래프를 구축합니다.
5. 그래프 기반 **내부 역재현 → 원본 사실별 비교 → 누락 노드·속성·값·엣지와 불일치 원인 판정 → 잘못된 그래프 폐기 → 전체 그래프 다시 생성**을 내부적으로 반복합니다.
6. 사례별 최종 그래프, 내부 복원 명세, 사실별 비교표, 실패 회차·수정이력, 미해결 결손, 온톨로지 확장안과 증거·한국어 보고를 **완전한 JSON 한 개**로만 반환합니다. **중간 단계의 응답을 API로 보내지 않으며**, 사용자에게 추가 답변을 요구하지 않습니다.

GitHub Actions는 `202 Accepted`를 성공으로 간주하지 않고, 받은 `job_id`를 저장한 후 `GET /integrations/v1/public/jobs/{job_id}`를 폴링합니다. `completed`의 `result_text`만 `result.raw.txt`로 그대로 저장하고, JSON 파싱/스키마/원본 ID·순번·사례 수·모든 그래프·원문 비교·검증 판정을 확인합니다. `failed` 또는 전송 불명확 상태는 체크포인트에 보존하고 **자동 재전송하지 않습니다**.

## 결과 JSON 고정 필드
```json
{
  "schema_version":"A-ONE-SHOT-v1",
  "group":"A","source_id":"<TradingView script id>","a_order":1,
  "source_verification":{"pine_verified":false,"pine_sha256":null,"source_access_status":"PREVIEW_ONLY","source_facts":[],"unverified_source_items":[]},
  "case_discovery":{"method":"...","candidates_considered":0,"cases_discovered":0,"cases":[
    {
      "case_id":"<source>-C01","kind":"UNVERIFIED","economic_mechanism":"...",
      "factual_evidence":[],"inferences":[],
      "prior_87_links":[],"prior_12_links":[],"indicator_links":[],
      "fact_register":[],"rounds":[],
      "final_graph":{"nodes":[],"edges":[]},
      "final_reconstruction":{},
      "final_comparison":{"checks":[],"source_coverage_pass":false,"self_check_pass":false},
      "internal_verdict":"BLOCKED","independent_blind_verified":false,
      "unresolved":[]
    }
  ]},
  "summary":{"total_cases":0,"internally_passed":0,"blocked":0,"incomplete":0,"unresolved_claims":[],"overall":"BLOCKED","report_ko":"..."},
  "independent_blind_verified":false
}
```
위 JSON은 **필드 모양 예시**로 실제 사례 또는 완료 결과가 아닙니다. 실제 결과에서는 사례 수·검증 결과를 일치시키고 각 사례 그래프·검증 회차가 빈 채로 합격하면 안 됩니다.

## 합격/진행 규칙
- 원본 **A그룹 공식 순번, TradingView ID**가 검증되어야 합니다.
- 각 관련 사례가 모두 공개된 원본 사실을 구조적으로 재현해야 합니다. 원본 Pine 전문 미확보는 `FULL_SOURCE_PASS`가 아닙니다.
- 내부 실패는 필요한 만큼 전체 그래프를 다시 작성하고, 해결 불가능하면 `BLOCKED`로 명시하며 다음 원본을 자동 진행하지 않습니다.
- **단일 AI 대화 안의 역재현은 자기검증입니다.** 별도 문맥에서 원본을 보지 않은 독립 블라인드 검증으로 거짓 주장하지 마십시오. `independent_blind_verified:false`를 명시하고, 다음 원본 이동 정책에서 이 구분을 유지합니다.
- 완료 응답 `result_text`, `result.json`, `validation.json`, 원본/프롬프트 SHA, `request_id`, `job_id`, 오류 및 상태는 각 원본별 GitHub Actions 아티팩트로 보존합니다.

## 기존 구현에서 폐기해야 할 방식
기존 `research/hitel_a_one_source.py` 및 `research/hitel_a_recover_discovery.py`의 `DISCOVER → GRAPH-R1 → BLIND-R1 → COMPARE-R1 → ...` **각 단계마다 별도 HITEL 메시지를 보내는 로직을 신규 실행 경로에서 사용하지 않습니다.** 기존 아티팩트·요청 ID는 감사 이력으로 보존합니다.

## 준비 단계
현재 공식 A그룹 전수 1,814개 순번 원장이 GitHub 실행 입력으로 연결되지 않았습니다. 원장 확정 전 1번부터 자동 실행했다고 주장하거나 임의 목록으로 대체하지 않습니다. 사용자 요청에 맞는 1원본/1AI호출 실행기와 엄격한 JSON 계약의 검증용 설계·테스트 코드는 별도 ZIP 아티팩트로 제공합니다.

## v7 정본 20항목 전수 연구 JSON 계약 (2026-11-19 추가)

2026-11-11 확정 과업지시서 `STOCK-AUTO-RESEARCH-OUTPUT-CONTRACT-v7.0`의 **정확한 분리**를 준수하십시오. `source_sections_01_to_10`는 원본당 1회, `case_sections_11_to_20`는 발견된 사례마다 1회 작성합니다. 각 항목은 반드시 `section_id, title, status, summary, facts[], evidence_refs[], limitations[], artifact_paths[]`를 가집니다. 빈 제목만 채운 PASS, 생성되지 않은 파일·실행 기록의 임의 경로, 근거 없는 수치 또는 합격 표시는 금지합니다.

### 원본 공통 01~10
- **01** 원본 식별·경로·ID·SHA·실제 접근·라이선스
- **02** Pine 전체 코드·입력·지표·주문 구문·리페인팅·정확한 줄 위치
- **03** 자산·시장·계약·거래소·통화·승수·틱·체결가능시간
- **04** 원본 진입·청산·포지션·리스크·수수료·체결 시점
- **05** 원저자 주장 성과, 실제 재현/백테스트 및 미검증 요소 구분
- **06** 경제적 수익구조·레그·현금흐름·반증 가능성
- **07** S001~S087 공식 정본 **87행 전수 비교**, 직접/유사/구성요소/가설/비관련/미확인
- **08** R01~R12 공식 정본 **12행 전수 비교**, 신규 전략 유형과 미확보 정본 명시
- **09** 경제적 가설, 수익·헤지 메커니즘, 반증·필요 시장자료
- **10** 실제 수행한 외부 검색 API·시각·원문 채택/탈락·검색 불가 구분

### 개별 CASE_ID마다 필수 11~20
- **11** 문헌·사례 출처, DOI/저자/원문 위치/권리/증거 수준
- **12** 원문 확인 규칙 `SOURCE_CONFIRMED_RULES`과 AI 창작 `RESEARCH_ASSUMPTIONS` 완전 분리
- **13** 계약·각 거래 Leg의 종목/거래소/방향/수량/승수/만기/통화/헤지비율
- **14** LONG/SHORT 진입·청산·손절·목표·충돌처리·상태기계의 실행 수식
- **15** 매수/매도 방향을 포함한 P&L·호가·환산·거래비용·증거금·스트레스
- **16** 데이터 공급처·시각정렬·계약월·시장세션·저작권·실데이터/합성 구별
- **17** 완전 Python 전략·파라미터·환경·CLI·SHA·입출력 계약. 단, 실제 코드 없으면 `NOT_RUN`
- **18** 실제 기능·음성·경계·누수 테스트의 커맨드·종료코드·로그. 미실행은 `NOT_RUN`
- **19** 주문·포지션·차트·백테스트·실거래 데이터 SHA/성과. 미실행은 `REAL_BACKTEST_NOT_RUN`
- **20** 전략 채택·기존 87+12 연결·무효화 조건·다음 검증·재현성 이력

하나의 최종 JSON에는 원본 공통 `01`~`10` **정확히 10개**, 그리고 각 CASE마다 `11`~`20` **정확히 10개**가 모두 포함되어야 합니다. GitHub는 누락·잘못된 순번·근거 없는 PASS·미수행 섹션을 최종 합격으로 간주하지 않습니다. 한 번의 AI 호출 안에서의 재구성은 내부 자기검증일 뿐 별도 새 대화방의 독립 블라인드 검증이 아닙니다.

### 실제 입력·전송 제약
HITEL 공개 API는 텍스트형 요청만 받으므로, GitHub 실행기는 각 원본에 꼭 필요한 **검증된 정본 정의·원본 사실 및 관련 인디케이터 연결**을 24,000자 입력 한계 안에서 제공해야 합니다. 전체 33,890건이나 23,885개 연결을 넣은 척하지 마십시오. 필요한 87+12 전문·Pine을 확보하지 못했으면 `CATALOG_UNVERIFIED` / `PINE_NOT_VERIFIED`로 처리하고 최종 합격을 차단합니다. 원본 하나의 결과가 JSON으로 완전히 반환되지 않거나 모델 출력이 잘린 경우에도 `BLOCKED`로 보존합니다.
