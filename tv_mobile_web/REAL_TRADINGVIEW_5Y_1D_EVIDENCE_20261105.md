# TradingView 앱 원본 연결을 재사용한 5년 일봉 실증 보고서 (2026-11-05)

## 실행된 실제 데이터 (테스트용 가격 아님)

| 심볼 | 실제 5년 일봉 | 실제 날짜 범위(UTC) | 수집 날짜 확보율 | WebSocket 과거 요청 | 저장·해시 재검증 |
|---|---:|---|---:|---:|---|
| NASDAQ:AAPL | 1,254 | 2021-11-05 ~ 2026-11-04 | 96.17% (평일) | 20회 | 통과 |
| KRX:005930 | 1,222 | 2021-11-05 ~ 2026-11-04 | 93.71% (평일) | 13회 | 통과 |
| BINANCE:BTCUSDT | 1,819 | 2021-11-12 ~ 2026-11-04 | 99.62% (24x7) | 22회 | 통과 |

AAPL 실수집 및 부분 300봉을 1,254봉으로 확장: https://github.com/lyonbegin/autonomous-investor-backend/actions/runs/42022732486

AAPL 영구 볼륨 데이터 재조회·SHA256 검증·실제 모바일/데스크톱 그래프 표시: https://github.com/lyonbegin/autonomous-investor-backend/actions/runs/42025014239

삼성전자·비트코인 실수집·해시 검증·영구 저장: https://github.com/lyonbegin/autonomous-investor-backend/actions/runs/42025407594

AAPL 저장 파일 SHA256: 128d467ee7ef454c557dc5302407b40490df23c7d2b50d7c27af59a0d68e8a06

## 원본 코드 재활용 관계

사용자 제공 TradingView APK 내부 assets/chart/index.js에서 시간봉 설정 setResolution, 날짜 이동 ranges().goToTime을 확인했고, assets/feature_chart_kotlin_js_client.js에서 ranges().selectRange 메서드를 확인했다.

현재 서비스에서는 독립 분기 내 원본 프로젝트의 official_chart_probe.py 디코더(decode_chart_messages, collect_bars)를 재사용해 TradingView 공개 차트에서 전달되는 실제 WebSocket OHLCV를 추출한다.

사용자가 수집 버튼을 클릭하면 5년 기간(60M), 일봉(1D) 차트를 연다. 처음 전달되는 약 300개 봉에서 과거 방향으로 사용자 인터페이스를 조작해 request_more_data를 유발했다. 세 종목 모두 추가 과거 봉을 실제로 수신한 실행 기록이 있다.

직접 앱 내부 ranges().selectRange 함수의 호출 성공은 아직 확인되지 않았다. 모바일 앱 내부 함수 확인 사실과 웹 차트에서의 직접 호출을 혼동하면 안 된다. 이번 세 종목 성공은 정상 차트 UI 이동과 추가 WebSocket 이력 수신의 실증이다.

## 저장 및 품질

- 지원 간격: 일봉 1D만. 분봉/시간봉으로 5년 다운로드하지 않는다.
- 저장: 별도 Railway 서비스 tradingview-full-mobile-web-lab 및 별도 1GB 볼륨 /data.
- 저장 형식: gzip JSON 가격 봉 + SQLite 메타데이터; SHA-256 파일 무결성 검사.
- 동일 종목 재수집: 실제 과거 봉을 병합해 누락을 보완하고 기존 장기 이력을 삭제하지 않는다.
- 품질: 5년 최초/최종 날짜, 1일봉 간격, 평일 또는 24x7 날짜의 최소 90% 확보를 동시에 검사.
- 아직 별도 거래소 공식 휴장일/매매정지 기준 완전성 검수는 하지 않았다.
- 전체 거래소·전체 종목 수집 완료라는 주장은 하지 않는다.
- 운영 n8n 기존 코드·기존 관리자 UI 병합은 하지 않았다.
- 자동 수집 Cron 없음. 계정 인증 또는 토큰 입력을 새로 요구하지 않는다.
- 원본 Android와 픽셀 단위 UI 1:1 및 전체 339개 기능 구현은 아직 미완료.
- TradingView 원천 데이터 상업적 장기 저장·제3자 제공의 라이선스 문제는 별도로 검토해야 한다.

## 직접 확인

개발 모바일 웹:
https://tradingview-full-mobile-web-lab-production.up.railway.app/

미국: https://tradingview-full-mobile-web-lab-production.up.railway.app/#/chart/NASDAQ%3AAAPL

한국: https://tradingview-full-mobile-web-lab-production.up.railway.app/#/chart/KRX%3A005930

암호화폐: https://tradingview-full-mobile-web-lab-production.up.railway.app/#/chart/BINANCE%3ABTCUSDT

실행·검증 코드는 독립 브랜치 feature/tradingview-android-full-mobile-web-20261105에만 있으며 기존 운영 브랜치를 수정하지 않는다.
