# BAEK-2020-HG-PL-RESEARCH | 전략 개발 완료 범위

- 거래 알고리즘과 생성 Python 소스: **생성 및 기능 실행 완료**
- 원문 동일 재현: **아님**, 출처와 독립적인 설계 가정을 명시
- 합성 기능시험에서 청산 완료한 거래: **7건** (시장 성과와 무관)
- 경제적 거래구조: A pair of metal futures may have a time-varying common driver; temporary pricing deviations may revert. Short deviation and simultaneously hedge related futures. This is a risky relative-value position, not risk-free arbitrage.
- 검증해야 할 핵심 위험: PL gamma is not matched with HG; commodity relationship breaks; inferred OLS beta is not proven cointegration. Integer hedge mismatch and rollover risk. Hard signal stop in z does not cap gap loss; no actual broker margin or liquidation logic.
- 실데이터·증거금·호가·PAPER·LIVE: **검증하지 않음**
- 기존 87개 후보 연결: S045, S028; 원문 구조와 동일 전략 확정 아님
- 기존 12개 추가 정본: **미확보**

전략 코드 부족을 이유로 연구개발을 거절하지 않음. 실거래 접근권 미확보는 LIVE/PAPER 단계에서 검증함.
