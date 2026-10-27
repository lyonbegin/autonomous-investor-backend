# TradingView / Pine 기존 구현 복원

소스: tradingview-service 최신 HEAD의 tradingview.py(약 3,800줄), corporate_bonds.py, source_registry.py, browser_worker와 quant-lab-control의 market_history.py, strategy_spec.py, pine_visual.py를 함께 복원했다.

- 아이디어·시장·스크립트·Pine 원문/메타데이터·후보·고정 시간축 에이전트·회사채 backfill과 작업 상태 API를 보존했다.
- 최신 public_frontend에서 /ideas가 /scripts로 리다이렉트되어 도달할 수 없던 기존 IdeasPage/IdeaDetailPage를 다시 연결했다. 스크립트 화면은 별도로 유지한다.
- Python 외부 시장/거시/소스 데이터는 browser_http를 통한다. 내부 Pine 소스 서비스 호출은 internal_http로 분리해 인증 토큰이 외부 브라우저 Worker에 전달되지 않게 했다.
- public_frontend의 API base는 VITE_PUBLIC_API_URL로 로컬 중계 API에 연결할 수 있다. 비밀값을 VITE_*에 넣지 않는다.

현재 코드는 indicator와 strategy, source availability를 구분하지만 원본과 Python 변환 신호 동등성, 전체 라이선스 판정, 모든 콘텐츠 증분 수집은 검증되지 않았다. Dynamic Liquidity Clouds 같은 특정 지표 시각화 구현은 독립 검토가 필요하다. UI 렌더링이나 Pine 변환 성공을 실거래 적격성으로 승격하지 않는다.

회사채 코드의 작업 체크포인트·SQLite 동시성 및 Horizon·macro 최신 운영 결과는 KNOWN_ISSUES와 RAILWAY_SERVICE_INVENTORY를 참조한다. 운영 수집 요청·백필·DB 쓰기는 이번 조사에서 실행하지 않았다.
