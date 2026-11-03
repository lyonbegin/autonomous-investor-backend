# WF-02: 무료 로컬 PYNE로 DDDS Pine 141줄 전체 변환

전략 원본: TradingView 게시 DDDS, 원본 SHA256 5a245e99447f13012dd026528235fc2c299cad5cb7b228653c684886dcba6507.
무료 hoox-pyne[compile]==0.6.31, https://github.com/hoox-sh/pyne (AGPL-3.0). 상용 PyneComp API 불필요.
생성된 실제 DDDS Python SHA256 ef27e69cbb71bc101431a2f9f71783c37f1f8094a7a77e080032ca3bbd7994a1.

## 기존 WF02 그대로 6노드
N01 원본/권리 확인 → N02 참조 Library 해석 → N03 무료 컴파일 라이브러리 지원 검사 → N04 PYNE 로컬 CLI로 Pine 전체 Python 생성 → N05 원본 SHA/변환본 SHA 저장(SQLite 별도 테이블 및 기존 PostgreSQL) → N06 결과/미검증 상태 반환.
Library import 지원이 불확실한 코드는 실패로 차단하며 다른 전략 코드로 대체하지 않는다.

## 오른쪽 차트
실제 공개 TradingView NASDAQ:AMZN 120분봉 최근 300개를 Chromium Worker가 읽고, 생성된 정확한 DDDS Python 파일을 별도 시간제한 프로세스에서 실행한다.
Decycler, Price anchor, Gradient, Lower/Upper band, Stop, Target 시계열과 주문 이벤트를 UI에서 볼 수 있다.
현재 공개 300봉 시험에서 전략 이벤트 0건; TradingView 장기 백테스트 299건과 일치하는 것이 아니다.
저자 차트 스냅샷 BATS:AMZN과 공식 보고서 현재 Properties NASDAQ:AMZN도 다르다.
전체 2016~2026 데이터와 TV 주문/체결 시각 검증 없이는 동등성 승인 불가; PAPER/LIVE 거래 비활성.
컴파일된 Python의 런타임은 PYNE이며 PyneCore와 호환된다고 가정하지 않는다.

## 검증
Python WF02 6노드: .github/workflows/wf02-free-pyne-ddds.yml
실제 AMZN 300봉 PYNE Python 직접 실행: .github/workflows/wf02-free-ddds-amzn-runtime.yml
Railway 원본 UI 실브라우저: .github/workflows/wf02-free-pyne-live-browser.yml

## 라이선스
hoox-sh/pyne는 AGPL-3.0. 네트워크 서비스 배포 시 해당 라이선스의 소스 제공 의무에 주의할 것.
DDDS 원본은 MPL-2.0. 출처 및 저작권 표시를 유지할 것.
무료 API 비용과 소스 라이선스 준수는 별개다.
