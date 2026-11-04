# 글로벌 마켓 / 10년 일봉 데이터 페이지 (수동 전용)

- 사용자 화면: `/markets/`
- 상태 API: `/api/markets/summary`, `/api/markets/instruments`
- 일봉 보기: `/api/markets/bars?key=...` (실제 저장 Parquet + SHA256 검증, 관리자 키 필요)
- 종목 목록만 갱신: `POST /api/markets/update` `{"scope":"catalog"}`
- 종목별 일봉 갱신: `{"scope":"instrument","key":"equity:NASDAQ:AAPL:spot"}`
- 특정 자산군: `{"scope":"category","category":"equity","max_items":100}`
- 전체 대상: `{"scope":"all","max_items":100}` (null = 제한 없이 시작)
- 작업 상태: `/api/markets/update-status` (Railway 볼륨 `manual-update-job.json`)
- 인증: `MARKET_UPDATE_TOKEN` 환경변수. 실제 OHLC 열람 및 업데이트 버튼에 필요. 키는 페이지 새로고침 시 브라우저에서 잊음.
- 자동 실행: **없음**. Cron 설정 null. FastAPI 프로세스는 데이터 다운로드 없이 페이지 요청만 응답.
- 원천 목록: `/data/market_daily_10y/universe/world.csv`가 있으면 우선 사용, 없으면 코드의 기본 28개. 미국/홍콩 공식 목록은 사용자가 '전체 종목 목록만 갱신'을 클릭할 때만 확보.
- 데이터: `/data/market_daily_10y/catalog.sqlite3`, `daily/{asset_class}/{hash}.parquet`. CI 수집은 운영 수량에 포함되지 않음.
- TradingView: 탐색 범위의 **메뉴/분류만 참고**. TradingView HTML/CSS/로고/차트를 복사하거나 TradingView 시세를 다운로드하지 않음. 시장별 전체 종목 연결 여부는 실제 거래소별 목록 공급원 상황에 따라 다름.
- 런타임: uvicorn market_daily_10y.markets_api:app --host 0.0.0.0 --port 8000. Dockerfile = `market_daily_10y/Dockerfile`; Railway 공개 도메인은 targetPort 8000.
- 동작 검증: `python -m pytest -q market_daily_10y/tests/test_markets_api.py` 및 `.github/workflows/manual-markets-ui.yml` Playwright Chromium 데스크톱/모바일 실 브라우저 검사.

## 정상 / 미완료 구분

1. 시장 메뉴와 분류: 구현 및 CI 실제 클릭 검사 완료
2. 지역별 실제 전 종목 마스터: 미국·홍콩 공식 일부 연결, 나머지 주요 거래소 확대 필요
3. 실제 10년 일봉: 파일에 기록된 것만 표시 (없으면 '미확보')
4. 사용자 클릭이 없는 다운로드: 없음
5. 배포 빌드 성공 ≠ 10년 데이터 수집 완료
6. 외부 공급원 장기 저장/대외 제공의 상업적 이용권 검토 필요

## 프로젝트의 기존 n8n UI와 관계

이 페이지는 **시장 수집 볼륨에 연결된 독립 페이지**다. n8n 운영 UI / TradingView 아이디어 페이지 / WF-01~WF-04 노드를 덮어쓰지 않는다. 기존 운영 UI의 사이드 메뉴 연결은 별도 연동 개발로 남아 있다.
