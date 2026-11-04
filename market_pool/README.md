# 글로벌 다중 자산 일봉 데이터 풀 (WF-03 데이터 준비, WF-04가 읽음)

## 구현 상태 — 성공을 과장하지 않기

- 구현: 등록/중복제거/원본 출처 감사기록/일봉 Parquet(zstd)/CSV.gz/증분 갱신/가격 검증/다중 자산/분봉·시간봉→현지 거래일 일봉.
- 실제 저장된 공개 데이터 예시: Plotly MIT 원본 [AAPL 과거 OHLCV 506봉](fixtures/REAL_plotly_AAPL_2015_2017.csv) (2015-02-17~2017-02-16). **2016~2026 전체 10년 글로벌 풀 아님.**
- 확인할 것: 클라우드 서버의 외부 인터넷, 야후 이용 조건, 지속 스토리지, 10년치 백필 결과, 매일 갱신 로그, 국가별 거래소 종목 리스트 완전성.
- 이 폴더는 주식 전용이 아님. 자산 분류: equity/etf/index/future/option/fx/crypto_spot/crypto_future/commodity/bond/rate.
- 매번 새 전략에서 가격을 긁어오지 않음. 전략과 독립된 단일 풀을 주기적으로 업데이트한 다음, 전략의 대표 종목 차트에서 유사한 후보 시계열을 **이 풀에서 검색**.

## 네트워크 연결된 서버에서 실행

