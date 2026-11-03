# 주식 자동화 · TradingView 원본 ↔ Python 차트 1차 동등성 검증

> 구현일: 2026-11-01  
> 서비스: https://investment-pine-parity-review-production.up.railway.app/  
> **주식 프로젝트 소유**: `n8n/pine-parity/` · 범용 공통 편집기 노드 종류는 변경하지 않음

## 이 프로젝트의 1차 목표

TradingView의 원본 Pine 전략과 그 적용 차트가 왼쪽, 같은 TradingView CSV 데이터를 사용하는 Python 전략 렌더링 차트가 오른쪽. 지표 계산·매매 신호·표시 객체를 비교하여 실질적인 변환 동등성을 판단한다.

- **수치 검증**: TradingView의 CSV에 원본 스크립트가 출력한 지표값·신호값이 반드시 포함되어야 함
- **시각 검증**: 실제 TradingView 차트 캡처와 Python 서버가 만든 SVG를 나란히 또는 투명도 중첩 방식으로 확인
- **결과 무결성**: Pine 원문, TV 시세 CSV, Python 변환 소스, Python SVG, 원본 이미지, 일곱 실행 단계 trace를 실행 ID로 저장
- **정식 완료**: 수치 일치만으로 완료 처리하지 않음. 실제 원본 차트의 그래픽·마커가 일치하는 시각 검증이 별도로 필요

## 사용 방법

1. TradingView에서 본인이 사용·검증할 수 있는 **공개 소스 또는 정당한 권한이 있는 Pine 전략**을 차트에 적용한다.
2. 사용할 종목/거래소/시간봉/기간/입력 파라미터를 고정한다.
3. TradingView의 **Download chart data** 기능으로 OHLC 및 지표 플롯/신호 출력이 포함된 CSV를 내보낸다. CSV 헤더에 `time,open,high,low,close` 및 비교할 원본 출력열이 포함돼야 한다.
4. TradingView에서 원본 전략을 표시한 차트를 PNG 또는 JPEG(2.4MB 이하)로 캡처한다. 가능하면 차트 영역만 크롭한다.
5. 서비스에 원본 페이지 URL, 종목/시간봉, Pine 코드, 시세·지표 출력 CSV, 이미지 파일을 입력한다.
6. Python 수치 계산 및 SVG 차트 생성 실행. 왼쪽 TradingView 원본 이미지와 오른쪽 Python 차트를 비교한다.
7. CSV에서 각각의 지표/신호 열 이름을 `columns` JSON에 매핑한다.
8. 차트 중첩 패널에서 투명도와 X/Y 위치를 조절해 정렬한 뒤 선과 신호의 시각적 차이를 확인한다.
9. 실행 결과의 `trace_url`로 일곱 단계 입력/출력·상태·오류를 확인하고, 원본·변환본·이미지를 실행 ID로 재조회한다.

### 지원 Pine 문법

**현재 정확히 구현된 작은 범위:** Pine v5/v6, `strategy(...overlay=true)`, `input.int` 길이, `ta.sma(close,len)`, `ta.ema(close,len)`, `ta.crossover/ta.crossunder`, `if` 조건에 따른 `strategy.entry/strategy.close`, `plot` 및 기본 `plotshape/plotchar`.

이 파서는 Pine 전체 문법 컴파일러가 아니다. `request.security`, `strategy.exit`, 타임프레임 중첩, 동적 객체 생성, 주문 설정 변경, 사용자 정의 함수·Library 의존성 등은 **지원하지 않으며 자동 합격 처리하지 않는다.**

서버는 사용자 입력 Pine을 Python으로 `exec`하지 않는다. 엄격히 제한한 구문으로 Python 계산·차트 SVG를 생성하고 독립적인 생성 Python 코드(`strategy.py`)를 저장한다. 생성된 Python 코드와 실행 엔진의 계산이 일치하는지는 CI에서 실제 실행해 검증한다.

### 중요: TradingView 기준자료는 실제 자료여야 한다

`합성 예제 불러오기`는 입력·출력·SVG 동작 확인용이다. **TradingView 자료가 아니므로 절대로 1차 검증 완료가 아니다.**

- `REFERENCE_COLUMNS_REQUIRED`: CSV가 있더라도 Pine의 플롯/신호 출력열이 없어 수치 일치 판단 불가
- `NUMERIC_MISMATCH`: TradingView의 수치와 Python 계산 결과 불일치
- `TRADINGVIEW_SCREENSHOT_REQUIRED`: CSV 지표값이 일치해도 차트 캡처가 없음
- `NUMERIC_MATCH_VISUAL_REVIEW_REQUIRED`: 수치는 일치하지만 실제 이미지 시각 비교를 완료하지 않음
- `REJECTED_NO_PARITY_CLAIM`: 미지원 Pine 구문 또는 잘못된 입력

