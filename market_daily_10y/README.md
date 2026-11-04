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


## 대규모 종목 풀: 지속 큐 모드 (2026-11-05 추가)

이제 파일의 숫자 위치를 가리키는 \`cursor.json\`과 별개로 \`collection_queue\` SQLite 테이블을 활용할 수 있다.
신규 종목이 추가되어도 기존 종목의 수집 진행 상태를 잃지 않는다. 시장/자산군을 교차 선택해 초기 종목 확보의 편향을 줄이고, 실패 종목은 지수형 일 단위 재시도 간격을 둔다.

\`\`\`bash
# Railway Cron에 권장하는 명령: 공식 미국·홍콩 종목 목록 + SQLite 큐
python -m market_daily_10y.collector \
  --refresh-global-universe --queue --limit 100 --pause 1

# 크기가 큰 instruments 전체 JSON 대신 간단한 실제 진행률과 처리량 경고
python -m market_daily_10y.collector \
  --root /data/market_daily_10y --progress --limit 100

# 기록: /data/market_daily_10y/latest-run-summary.json
\`\`\`

주의: 기본 \`--queue\` 옵션은 아직 켜지지 않는다. 운영 시작 명령에 명시해야 한다. 기존 \`--offset\`은 Queue 모드와 함께 쓸 수 없다. 10년 일봉 최초 적재에 성공하더라도 커버리지 품질 검증을 통과하지 못한 신규 상장 종목은 유사도 검색에서 제외한다.

미국+홍콩 공식 목록 검증 시 후보 **15,943개**. 하루 100개는 초기 전체 순회에 **이론상 최소 160일**이 걸리며, 7일 이내 모든 후보 갱신에는 이론상 **하루 2,278개 이상**이 필요하다. 실제 미지원 티커, HTTP 제한, 재시도, 데이터 사용 권리와 볼륨 용량 문제를 고려하면 이 숫자는 처리량 보장치가 아니다. 이때 \`capacity_below_7d_full_refresh\`는 true로 표시된다. 4GB 볼륨 한도도 대량 적재 이전에 측정·조정해야 한다.

* JPX는 현재 **관리자가 제공한 공식 원본 스냅샷**의 파서가 있는 상태다. 자동 JPX 적재 완료로 보고하지 않는다.
* KRX는 **사용 허가가 확인된 목록 파일**을 통해서만 확장한다. 공개 오픈데이터에 붙은 비상업적·변경 금지·재배포 제한을 무시하지 않는다.
* Nasdaq/HKEX의 공식 상장 목록과 Yahoo **가격 데이터의 상업적 저장·재사용 권리**는 별도 확인이 필요하다.
* \`--progress\`의 \`listing_candidates\`는 데이터 다운로드 완료 수가 아니며, \`historical_eligible_rows\`와 \`recent_eligible_rows\`도 별도로 해석한다.
* WF-04/SCAMP에는 별도 분석 서비스에서 같은 시작·종료일과 실제 공통 거래일만 사용하며, 적격하지 않은 종목은 쿼리에 보내지 않는다.

검증 방식: GitHub Actions의 새 유닛·실제 Yahoo/공식 거래소 통합 smoke가 실패하면 전체 workflow도 실패로 표시하도록 설정했다. Railway 운영 데이터 적재 완료 여부는 Railway 실행 로그와 볼륨 DB를 직접 확인해야 한다.