\`\`\`bash
pip install -r market_pool/requirements.txt
# Railway라면 /data가 실제 영구 볼륨으로 연결되어야 함. ephemeral root 파일 저장 금지.
export MARKET_POOL_DIR=/data/global_market_pool
export MARKET_POOL_FORMAT=parquet
python -m market_pool.cli register
python -m market_pool.cli status

# 1. 이미 있는 데이터부터 가져오기 (새 크롤러 불필요)
python -m market_pool.cli import-eod /data/existing-global-eod/NASDAQ/combined/all_data.csv --exchange NASDAQ --asset equity
python -m market_pool.cli import-qlib /data/existing-qlib/us_data --region us
python -m market_pool.cli import-qlib /data/existing-qlib/cn_data --region cn

# 2. 시계열 데이터가 이미 시간봉인 경우 거래소의 현지 거래일로 묶어 일봉화
python -m market_pool.cli import-intraday 'equity:NASDAQ:AAPL:spot' \
  /data/existing-hourly.csv --timestamp-col timestamp

# 3. 빈 구간만 추후 동기화 (저장된 일봉의 마지막 날짜에서 7일 중첩)
python -m market_pool.cli yahoo --start 2016-11-04 --limit 5
python -m market_pool.cli binance 'crypto_spot:BINANCE_SPOT:BTCUSDT:spot' --begin 2017-08
python -m market_pool.cli binance 'crypto_future:BINANCE_USDM:BTCUSDT:um' --begin 2019-09

# 4. 오래된 실제 공개 CSV 데이터로 수입기 점검: 실제 과거 데이터이며 최신 커버리지 아님!
python -m market_pool.cli import-symbol 'equity:NASDAQ:AAPL:spot' \
  market_pool/fixtures/REAL_plotly_AAPL_2015_2017.csv --source plotly-mit-2015-2017
python -m market_pool.cli status
\`\`\`

## 재활용 중인 기존 프로젝트와 데이터

1. Microsoft Qlib — [GitHub](https://github.com/microsoft/qlib) / [데이터 사용 방법](https://github.com/microsoft/qlib/blob/main/docs/component/data.rst): US/CN 미리 만들어진 1일봉 데이터 ZIP. 먼저 Qlib의 공식 \`scripts/get_data.py qlib_data --target_dir ... --region us|cn\`로 다운로드·압축 해제 후 \`import-qlib\` 이용. Qlib 데이터는 조정/정규화될 수 있어 **원시 체결가격이 아님**.
2. Global EOD Market Data — [GitHub](https://github.com/JaiswalGunjan/global-eod-market-data): 16개 주요 거래소, CSV 일괄 저장 및 증분 업데이트 수집기. **미리 수집된 데이터가 담긴 repo는 아님**. NASDAQ/NYSE/NSE/BSE의 목록은 프로젝트에서 자동 수집 가능하지만 나머지 12개 거래소의 전체 종목 목록은 따로 입력해야 함. 기존 \`combined/all_data.csv\` 또는 per-symbol/일별 파일을 \`import-eod\`에 지정.
3. Binance Public Data — [GitHub](https://github.com/binance/binance-public-data) / [이미 만들어진 ZIP](https://data.binance.vision/): 암호화폐 현물과 코인/USDT 마진 선물의 월별 1일봉 ZIP을 수집기가 직접 가져옴. 2025년부터 일부 시각이 밀리초에서 마이크로초로 전환: 코드에서 처리함. 만기물·perpetual 구분해서 보관.
4. Yahoo Finance / yfinance — \`yahoo\`가 기존 풀에서 빠진 구간에 대해서만 일봉 조회. 미국/한국/일본/홍콩/중국/인도/유럽/호주 등 주식, ETF, 지수, 외환, 대표 선물 연속물 (실제 만기별 체결 데이터와 다름), 금리 지수 등을 구분해서 조회. API 속도 제한, 미지원 종목·오류를 기록해야 함.
5. Plotly 공개 OHLCV — [소스](https://github.com/plotly/datasets/blob/master/finance-charts-apple.csv) / [MIT 라이선스](https://github.com/plotly/datasets/blob/master/LICENSE): 실제 과거 AAPL 506봉을 이 코드의 CSV 인수 테스트용으로 저장, 최신 시장 데이터인 척하지 않음.

## 데이터 모델 / 필수 제약

- 종목 고유키 = 자산군 + 거래소 + 상품/심볼 + 계약 유형. ETF와 일반주, 선물 연속물과 개별 만기, 현물 암호화폐와 무기한 선물은 절대 한 종목으로 병합하지 않음.
- 1행 = 현지 거래일의 \`date,open,high,low,close,adj_close,volume\`. Open/High/Low/Close > 0 및 OHLC 범위 검증, 거래량 누락은 임의 0으로 대체하지 않음.
- 가격 원본/조정 가격을 구별하고 공급원별 사용권과 데이터 버전을 기록. Yahoo의 주식분할·배당 조정과 Qlib 정규화는 동일하게 취급하지 않음.
- 전 세계 모든 상장 종목을 포함한 목록과 상장폐지 과거 종목까지 완전 수록했다는 뜻은 아님. 해당 시장별 ticker directory와 licensed historical universe가 있어야 커버리지가 채워짐.
- 미국 지수선물의 Yahoo \`ES=F\` 등은 연속물 **대용 시계열**. 현물 채권, 만기별 옵션의 10년 과거 호가/가격 시계열은 무료 Yahoo 데이터로 보장 불가. \`unavailable\` 공급원으로 표시하고 보충 데이터가 확인될 때까지 비워둠.
- 장내 주식은 각 거래소 거래시간과 휴장일에 따른 일봉을 우선하고, 외환/암호화폐는 24시간 경계를 별도로 구분. 시간봉 재집계에서는 시각대와 선물의 야간 세션 rollover_hour를 명시.
- 큰 저장소는 \`MARKET_POOL_FORMAT=parquet\` 및 지속 볼륨/오브젝트스토리지 사용. GitHub 소스 저장소에 수백 GB 주가 데이터 직접 커밋 금지.
- 전략별 스크리닝은 누적된 이 풀의 최근 5년/10년 일봉만 읽고 SCAMP/MASS 등 시계열 유사도 검색을 수행. 실제 전략 타임프레임 고도화는 WF-14에서만.

## 테스트

\`\`\`bash
pytest -q market_pool/tests
\`\`\`

단일 전략을 선택하기 전에 **데이터 풀부터 확보해야 한다**는 요구를 반영한 독립 데이터 파이프라인이다.