**현재 자동 이미지 동등성 판정은 없다.** TradingView 차트 캡처의 글꼴·가격축·화면 범위 등이 서버 SVG와 다르므로, 단순 픽셀 동일성을 계산해 신뢰할 수 있는 PASS라 주장하지 않는다. 시각 검토는 아직 운영자 작업이 필요하다.

## 코드 구조

- `engine.py`: 제한형 Pine 파서 → Python 소스 생성 → Python 지표/신호 처리 → 같은 시세 CSV 비교 → Python SVG
- `server.py`: HTTP API, SQLite 실행 요약·7단계 trace, 캡처·원본 Pine·TV CSV·Python 소스·SVG 아티팩트 저장
- `index.html`, `app.js`: 실제 TradingView 이미지 왼쪽/ Python SVG 오른쪽, 이미지 중첩, 변수별 오차 표, 노드 trace
- `test_engine.py`: 정적 소스 문법, 생성 코드 동등성, 기준자료 부재·수치 불일치·거절 검증
- `../workflows/operations/WF02-chart-parity-first-stage.json`: 기존 n8n 기본 노드 유형만 사용하는 8노드 연결 예제 (현재 `active:false`)

**공통 프로젝트 `shared-n8n-studio`의 노드 종류나 내부 런타임 코드는 수정하지 않는다.** 실제 주식 전략 파싱/렌더링/동등성 규칙은 투자 프로젝트 소유다.

## 주요 HTTP API

```http
GET  /health
POST /api/compare
GET  /api/runs/{run_id}
GET  /api/runs/{run_id}/trace
GET  /artifacts/{run_id}/reference
GET  /artifacts/{run_id}/python.svg
GET  /artifacts/{run_id}/strategy.py
GET  /artifacts/{run_id}/source.pine
GET  /artifacts/{run_id}/tv-export.csv
```

`POST /api/compare` JSON:

```json
{
  "source_url": "https://www.tradingview.com/script/EXAMPLE/",
  "symbol": "NASDAQ:AAPL",
  "timeframe": "1D",
  "pine_code": "//@version=6\nstrategy(...)", 
  "csv_text": "time,open,high,low,close,Fast TV,...",
  "columns": {
    "fastMA": "Fast TV",
    "slowMA": "Slow TV",
    "longCondition": "Long Signal",
    "shortCondition": "Short Signal"
  },
  "screenshot_data_url": "data:image/png;base64,..."
}
```

각 노드 수준 진단에 해당하는 실행 이벤트는 `/api/runs/{run_id}/trace`에서 `node, input, output, status, duration_ms, error`로 내려온다. 원본 전체는 변조 없이 개별 아티팩트 경로로 저장한다.

## 배포와 테스트

- `n8n/Dockerfile.pine-parity.railway` : Python 3.12 stdlib 기반 독립 서비스
- Railway 서비스: `investment-pine-parity-review`
- 데이터 볼륨: `/data` → SQLite와 원본 캡처·CSV·Pine·Python 파일 영속화
- GitHub Actions: `.github/workflows/pine-parity-first-stage.yml`
- 기존 n8n Workflow는 그대로 유지하며 `WF02-chart-parity-first-stage.json`은 실제 백엔드와 연결할 준비용 **비활성 8노드**이다. 실제 n8n 환경에서 `PINE_PARITY_SERVICE_URL`과 승인·인증을 설정하기 전에는 활성화해서는 안 된다.
- 공개 테스트 페이지는 인증·사용자 소유권 격리가 없는 데모이므로 비공개 Pine 코드, 인증 키, 계정 정보나 민감한 차트는 업로드하지 말 것.

## 미완성 항목

- TradingView 로그인 브라우저를 통한 자동 원본 전략 적용·차트 데이터 취득·스크린샷 생성은 미구현
- Pine v5/v6 전면 문법 변환, 주문 체결 조건 완전 동등성·멀티타임프레임·외부 라이브러리 지원은 미구현
- 같은 화면에서 원본과 Python 이미지 비교가 가능하지만, 자동 시각 동등성 PASS와 실전 전략 1개 전체 1차 승인은 아직 미완료
- 본 서비스를 통해 실거래, 계좌 연결, 신호 자동매매 실행은 불가능
