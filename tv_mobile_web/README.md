# 독립 모바일 웹 구현 및 검수 상태

실행: `pip install -r tv_mobile_web/requirements.txt` 후 `uvicorn tv_mobile_web.server:app --port 8855`.

이 브랜치는 원본 Android 앱 기능 대조를 위한 독립 연구 구현입니다. 기존 관리자 UI와 운영 브랜치는 변경하지 않았습니다.

## 현재 구현

- 모바일 하단 5개 탭 및 전체 26개 기능 영역 탐색
- 기존 TradingView 연동 API에서 실제 시장 스캐너 정보와 아이디어 목록 GET 조회
- 5년 기간·일봉(1D)을 지정한 공식 차트 위젯 표시 (자체 일봉 저장은 아님)
- 관심목록 추가·수정·삭제와 알림 초안의 브라우저 로컬 상태
- 사용자 심볼 검색, 다크 모드, 모바일·데스크톱 반응형
- 원본 기능 339개 개별 이름·ID의 검색 가능한 검수 원장

## 미완료 — 구현 완료로 보고 금지

실제 Android 앱 조작 및 화면 픽셀 비교, 339개 전 기능 동등성, 서버 계정 동기화, 차트 과거 봉 자체 적재, 뉴스·경제 캘린더·거래·리플레이 등의 전체 동작은 미검증 또는 미구현입니다.

시장 조회·상태 열람으로 백그라운드 데이터 다운로드를 시작하지 않으며 Cron과 관리 키도 추가하지 않았습니다.

브라우저 테스트의 시장 값은 테스트 전용 fixture로, 실제 TradingView 가격 수집 성과가 아닙니다.

## 검증

- `python -m pytest -q tv_mobile_web/tests/test_server.py`
- `node --check tv_mobile_web/web/app.js`
- `node --check tv_mobile_web/web/feature_registry.js`
- `python tv_mobile_web/tests/browser_e2e.py` (Playwright/Chromium 설치 필요)

전체 기능 원장은 TV-001~TV-339와 26개 영역을 유지하며, 미확인 신규 화면 후보 44개도 추가 조사 대상입니다. 기존 운영 관리자 화면과의 병합은 전수 검증 이후로 보류합니다.
