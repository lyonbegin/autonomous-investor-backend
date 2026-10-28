# 주식 자동화 플랫폼 — 최종 통합 기획 및 구현 기준서

기준일: 2026-10-28. 이 문서는 제품 목표 기준이지 구현 완료 확인서가 아닙니다.

## 제품 목표

TradingView Ideas·Markets·Scripts·Pine Script 수집/분류/버전 관리 → Python 필수 12개 투자 엔진/AlphaForge 분석 → 백테스트·예측·위험 평가 → AI 에이전트 추천·배정·경쟁·자본 배분 → n8n 워크플로 실행/승인/감사 → NautilusTrader PAPER 운용 → 관리자·일반 사용자 전략 탐색/성과 서비스.

**n8n 원본 편집기는 플랫폼 운영의 중심 기반이지 최종 제품 전체가 아닙니다.** 원본 Python 코드를 보존하고 어댑터로 연결하며 LIVE 주문은 안전 검증과 별도 승인 전 차단합니다.

## 필수 12개 엔진

TradingAgents(토론), FinRobot V2(재무·공시), RD-Agent(Q)(연구), Microsoft Qlib(퀀트), Amazon Chronos(예측), Stable-Baselines3(RL), Ray RLlib(분산 RL), vectorbt(백테스트), FinRL-Trading(투자 정책), Riskfolio-Lib(위험), PyPortfolioOpt(최적화), NautilusTrader(백테스트·주문 의도·실행).

기존 설계는 엔진 래퍼 117 + 서비스 API 20 = **137 연산**, identity/join/approval 3개 제어 = **140 투자 노드 유형**. n8n 기본 노드와 별개이며 전체 연산이 거래 권한을 가진다는 뜻은 아닙니다.

## 필수 구현 단계

1. n8n 서버 영구 저장, 버전·게시·스냅샷·재접속 복원.

2. 원본 n8n 캔버스에서 137개 실제 Python 연산 + 3개 제어 노드의 실행·입출력 JSON·병렬 합류·분기·오류·승인 후 재개.

3. TradingView 증분 수집 → Pine 적격성·라이선스 검증 → 백테스트 → 12개 엔진 평가 → 에이전트 추천/배정 → 위험 평가.

4. 원본 n8n 실행 상태(queued/running/success/failed/skipped), 시간, 로그, 오류, 재시도, 승인·감사.

5. NautilusTrader PAPER 전략 운용·멱등성·Fencing Token·HALT·브로커 원장 대조. LIVE 차단.

6. TradingView 탐색 및 AlphaForge 분석을 참고한 관리자/일반 사용자 프론트엔드, 성과/전략/에이전트 상태 제공.

## 운영 워크플로

| 코드 | 내용 | 상태 |

|---|---|---|

| F01 | 15분 주기 전략·Pine 수집·버전 | 구현/합성 테스트 기록, 실데이터 종단간 별도 |

| F02 | 전략 적격성 검토 및 승인 | 계획 |

| F03 | 1분 주기 승인 전략 PAPER 에이전트 DB 배정 | 구현/합성 테스트 기록, 상주 전략 실행 아님 |

| F04 | NautilusTrader PAPER 운용 | 미구현 |

| F05 | 1분 주기 이상 이벤트 독립 감사/HALT | 구현/합성 테스트 기록, 실브로커 대조 아님 |

| F06~F09 | 최종 명칭·책임 | 확인 근거 부족, 임의 확정 금지 |

| F10 | 주문·포지션 원장 대조/안전한 해제 | 계획 |

**13개 n8n JSON = F01/F03/F05 운영 3개 + 합성 10개.** 10개 합성 시나리오는 신규 수집, 전략 버전 변경, 자본 배분 경쟁, 부분 체결, 장기 백테스트, 전략 드리프트, 브로커 타임아웃, 에이전트 중단, 지원 불가 Pine, 전략 폐기이며 삭제 금지. 합성과 실데이터 검증은 반드시 구분.

## 2026-10-28 구현 상태

완료/기록 존재: n8n 원본 편집기 사용자 조작 브라우저 검증 보고, 13개 JSON 조회, localStorage, 12개 엔진 API/DAG 프로토타입, F01/F03/F05 합성 검증, 10개 Webhook/Worker 합성 시나리오.

미완료/미검증: n8n 원본 편집기 서버 영구 저장, 140개 투자 노드의 n8n 네이티브 실행, TradingView 실데이터/Pine 전체 변환, 12개 엔진 실데이터 종단간 AI 추천, NautilusTrader PAPER 실제 전략 운용/체결 대조, 최종 사용자 프론트엔드.

각 완료 판정에는 실제 코드, DB/API/브라우저 시나리오, CI·실행 로그, 오류 복구 및 배포 증거가 필요합니다.

## 이 프로젝트 모든 채팅에서 공유

1. 이 기준서(DOCX 또는 Markdown)를 다운로드하고 ChatGPT '주식 자동화' 프로젝트의 파일로 업로드합니다.

2. 프로젝트 지침에 다음을 추가합니다: '프로젝트 파일의 주식 자동화 최종 통합 기획 및 구현 기준서를 우선 기준으로 사용한다. n8n 편집기는 전체 플랫폼의 일부이며, 12개 투자 엔진 모두 필수다. 완료와 미완료, 합성 테스트와 실데이터 검증을 구분한다.'

3. 새 채팅은 '프로젝트 파일의 최종 기획안 기준으로 이어서 진행해'라고 시작합니다.

GitHub 저장만으로 ChatGPT 프로젝트 모든 채팅이 문서를 자동으로 읽는 것은 아닙니다. 변경 시 GitHub와 프로젝트 첨부 파일을 동기화하세요.

## 근거 문서

- [12개 엔진·140개 투자 노드 명세](https://github.com/lyonbegin/autonomous-investor-backend/blob/feature/n8n-native-editable-test-20261028/docs/INVESTMENT_NODE_WORKFLOW.md)

- [F01/F03/F05 운영 명세](https://github.com/lyonbegin/autonomous-investor-backend/blob/feature/n8n-native-editable-test-20261028/docs/F01_F03_F05_OPERATIONS.md)

- 이 프로젝트 대화에 사용자가 제공한 최종 기획 보고