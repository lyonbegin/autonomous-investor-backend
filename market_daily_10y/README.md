# 글로벌 10년 일봉 독립 수집기

기존의 2015~2017년 과거 샘플 데이터 반입 방식을 **폐기**하고, 데이터 공급원에서 **최근 10년 일봉(1D)을 직접 받는 별도 서비스**다. WF-04에서 새 전략이 등록될 때 수집기를 다시 실행하지 않는다.

## 날짜 기준

- 전 세계 모든 자산에 **같은 기간** [UTC 실행일 10년 전, UTC 실행일) 적용.
- 예: 2026-11-04 수집 → **2016-11-04 ~ 2026-11-03** 일봉.
- 시장별 원본 거래소 날짜를 유지. 미국 종가를 KST 날짜로 이동시키지 않음.
- 미국/한국 휴장일은 달라서 바의 개수가 다를 수 있음. **시계열 검색 직전에 실제 공통 거래일만 inner join**. 가짜 보간, 평일 채움 없음.
- 서로 다른 날짜에 갱신한 배치도 최대 **7일 차이만** 허용하고, 오래된 as-of 기준 동일 10년 창으로 재절단한 뒤 일봉 정합성을 재검사한다. 7일 초과 데이터는 비교 거부.
- 10년 시작 32일 이내, 종료 10일 이내, 평일 또는 7일 달력 기준 80% 이상의 실제 일봉을 **동시에** 만족해야 유사도 비교에 노출된다. **새로 상장한 기업**은 실데이터가 있더라도 별도 보류.
- 자산군: 주식, ETF, 지수, 선물 연속물, 옵션, FX, 암호화폐 현물/선물, 원자재, 채권, 금리. 제공 가능 여부는 Yahoo 티커별로 다름. ETF를 원래 채권과, 연속 선물을 개별 만기 계약과 **동일 상품으로 취급하지 않음**.

## 코드/배포

- 독립 프로그램: `market_daily_10y/collector.py`
- 독립 Dockerfile: `market_daily_10y/Dockerfile`
- Railway 독립 서비스: `global-daily-10yr-collector`
- Railway Cron: **매일 08:00 UTC (한국 17:00)** 실행, 끝나면 프로세스 종료.
- 데이터: 별도 **4GB 영구 볼륨 /data**, 기간/품질 메타 SQLite, 일봉 **Parquet Zstandard**.
- 기본 20개씩 수집, 수집기가 기록하는 **회전 커서**를 사용해 다음 배치로 진행. 세계 전 종목 확보에는 별도의 거래소 목록과 공급원·속도/이용권한 검증이 필요하다.
- 수집기가 데이터를 다운로드한 뒤에는 **증분 갱신 시 최근 10일만 다시 조회**해 공급원 가격 수정에 대응한다.
- 저장소 내용은 실시간 자동매매 호가가 아니라 장기 시계열 유사도 선별용. 시장별 시간봉은 WF-14 전략 진화 단계에서 사용.

```bash
pip install -r market_daily_10y/requirements.txt

# 2016-11-04 ~ 2026-11-03 동일 범위, 미국 AAPL 한 종목 실제 수집
python -m market_daily_10y.collector --root ./local-daily-pool --asof 2026-11-04 --limit 1 --pause 0

# 전 세계 자산군의 최신 10년 일봉을 외부 인터넷에서 순차 수집
python -m market_daily_10y.collector --root ./local-daily-pool --limit 20

# 수집 결과와 10년 이력 충족 여부
python -m market_daily_10y.collector --root ./local-daily-pool --status

# 검증 통과된 두 실제 종목만 동일 달력 날짜로 비교
python -m market_daily_10y.collector --root ./local-daily-pool \
 --align equity:NASDAQ:AAPL:spot equity:KRX:005930:spot

# 전용 universe.csv를 다른 실제 거래소/선물 종목 목록으로 교체 가능
python -m market_daily_10y.collector --universe ./full-global-universe.csv --limit 20
```

## 검증 기록 및 주의

- [실제 GitHub Actions 실행](https://github.com/lyonbegin/autonomous-investor-backend/actions/runs/41820807656)에서 Yahoo **AAPL 10년 일봉 2,512개**, 2016-11-04~2026-11-03, **96.32% 평일 대비 커버리지**, 10개 단위 테스트 통과를 직접 확인.
- 이것은 AAPL 1개 종목의 10년 실수집 성공이지 세계 모든 상장사의 수집 완료가 **아님**. 현재 기본 `universe.csv`는 실제 동작을 확인하기 위한 **28개 종목·상품 티커**다. 거래량 상위 전 세계 전체 거래소 종목 목록은 다음 확보 대상.
- Yahoo Finance/yfinance는 공식적 상업 데이터 배포 라이선스가 아닌 **개인·연구 용도의 접근 경로**이므로, 서비스 상용화에 앞서 적절한 데이터 라이선스가 필요하다.
- SCAMP/Matrix Profile/TA-CUDA는 **후속 별도 WF-04**로 연결해야 함. 이 수집기는 데이터 구축만 담당하고 GPU 계산을 실행하지 않는다.
