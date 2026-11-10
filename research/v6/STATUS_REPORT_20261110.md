# 주식자동화 자동전략 개발 v6 — 이전 생성 차단 3건 정상 개발 보고

기준: 2026-11-10 / 격리된 연구용 결과 / 기존 서비스 및 LIVE 거래 미변경.

## 왜 이전 지시가 잘못되었는가
v3의 `SOURCE_CONFIRMED_RULES` 검증을 매매규칙의 **자동 생성 차단 조건**으로 잘못 사용했습니다. 자료의 불확실성은 *출처 사실*로 표시해야 하지만, 검증되지 않은 연구 파라미터를 개발가정으로 명시하고 자체 구현하는 것은 본 프로젝트의 목적입니다. 따라서 원문이 진입·청산 알고리즘을 완성하지 않았더라도 연구 전략을 설계할 수 있어야 합니다. v4 정정 규약으로 변경했습니다.

## 코드 생성·실행 결과
| 사례 | 독립 연구전략 | 레그 | 생성·기능시험 결과 | 실제 시장 성과 |
|---|---|---|---|---|
| Baek 2020 | OLS 연구용 HG–PL 선물 15일 밴드 평균회귀 | PL 2계약, HG 1계약 | Python 생성, 합성 청산 거래 7건 | 실데이터 미실행 |
| Psaradellis 2021/2023 | PL–GC 2:1 RSI 스프레드 | PL 2계약, GC 1계약 | Python 생성, 합성 청산 거래 13건 | 실데이터 미실행 |
| Iwatsubo 2022 | NYMEX–JPX/OSE 백금 환율조정 2시장 호가차 | NYMEX 1계약, JPX/OSE 3계약 + FX 선도호가 참고 | Python 생성, 합성 호가 리플레이 1건 | 실데이터 미실행 |

모든 사례는 `strategy_spec.json`, `generated_strategy.py`, `synthetic_functional_result.json`, `synthetic_cli_output.json`, `synthetic_trades.csv`, `v3_20_sections.json/md`, `taxonomy_87.csv`(87행), `source_map.json`, `execution_manifest.json`, `assessment.md` 파일을 실제로 포함합니다.

## 규칙·데이터의 정확한 경계
**Baek**: 논문의 ECM/SVR·15일 밴드 사고방식은 원문 기반입니다. 이번 코드의 HG–PL OLS 계수, 1.5σ 진입, ±0.35σ 청산, 7봉 최대보유, 2PL 대 1HG 계약 및 비용은 독자 설계입니다. OLS만으로 공적분을 검정했다고 주장하지 않습니다. 단순 계약수는 OLS 결과와 헤지 노출 차이가 크면 후보를 거절합니다.

**Psaradellis**: 원문은 PL–GC 스프레드·2PL:1GC 승수 정렬·RSI2라는 규칙 분류 및 거짓발견률 통제의 연구입니다. RSI(14), 35/65 진입, RSI 중립 구간 청산과 다음 봉 시점은 개발가정입니다. 논문 RSI2라는 **규칙 ID**를 RSI(2일)라고 잘못 해석하지 않았습니다. 실제 FDR/Walk-forward 결과는 미검증입니다.

**Iwatsubo**: 원문의 PROF 계산식은 동시각 bid/ask와 USD/JPY 선도 환율로 양방향 가격 차이를 측정합니다. 이번 코드에는 뉴욕 50온스와 일본 500g×3계약의 잔여 백금 노출, 도쿄·뉴욕·FX 호가의 신선도와 만기·시장시간을 검사합니다. 이것은 **시장 중립 또는 고정 차익이 아닙니다**. 실제 FX 선도 헤지 계약 체결·월물별 현물 인도 동등성·증거금·대차 및 동시 주문장 체결은 구현·검증하지 않았습니다.

## 실행방법
```
cd auto_research_v6
python build_v6.py
python build_reports_v6.py
python -m unittest discover -s tests -v
python results/0CVvd49h/cases/BAEK-2020-HG-PL-RESEARCH/generated_strategy.py fixtures/synthetic_daily_bars.json
python results/0CVvd49h/cases/PSARADELLIS-PL-GC-RULES-RESEARCH/generated_strategy.py fixtures/synthetic_daily_bars.json
python results/0CVvd49h/cases/IWATSUBO-CROSS-VENUE-MICROSTRUCTURE/generated_strategy.py fixtures/synthetic_quote_snapshots.json
```
- 전체 회귀 테스트: **30개 통과** (`test_results.log`)
- 생성 코드 CLI 3개 모두: **종료코드 0**, JSON 파싱 성공 (`synthetic_cli_output.json`)
- 데이터: **사용자 실거래 데이터 아님**, 날짜·가격 모두 결정론적 합성 생성.
- 자동외부검색/모델 기반 임의 Strategy ID 전체 반복 발굴: **이번 결과로 검증되지는 않음**. 다만 `auto_discovery_v6.py`는 외부의 경제적 근거만으로 신규 연구규칙을 생성하는 범용 인터페이스를 구축했고, 서로 다른 Strategy ID를 이용한 모의 경로 테스트가 통과했습니다. 동일 규칙 가족의 `spec.kind` 입력으로 코드는 생성되지만, 원본 전체를 자동 조사하는 완성 엔진은 별도 작업.
- 리스크: 사용허가, 실제 브로커 API, 마진, 호가창, 수수료, 롤오버, 다중비교 편향, 타시장 동시 체결, 실거래 차단을 실시장 검증으로 별도 다룰 것.

## 생성한 신규 분류 후보 (87개 기존 정본 대체 아님)
- `METALS-HG-PL-COINT-REVERSION` — 금속 공적분 회귀 스프레드(OLS 연구 대체)
- `METALS-PL-GC-RSI-SPREAD` — 금속 간 RSI 상대가치 스프레드
- `CROSS-VENUE-PLATINUM-FX-QUOTES` — 이중 거래소 백금·FX 선도호가 차이

**기존 87개는 원문 이름과 ID를 그대로 보존했습니다. 추가 12개 연구영역의 정본 명칭은 미확보로 남겼으며, 0행을 거짓으로 12행 채우지 않았습니다.**

## 주요 출처
- Baek et al. (2020), Sustainability 12(17), 6791, Section 2.4: https://doi.org/10.3390/su12176791
- Psaradellis et al., Technical analysis, spread trading, and data snooping control, manuscript p.7 footnote 6 and Table 2: https://doi.org/10.1016/j.ijforecast.2021.10.002
- Iwatsubo & Watkins (2022), J. Risk Financial Management 15(12), 593, Equation (1): https://doi.org/10.3390/jrfm15120593
- Japan Exchange Group (OSE Standard Platinum 500g specification, TOCOM transfer 2020): https://www.jpx.co.jp/english/derivatives/products/precious-metals/platinum-standard-futures/01.html
