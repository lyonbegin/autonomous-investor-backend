# IWATSUBO-CROSS-VENUE-MICROSTRUCTURE | 전략 개발 완료 범위

- 거래 알고리즘과 생성 Python 소스: **생성 및 기능 실행 완료**
- 원문 동일 재현: **아님**, 출처와 독립적인 설계 가정을 명시
- 합성 기능시험에서 청산 완료한 거래: **1건** (시장 성과와 무관)
- 경제적 거래구조: Price discovery/liquidity may differ between NYMEX and historical TOCOM and present JPX/OSE platinum listings; opposite execution-side bid/ask comparisons after forward FX normalization reveal temporary apparent price discrepancies.
- 검증해야 할 핵심 위험: JPX/OSE 500g contract specification independently identified, but specific month/account permissions and cross-venue delivery equivalence unverified; delivery/clearing not fungible. Non-zero residual metal delta and forward hedge mismatches mean it is NOT riskless. Bid/Ask cannot be assumed simultaneously filled; size/depth and market access unverified.
- 실데이터·증거금·호가·PAPER·LIVE: **검증하지 않음**
- 기존 87개 후보 연결: S014, S006, S012; 원문 구조와 동일 전략 확정 아님
- 기존 12개 추가 정본: **미확보**

전략 코드 부족을 이유로 연구개발을 거절하지 않음. 실거래 접근권 미확보는 LIVE/PAPER 단계에서 검증함.
