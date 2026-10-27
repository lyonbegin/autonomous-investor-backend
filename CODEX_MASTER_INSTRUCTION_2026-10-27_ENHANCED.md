# CODEX MASTER INSTRUCTION — 2026-10-27 통합 보완판
## AUTONOMOUS INVESTOR — 전체 프로젝트 인수인계 및 완전 통합 개발 지시서

당신은 기존 ChatGPT에서 장기간 개발해 온 **AUTONOMOUS-INVESTOR 주식 자동화 프로젝트**의 후속 개발 담당 AI입니다.

이 프로젝트는 신규 프로젝트가 아닙니다. 이미 GitHub에 여러 개발 브랜치가 있고, Railway에 Python 백엔드, n8n, React 관리 화면, TradingView 수집기 및 관련 인프라가 구축되어 있습니다.

**가장 중요한 명령: 특정 브랜치 하나만 선택하지 마십시오. 지금까지 개발한 전체 구현을 분석하고 하나의 통합 프로젝트로 복원하십시오.**

> **인수인계 문서 상태:** 이 문서는 2026-10-27 사용자 제공 원본 16개 장을 보존하고 같은 날 GitHub/Railway에서 확인한 사실 및 이전 대화의 후속 개발 결과를 보강한 판본입니다. 아래에 기록한 커밋·배포·서비스 상태는 조사 시점의 스냅샷이지 현재 정상 동작의 영구 보증이 아닙니다. 소스 코드, 실행 로그, 외부 HTTP 테스트, 실제 권한 확인으로 다시 검증하십시오.
>
> **Codex 이전의 의미:** Codex가 GitHub 저장소와 Railway 프로젝트에 연결해 *기존 작업 전체를 이어받도록* 하는 것이며, 이 마크다운만으로 코드·DB·n8n 실행 상태가 Codex 환경으로 자동 복사되는 것은 아닙니다. GitHub/Railway CLI 및 연결 권한은 Codex 실행 환경에서 별도 확인하십시오.

현재 대화에서 사용자가 별도로 지정하지 않더라도 아래 범위 전체를 필수 개발 대상으로 간주하십시오.

---

# 1. 원본 프로젝트

GitHub 저장소:

https://github.com/lyonbegin/autonomous-investor-backend

Railway 프로젝트:

`AUTONOMOUS-INVESTOR`

현재 알려진 운영 관리 화면:

https://investment-n8n-operations-ui-production.up.railway.app/

기존 n8n 원본 편집기 접근 게이트웨이:

https://investment-n8n-native-editor-production.up.railway.app/

위 주소와 배포 상태는 인수인계 기록입니다. 현재 정상 작동 여부는 실제로 재검증하십시오.

기존 저장소, 데이터베이스, Railway 서비스, n8n 워크플로를 임의로 삭제하거나 초기화하지 마십시오.

# 2. 모든 브랜치를 조사하고 통합하십시오

최소한 다음 브랜치를 확인하십시오.

- `main`
- `integration-lab`
- `feature/investment-12-engine-workflow`
- `feature/public-demo-readonly-20261025`
- `feature/secure-selfhost-deployment` (2026-10-27 실제 확인)
- `secure-selfhost` 관련 통합 브랜치
- 그 밖의 TradingView, n8n, React, Python, 에이전트, 감사 및 투자 전략 관련 브랜치

`secure-selfhost`는 브랜치 식별을 위한 키워드입니다. 실제 이름을 확인하십시오.

실행할 초기 조사:

```bash
git status
git remote -v
git fetch --all --prune
git branch -a
git log --all --oneline --decorate -50
```

다음 사항을 조사하십시오.

1. 각 브랜치의 최종 커밋 및 변경 이력
2. 브랜치 사이의 공통 조상과 병합 관계
3. 12개 엔진의 원본 및 최신 구현
4. 엔진 어댑터와 투자 워크플로
5. Python API와 미들웨어
6. n8n 운영 워크플로
7. TradingView 수집 및 전략 분석 코드
8. React 운영 관리 화면
9. React 공개 프론트엔드
10. Railway Docker 및 서비스 설정
11. 전략 감사, 위험 관리, 백테스트 코드
12. 이전 브랜치에는 있지만 최신 브랜치에서 사라진 기능

파일 이름만 비교하지 말고 실제 코드와 동작을 분석하십시오.

최신 브랜치에 없다는 이유로 기존 기능을 폐기하지 마십시오.

브랜치 전체를 무조건 병합하는 것도 금지합니다. 구현 단위로 의존성과 충돌을 분석한 후 안전하게 통합하십시오.

통합 작업용 새 브랜치를 만들고 기존 브랜치와 `main`을 보존하십시오.

# 3. 12개 투자 엔진 전체 복원 및 통합

12개 엔진은 선택 기능이 아닙니다.

**반드시 12개 전체를 필수 범위로 포함하십시오.**

`integration-lab`의 설치·검증 스크립트와 `feature/investment-12-engine-workflow`의 엔진 어댑터를 포함하여 모든 관련 브랜치에서 실제 엔진 구현을 조사하십시오.

각 엔진에 대해 다음 내용을 기록하십시오.

- 엔진의 실제 이름
- 원본 GitHub 프로젝트
- 현재 설치 여부
- 사용 언어 및 프레임워크
- 필요한 의존성
- 주요 기능
- 기존 소스 및 어댑터 경로
- API 인터페이스
- 다른 엔진과의 의존성
- 실행 및 테스트 방법
- 현재 정상 작동 여부

12개 엔진의 이름을 임의로 만들어서는 안 됩니다.

기존 코드에 정의된 원본 엔진 목록을 기준으로 정확하게 12개를 확정하십시오.

기능이 중복되는 엔진은 소스를 무리하게 합치지 않고 기존 구현을 유지하면서 어댑터를 통해 연결하십시오.

각 엔진은 독립적으로 시작, 종료, 상태 조회 및 오류 추적이 가능하도록 구성하십시오.

설치 실패를 성공으로 보고하지 마십시오.

# 4. 시스템 전체 아키텍처

목표는 다음 구성 요소를 하나의 시스템으로 연결하는 것입니다.

**데이터 수집 계층**

TradingView, 시장 데이터, 가격·거래량 데이터, 전략 및 지표, 거시경제 데이터

↓

**전략 분석 계층**

Pine Script 분석, 신호 생성, 전략 분류, 전략 평가, 백테스트

↓

**12개 투자 엔진**

각 엔진의 분석, 예측, 최적화, 위험 평가 및 전략 처리 기능

↓

**에이전트 계층**

전략별 에이전트 생성, 전략 할당, 실행 상태, 성능 평가 및 위험 관리

↓

**n8n 오케스트레이션**

전략 수집, 검증, 에이전트 배치, 실행 상태 관리, 감사 및 장애 처리

↓

**Python 백엔드 / API / 미들웨어**

통합 데이터 모델, 이벤트 처리, 작업 실행, API 제공, 상태 기록

↓

**React 프론트엔드**

전략 탐색, 시장 분석, 에이전트 모니터링, 운영 현황, 백테스트 결과

↓

**Railway 배포 인프라**

PostgreSQL, Redis, Python 서비스, n8n, 브라우저 수집기, 웹 애플리케이션

모든 계층이 독립적으로 유지보수 가능하면서 통합 API와 이벤트 계약을 통해 연결되도록 하십시오.

# 5. n8n 노드 플로우 UI — 최우선 원칙

**별도의 React Flow 노드 편집기를 개발하지 마십시오.**

이전 개발 과정에서 이 요구가 반복적으로 잘못 해석되었습니다.

사용자의 명시적 요구는 다음과 같습니다.

- 기존 n8n의 원본 노드 에디터 사용
- 기존 n8n의 노드 및 연결선 사용
- 기존 n8n의 워크플로 실행 화면 사용
- 기존 n8n의 노드별 입출력 데이터 사용
- 기존 n8n의 실행 기록 사용
- 새로운 복제 편집기 제작 금지

React 관리 화면은 n8n 원본 편집기와 연동하는 역할만 수행합니다.

연동 과정에서는 기존 n8n 기능을 훼손하거나 인증을 우회하지 마십시오.

기존 운영 워크플로 F01, F03, F05 및 다른 모든 워크플로를 검색하십시오.

기존 10개 시나리오 테스트와 실제 n8n 운영 워크플로를 구분하십시오.

n8n의 실제 노드 실행 상태와 사용자 인터페이스에서 표시하는 시뮬레이션 상태를 혼동하지 마십시오.

# 6. TradingView 완전 통합

다음 사이트를 기능적 벤치마킹 대상으로 사용하십시오.

https://kr.tradingview.com/ideas/

https://kr.tradingview.com/markets/

https://www.tradingview.com/scripts/

필수 기능:

1. TradingView 아이디어 탐색
2. 시장별 탐색
3. 종목별 분석
4. 전략 및 지표 탐색
5. 카테고리별 전략 정리
6. Pine Script 원본 코드 등록
7. Pine Script 버전 및 라이선스 기록
8. 전략별 차트 분석
9. 전략 신호와 실제 시장 데이터 연결
10. 전략 평가 및 백테스트
11. 전략별 에이전트 자동 할당
12. 새로운 전략 수집 및 변경 감지

사용자는 단순히 TradingView와 비슷한 아이디어를 제안받기를 원하지 않습니다. 실제 전략 데이터와 코드를 활용할 수 있는 시스템을 원합니다.

가능한 경우 공식 API와 허용된 데이터 접근 방법을 우선하십시오.

제3자 소스의 라이선스와 서비스 이용 조건을 준수하십시오. 특히 CC BY-NC-SA와 같은 비상업적 라이선스의 코드를 상업적으로 사용할 수 있다고 가정하지 마십시오.

TradingView의 저작권이 있는 UI나 콘텐츠를 무단 복제하지 말고, 필요한 탐색·분석 기능을 자체 시스템에서 구현하십시오.

AlphaForge는 분석 사이트 설계와 기능의 참고 대상으로 취급하되, 소스나 콘텐츠를 무단 복제하지 마십시오.

# 7. React 프론트엔드 복원 및 확장

기존 `investment_studio` 및 관련 React 코드를 조사하십시오.

확인해야 할 기존 구성 요소에는 다음이 포함됩니다.

- `ScenarioConsole.tsx`
- `OperationsConsole.tsx`
- 기존 전략·에이전트 관리 컴포넌트
- 기존 API 클라이언트
- TradingView 탐색 관련 컴포넌트

필수 화면:

1. 통합 대시보드
2. TradingView 아이디어
3. TradingView 시장
4. TradingView 전략과 Pine Script
5. 12개 엔진 목록 및 운영 상태
6. 투자 에이전트 목록 및 상세 상태
7. 에이전트별 적용 전략
8. 전략별 성과와 백테스트
9. n8n 원본 워크플로 연결
10. 10개 시나리오 실행 화면
11. 실행 로그 및 감사 기록
12. 시스템 운영 관리

메뉴와 UI 문구는 기술적으로 영어가 필요한 경우를 제외하고 한국어로 작성하십시오.

UI를 독자적으로 전면 재설계하기 전에 기존 컴포넌트를 최대한 재사용하십시오.

# 8. 기존 10개 시나리오 보존

다음 시나리오를 모두 유지하십시오.

1. 신규 전략 발견 및 할당
2. 전략 버전 변경
3. 에이전트 자금 경쟁
4. 부분 체결 처리
5. 장시간 백테스트
6. 전략 성능 악화
7. 브로커 응답 지연
8. 에이전트 장애 복구
9. Pine Script 변환 실패
10. 전략 폐기 및 종료

각 시나리오에서 다음을 확인하십시오.

- 시나리오 선택
- 실행 시작
- 진행 상태 조회
- 단계별 상태 변경
- 노드별 실행 결과
- 입력 및 출력 데이터
- 오류 발생 위치
- 최종 완료 또는 실패 결과

현재 합성 시뮬레이터와 실제 n8n 워크플로는 분리하여 표시하십시오.

실제 매매 실행을 하지 않는 시나리오는 명확하게 시뮬레이션이라고 표시하십시오.

# 9. Railway 전체 인프라 복원

기존 Railway 프로젝트는 `AUTONOMOUS-INVESTOR`입니다.

이전 기록은 약 17개였으나 **2026-10-27 production 환경의 서비스 목록은 19개**로 재조회되었습니다(아래 부록 참조). 이후에도 숫자와 배포·실행 상태를 다시 확인하십시오.

확인 대상:

- Python API
- 공개 API
- React 공개 프론트엔드
- React 운영 관리 화면
- n8n 메인
- n8n Worker
- TradingView 브라우저 서비스
- TradingView 전략 수집기
- Horizon 수집기
- Quant Lab
- 거시경제 수집기
- PostgreSQL
- Redis
- 관련 스케줄 작업 및 프록시

기존 서비스명, 서비스 ID, 환경변수 이름, 네트워크 연결, 포트, 데이터베이스 연결 및 배포 브랜치를 조사하여 기록하십시오.

비밀값은 출력하거나 GitHub에 커밋하지 마십시오.

확인된 과거 장애:

**Horizon 수집기**

장시간 실행 후 타임아웃 및 작업 충돌이 발생했습니다.

기존에 요청량과 타임아웃을 낮추는 수정이 있었으나 정상 수집이 최종 확인된 것은 아닙니다.

**거시경제 수집기**

Chromium 게이트웨이 HTTP 503 및 상위 API HTTP 502 오류가 발생했습니다. 그러나 **2026-10-27 최근 cron 로그에는 BLS Public Data API 및 미국 재무부(Treasury) 데이터 수집 HTTP 200 성공 기록도 확인**됩니다. 과거 장애를 그대로 현재 장애라고 단정하지 말고, 재현성·누락·최신 데이터 여부를 검증하십시오.

**신규 회사채 수집기**

2026-10-27 추가 확인된 `tradingview-corporate-bond-cron`에서 `database is locked`에 따른 HTTP 502 및 요청 타임아웃 흔적이 보입니다. 별도 필수 장애 항목으로 등록하십시오.

Horizon·거시경제·회사채 수집기의 최신 실행 이력과 DB 적재 결과를 구분해 검증하고 원인을 해결하십시오.

# 10. 인증 및 접근 권한

공개 테스트 관리 화면은 로그인 없이 조회할 수 있어야 합니다.

그러나 다음 기능은 공개적으로 실행될 수 없어야 합니다.

- 실제 주문
- 매매 엔진 관리 명령
- 전략 승인
- 자금 이동
- 에이전트 변경
- n8n 관리 기능
- 비밀정보 조회
- 내부 운영 설정 변경

읽기 전용 공개 기능과 실제 운영 권한을 서버 측에서 분리하십시오.

n8n 원본 편집기는 관리자 기능이므로 보호된 접근 방식을 유지하십시오.

기존 n8n 최초 소유자 계정 설정 상태도 확인하십시오. 2026-10-25 검사에서 `showSetupOnFirstLoad=true`가 반환되어 최초 소유자 설정 미완료 위험이 발견되었으며, 운영 n8n 직접 공개 도메인은 제거한 기록이 있습니다. 현재 상태는 재검증하십시오.

이전 개발에서 생성된 임시 접근 계정과 비밀번호는 안전하게 교체해야 할 대상으로 간주하십시오. 특히 임시 n8n 프록시 접속 비밀번호가 이전 대화에 노출된 이력이 있으므로 **사용 중이라면 최우선 폐기·회전(rotation)** 하십시오. 이 지시서, AGENTS.md, GitHub 커밋, 로그, PR, 테스트 결과에는 평문 비밀번호·토큰·해시·인증 쿠키를 기록하지 마십시오.

인증을 단순히 화면에서 숨기는 것으로 처리하지 마십시오. API 서버와 프록시 모두에서 권한을 검사하십시오.

# 11. 기존 GitHub 개발 성과 보존

이미 다음과 같은 작업이 진행되었습니다.

- Python 백엔드 구현
- n8n 운영 워크플로 구축
- TradingView 수집기 개발
- React 관리 화면 구축
- 10개 합성 시나리오 구현
- 공개 테스트 모드 개발
- Railway 배포
- 공개 API 접근 제어
- Chromium 브라우저 UI 테스트
- n8n 원본 에디터 연결 게이트웨이 구축

이 내용을 초기 개발 참고 정보로 취급하되, 실제 구현 여부는 코드와 테스트로 확인하십시오.

기존 브랜치에 완료된 기능이 있다면 동일한 코드를 중복 개발하지 마십시오.

기존 기능을 복원하는 과정에서 최근에 수정된 접근 제어, Docker 빌드 설정 및 프론트엔드 기능을 잃어버리지 않도록 하십시오.

# 12. 전체 통합 작업 순서

다음 순서로 진행하십시오.

## Phase 1 — 전수 조사

전체 브랜치, 소스, 12개 엔진, Railway 서비스, n8n 워크플로, 데이터베이스, API를 조사하십시오.

조사 결과를 문서화하십시오.

## Phase 2 — 통합 설계

전체 아키텍처와 의존성 그래프를 작성하십시오.

브랜치별 기능 비교표를 만들고 각 구현의 최종 유지 버전을 결정하십시오.

## Phase 3 — 12개 엔진 통합

12개 엔진 전부의 의존성과 어댑터를 정리하고 설치 및 실행을 검증하십시오.

## Phase 4 — 백엔드 통합

Python API, 데이터 수집기, 미들웨어, 전략 분석, 에이전트와 실행 이벤트를 통합하십시오.

## Phase 5 — n8n 통합

기존 n8n 원본을 유지하고 실제 워크플로를 연결하십시오.

## Phase 6 — 프론트엔드 통합

TradingView 탐색, 전략 분석, 엔진 상태, 에이전트 현황, n8n 연결 및 시나리오 화면을 통합하십시오.

## Phase 7 — 검증

단위 테스트, 통합 테스트, Docker 빌드, API 검사, Chromium 화면 검사, 10개 시나리오 테스트를 수행하십시오.

## Phase 8 — 배포 준비

Railway 서비스별 설정 차이를 점검하고 안전한 배포 계획을 작성하십시오.

기존 운영 환경은 보존하고, 가능하면 별도 스테이징 환경에서 먼저 검증하십시오.

실거래 활성화, 운영 데이터 변경 및 파괴적 작업은 사용자 명시 승인 없이 실행하지 마십시오.

# 13. Codex 작업 규칙

다음 규칙을 반드시 지키십시오.

1. 기존 구현 우선, 신규 개발은 부족한 기능에 한정합니다.
2. 12개 엔진 전체를 필수 범위로 취급합니다.
3. 모든 관련 브랜치를 조사합니다.
4. n8n 노드 UI를 별도로 복제하지 않습니다.
5. 기존 GitHub 기록을 보존합니다.
6. Railway 운영 서비스를 임의로 삭제하지 않습니다.
7. PostgreSQL 및 Redis 데이터를 초기화하지 않습니다.
8. 테스트 결과 없이 완료를 선언하지 않습니다.
9. 필요한 경우 코드를 직접 수정하고 테스트합니다.
10. 실행하지 않은 검사를 성공했다고 보고하지 않습니다.
11. 실패한 사항은 로그 및 원인과 함께 보고합니다.
12. 한국어로 진행 상황과 결과를 보고합니다.
13. 기존 사용자 결정을 임의로 뒤집지 않습니다.
14. 코드를 무조건 처음부터 다시 만들지 않습니다.
15. 시뮬레이션 결과와 실거래 결과를 구별합니다.

# 14. 반드시 작성할 인수인계 문서

저장소에 다음 문서를 작성하거나 기존 문서를 갱신하십시오.

- `docs/CODEX_PROJECT_HANDOFF.md`
- `docs/BRANCH_INTEGRATION_MATRIX.md`
- `docs/ENGINE_12_INVENTORY.md`
- `docs/SYSTEM_ARCHITECTURE.md`
- `docs/RAILWAY_SERVICE_INVENTORY.md`
- `docs/N8N_WORKFLOW_INVENTORY.md`
- `docs/TRADINGVIEW_INTEGRATION.md`
- `docs/TEST_AND_DEPLOYMENT_PLAN.md`
- `docs/KNOWN_ISSUES.md`
- 루트의 `AGENTS.md`

`AGENTS.md`에는 앞으로 Codex가 새 작업을 수행할 때도 반드시 지켜야 할 기존 코드 보존, 12개 엔진 필수, n8n 원본 UI 사용, 운영 환경 보호 및 한국어 보고 원칙을 기록하십시오.

문서에 비밀 키나 비밀번호를 기록하지 마십시오.

# 15. 완료 판정 기준

다음 조건이 충족되어야 전체 통합 완료로 판단할 수 있습니다.

- 전체 관련 브랜치 조사 완료
- 12개 엔진의 실제 이름과 원본 확인
- 12개 엔진 설치 및 검증 결과 확보
- Python 백엔드 통합
- 전략 분석 및 데이터 수집 연결
- n8n 원본 워크플로 연동
- React 화면 통합
- 에이전트별 전략 및 실행 상태 표시
- 10개 시나리오 실행 검증
- 자동화 테스트 결과 확보
- Railway 배포 준비 및 안전성 검증
- 기술 문서 작성
- 기존 기능 회귀 테스트 통과

부분적으로 완료했다면 해당 항목만 완료로 표시하십시오.

# 16. 지금 즉시 실행할 명령

현재 Codex가 `feature/investment-12-engine-workflow`만 선택하려는 상황을 수정하십시오.

**나는 해당 브랜치만 선택하지 않습니다. 모든 관련 브랜치의 구현을 하나로 통합하도록 지시합니다.**

먼저 저장소 전수 조사를 시작하십시오.

1. 모든 원격 브랜치를 조회하십시오.
2. 12개 엔진의 정확한 목록을 확인하십시오.
3. 브랜치별 주요 기능 및 차이를 분석하십시오.
4. 현재 Railway와 n8n 연결 구조를 확인하십시오.
5. 충돌 없는 통합 개발 브랜치를 설계하십시오.
6. 인수인계 문서 초안을 생성하십시오.
7. 이후 통합 구현과 테스트를 단계적으로 실행하십시오.

가능한 작업은 직접 수행하십시오. 단순히 개발 계획만 작성하고 종료하지 마십시오.

단, 권한이 없거나 인증이 필요한 외부 작업은 성공한 것처럼 보고하지 말고 필요한 접근 권한을 구체적으로 제시하십시오.

첫 번째 보고에는 다음 표를 반드시 포함하십시오.

| 구분 | 확인된 구현 | 원본 브랜치 | 현재 상태 | 통합 조치 |
|---|---|---|---|---|
| 12개 투자 엔진 | | | | |
| Python 백엔드 | | | | |
| TradingView | | | | |
| Pine Script | | | | |
| n8n 워크플로 | | | | |
| React 프론트엔드 | | | | |
| 전략 에이전트 | | | | |
| 10개 시나리오 | | | | |
| Railway 인프라 | | | | |
| 데이터베이스 | | | | |

**최종 목표는 하나의 브랜치를 선택하는 것이 아니라, 지금까지 개발한 AUTONOMOUS-INVESTOR 시스템 전체를 손실 없이 Codex 환경으로 인계하고 모든 핵심 기능을 통합 개발하는 것입니다.**

지금부터 Phase 1 전수 조사와 통합 개발 브랜치 준비를 실제로 시작하십시오.

---

# 17. 2026-10-27 재확인된 실제 기반 정보 (Codex 신규 필수 지침)

아래는 사용자 제공 기존 문서의 문구를 바탕으로 임의로 지어낸 값이 아니라, **2026-10-27 GitHub/Railway 연결 조회에서 직접 확인한 사실**입니다. 다만 실시간 상태가 아니므로 Codex는 실제 작업 착수 시 다시 조회하여 `observed_at`, 응답 원천, 커밋 SHA, 환경 ID를 함께 기록해야 합니다.

- GitHub: `lyonbegin/autonomous-investor-backend`, 기본 브랜치 `main`, 2026-10-27 조회 당시 원격 브랜치 **21개**.
- Railway: 프로젝트 `AUTONOMOUS-INVESTOR` (`155584dd-b4a4-416c-8f25-c24970c9007c`), `production` 환경 (`891ba96c-9d98-492d-9176-25481e256c60`), 서비스 **19개**.
- 원본 n8n 메인: `investment-n8n-main`은 GitHub `feature/secure-selfhost-deployment`의 Dockerfile `n8n/Dockerfile.main.railway`을 사용하며, 2026-10-25 기록상 `n8nio/n8n:2.44.5`를 기초 이미지로 사용.
- 새 n8n 원본 에디터 게이트웨이: `investment-n8n-native-editor`는 기존 n8n에 연결하는 인증 프록시이며, **별도로 개발된 React Flow 편집기가 아님**.
- 기존 `investment_studio/src/InvestmentStudio.tsx`에는 다른 목적인 **자체 12엔진 DAG 워크플로 편집기**가 남아 있습니다. 이 소스를 무단 삭제하지 마십시오. 다만 이것을 n8n 원본 편집기라고 속이거나, 이를 기반으로 n8n 복제 편집기를 확장해서는 안 됩니다. 별도 기능으로 분류하여 인수인계하고 사용 여부를 결정합니다.

## 17.1 직접 조회한 21개 브랜치

`main`, `integration-lab`, `dependency-lab`, `predeploy-verify`, `sqlite-recovery-temp`, `frontend-vite`, `public-frontend-react`, `public-platform`, `quant-lab-control`, `railway-deploy`, `railway-integrated-deploy`, `tradingview-service`, `feature/alpha-node-api-first`, `feature/alphaforge-react-clone-phase1`, `feature/investment-12-engine-workflow`, `feature/n8n-real-worker-e2e`, `feature/n8n-scenario-control-plane`, `feature/n8n-ten-scenario-console`, `feature/public-demo-readonly-20261025`, `feature/secure-selfhost-deployment`, `feature/strategy-registry-assignment-audit`.

**특히 새로 명시한 확인 대상:** `feature/alphaforge-react-clone-phase1`, `feature/n8n-real-worker-e2e`, `feature/n8n-scenario-control-plane`, `feature/n8n-ten-scenario-console`, `feature/strategy-registry-assignment-audit`, `public-frontend-react`, `public-platform`, `quant-lab-control`, `tradingview-service`. 기존 문서에 적힌 몇 개 브랜치만 확인하고 전수 조사했다고 보고하지 마십시오.

각 브랜치의 *실제 최신 HEAD 및 파일/커밋*을 조사하고, `git merge-base`, `git diff --name-status`, `git log --all`, 심볼/테스트 비교로 **코드 소유권과 기능별 최종 구현**을 확정하십시오. 단순 병합·체리픽으로 완전 통합을 주장하지 마십시오.

# 18. 12개 투자 엔진 — 원본 코드에서 확정된 명칭과 출처

**증거 위치:** `feature/investment-12-engine-workflow:app/core/integrations.py`의 `SPECS`에 정의된 12개 `IntegrationSpec`. 아래는 그 코드에 있는 이름·키·원본 GitHub 저장소입니다. 아래의 **'목록 확인'은 해당 엔진이 실제 운영 환경에 설치되어 정상 구동한다는 뜻이 아닙니다.**

| 내부 키 | 엔진 이름(원본 코드) | 원본 GitHub 프로젝트 | `pinned_ref` (코드 기준) |
|---|---|---|---|
| `tradingagents` | TradingAgents | `TauricResearch/TradingAgents` | `e8f5503e9b86d5c2710b0c76b1f686703968c9df` |
| `finrobot` | FinRobot V2 | `AI4Finance-Foundation/FinRobot` | `2717499b8e30f242640af08c4ad9afd1113c2d45` |
| `rdagent` | RD-Agent(Q) | `microsoft/RD-Agent` | `484776c211e4fbbeef03e0ec00d6bbee7362a4f4` |
| `qlib` | Qlib | `microsoft/qlib` | `54355232463878d2eebb91fe0ee5fa7fa1f5976c` |
| `chronos` | Chronos | `amazon-science/chronos-forecasting` | `1224fafa91e1ecd6674f5204066b159e40b5e4a1` |
| `sb3` | Stable-Baselines3 | `DLR-RM/stable-baselines3` | `b2878f4b83e21f16a53c54a62def628e05fd2e96` |
| `rllib` | Ray RLlib | `ray-project/ray` | `ray-2.59.0` |
| `vectorbt` | vectorbt | `polakowo/vectorbt` | `v1.2.0` |
| `finrl` | FinRL-Trading | `AI4Finance-Foundation/FinRL-Trading` | `4409abe925c904e570be78ebfb5e77ac3491dff8` |
| `riskfolio` | Riskfolio-Lib | `dcajasn/Riskfolio-Lib` | `7b1b26ac9760974c12ecefe290a9d3bd37b66b7a` |
| `pyportfolioopt` | PyPortfolioOpt | `PyPortfolio/PyPortfolioOpt` | `a6638d2e06dae6f444fd022cfd4b3c528902a85b` |
| `nautilus` | NautilusTrader | `nautechsystems/nautilus_trader` | `69aa8a283c8735cee4a536084078e3b19ac9a1be` |

**세부 검증 지침:** 소스의 `pinned_ref`, `python_module`, `symbols`, `probe()` 결과와 설치/런타임 결과를 `docs/ENGINE_12_INVENTORY.md`에 함께 기록하십시오. `app/integrations/`에서 어댑터 12개(예: `pypfopt.py`, `sb3.py`)를 확인했습니다. `integration-lab`은 설치/검증·브리지(`lab/bridges/`) 역할, `feature/investment-12-engine-workflow`는 `app/alpha_nodes/`와 12엔진 DAG에 강하게 관련됩니다. **NautilusTrader를 단일 주문 실행 주체로 설계한 기존 계약**을 먼저 검증하고, 다른 모델이 직접 브로커 주문을 제출하도록 임의 확장하지 마십시오.

`docs/INVESTMENT_NODE_WORKFLOW.md`에는 117개 엔진·래퍼 함수 + TradingView/Quant Lab 서비스 기능 20개 = 137개, 제어 노드 3개를 합쳐 팔레트 140개라는 **기존 구현 명세**가 있습니다. 이 수치가 현재 API에서도 유효한지는 실행 확인이 필요합니다. 각 엔진별 개별 기동/정지, 종속성, 서브프로세스 격리, 타임아웃, 재시도, 메모리/CPU 한도, 결과 스키마와 출처를 확인하십시오.

# 19. n8n 워크플로 / 12엔진 DAG / 10개 합성 시나리오를 반드시 구분

| 구성 | 실제 역할 | 소스 근거 | 사용자에게 보여줄 UI |
|---|---|---|---|
| **n8n 원본** | 운영 플로우 실행/노드 연결/실행 기록 | `n8n/workflows/`, `n8n/Dockerfile.main.railway` | **n8n 원본 에디터** (인증 후 접근) |
| **12엔진 DAG 백엔드** | 노드의 입출력 계약, 병렬 분기/합류, 버전 및 감사 | `app/alpha_nodes/investment_flow.py`, `investment_api.py` | n8n과 혼동 금지. 기존 API/기능 보존 후 통합 접점 분석 |
| **기존 React DAG 화면** | 12엔진 함수를 편집하는 별도 기존 실험·운영 코드 | `investment_studio/src/InvestmentStudio.tsx` | 새 n8n 복제 편집기로 확장 **금지**; 무단 삭제도 금지 |
| **합성 시나리오** | 위험/장애/상태 변경의 가상 이벤트 테스트 | `app/alpha_nodes/scenario_simulator.py`, `ScenarioConsole.tsx` | 명시적으로 `SYNTHETIC` 표기. 실제 거래 아님 |

GitHub 원본에서 확인한 n8n 정의 파일:

- 운영 3개: `n8n/workflows/operations/F01-strategy-sync.json`, `F03-agent-allocation.json`, `F05-independent-audit.json`.
- 시나리오 10개: `n8n/workflows/scenarios/01-new-strategy.json`부터 `10-strategy-retire.json`까지.
- 시작 스크립트: `n8n/scripts/start-railway-n8n.sh`. 최초 DB에 F01이 없을 때 13개 워크플로를 가져오고, 이미 있으면 사용자의 수정 이력/자격증명을 보존하려는 로직이 있습니다. **실제 DB 상태와 게시·활성화 여부는 별도 증거가 필요**합니다.

n8n 시각화가 실제로 완성됐다고 판단하려면, 워크플로를 n8n에서 열었을 때 노드·선·입출력·실행 이력·실패 지점이 보이는지 **브라우저로 검증**하십시오. React 모의 화면이나 Python의 가상 이벤트 진행률 100%만으로 n8n 원본의 실실행 상태를 주장하지 마십시오.

운영·테스트 통합은 다음 계약을 따릅니다.

1. `workflow_id`와 `run_id`, 실제 n8n `executionId`, 백엔드 시나리오 `run_id`를 별개의 식별자로 취급하고 상관관계 키를 저장합니다.
2. n8n 실행 이벤트와 합성 시나리오 이벤트는 `source=n8n|python_simulation|engine_runtime` 등으로 구분합니다.
3. 노드 상태는 `queued/running/success/failed/skipped/cancelled/unknown`을 시간과 원본 출처와 함께 기록합니다.
4. 각 노드의 입력·출력 데이터는 실제 n8n의 권한과 마스킹 정책을 따릅니다. 토큰·PII·브로커 계좌 값은 공개하면 안 됩니다.
5. 원본 n8n 편집기는 관리자 도구이므로 일반 사용자용 공개 화면에 임베딩하거나 인증을 우회하지 않습니다.

# 20. Railway 19개 서비스 현황 — 2026-10-27 스냅샷

**주의:** 아래의 `SUCCESS`는 *최근 배포 성공*을 의미할 뿐 실제 크론 작업/데이터 적재/워크플로 성공을 의미하지 않습니다. 이 표는 인수인계 단서이며 Codex가 최신으로 갱신해야 합니다.

| Railway 서비스명 | ID | 2026-10-27 최근 배포 | 조사/역할 |
|---|---|---|---|
| autonomous-investor-integrated | `02a6cadc-d059-45d5-b89f-618ebe6d611b` | SUCCESS | 통합 API 서비스 / `railway-integrated-deploy` |
| tradingview-collector-cron | `b07ee32b-315e-4da4-a703-cfe5889930e6` | SUCCESS | TradingView 정기 수집 `*/5 * * * *` |
| autonomous-investor-quant-lab | `530b6946-991c-4a67-b2e8-e90249ee515d` | SUCCESS | 퀀트 랩 / `quant-lab-control` |
| autonomous-investor-ui | `693151a6-18e0-4bc9-b5d7-d1a2869b341f` | SUCCESS | UI / `frontend-vite` |
| autonomous-investor-tradingview | `aae76a90-6237-4d0f-a3d0-621dbfe7f14f` | SUCCESS | TradingView 서비스 |
| autonomous-investor-public-D18a | `1b0c086f-8b94-4188-bc6d-6d6d167cb9bd` | SUCCESS | React 공개 프론트 / `public-frontend-react` |
| macro-collector-cron | `66329211-ad39-40d4-8cd4-beb32a4ce494` | SUCCESS | 거시경제 데이터 `15 */6 * * *` |
| autonomous-investor-tradingview-browser | `dce0b284-e16a-49c0-9bd4-6ca1e5136e76` | SUCCESS | 브라우저 수집기 |
| autonomous-investor-public-api | `382a3c15-b224-43c8-a890-6910d0003919` | SUCCESS | 공개 API / `public-platform` |
| investment-n8n-operations-ui | `d5028f56-c90e-40d7-bdcc-037c8c2220e9` | SUCCESS | 비로그인 읽기 + 합성 테스트 화면 |
| investment-n8n-worker | `d982a6d6-268b-4c29-892c-d475403d430d` | SUCCESS | n8n Worker |
| Redis | `1979d38a-942e-49df-959f-5a60625936e4` | SUCCESS | Redis 8.2 / 데이터 보존 |
| autonomous-investor-api | `99323fe2-606d-44b7-8c4a-1a672aab968a` | SUCCESS | `main` 기반 API |
| investment-n8n-native-editor | `6231df4a-7b0b-47be-9097-546472672763` | SUCCESS | **원본 n8n에 대한 인증 프록시** |
| investment-n8n-main | `06f6d322-17da-4ba9-be6a-88e6fb281446` | SUCCESS | n8n 메인, private 5678 포트 |
| tradingview-horizon-v3-cron | `30242c82-5bb3-4a93-856d-f20203bb6b4a` | SUCCESS | Horizon 크론 `*/5 * * * *` / 실행 오류 확인 필요 |
| Postgres | `d31addf0-389d-4cb7-9c67-002b65f68a30` | SUCCESS | PostgreSQL 18 / 데이터 보존 |
| tradingview-corporate-bond-cron | `6f240b92-5fdf-4b1e-8288-12349d3fab39` | SUCCESS | 회사채 ISIN prefix backfill `*/5 * * * *` |
| investment-n8n-ops-api | `0c1c0c69-6c16-41d5-abc7-cecc76036afa` | SUCCESS | Python 운영 API / 영속 볼륨 |

추가로 확인된 데이터 볼륨 이름: `postgres-volume`, `redis-volume`, `investment-operations-data`, `quant-lab-data`, `tradingview-recovery-4gb-Jz6Z`, `tradingview-data`. 실제 마운트·리전·용량·백업 여부는 Codex가 현장 확인하십시오. 저장소의 단일 브랜치가 전체 19개 서비스를 배포하는 구조가 아니며, **서비스마다 연결된 브랜치/이미지/스케줄이 다릅니다**. 통합 브랜치를 바로 전체 production 서비스에 연결하지 마십시오.

# 21. 현재 이슈 및 보안상 중요한 후속 조치

## 21.1 Horizon/거시경제/회사채

- **Horizon:** 2026-10-25 작업량을 `limit=500, max_markets=3`에서 `limit=20, max_markets=1`로 줄이고 HTTP 타임아웃을 100초로 낮춘 변경 이력이 있습니다. 2026-10-27 Railway 화면에서는 최신 배포 `SUCCESS`가 보이지만 최근 런타임 로그 조회에서는 `CRASHED` 흔적이 있습니다. **실제 성공 저장 레코드/마지막 성공 시각과 작업별 로그를 기준으로 실패 여부를 판정**하십시오. 단순 재시도·무작정 타임아웃 증가로 종료하지 마십시오.
- **거시경제:** 과거 Chromium 게이트웨이 HTTP 503/상위 HTTP 502 실패가 있었으나, 2026-10-27 cron 로그에는 **BLS + U.S. Treasury 수집 HTTP 200 성공과 `MACRO-2026-10-27` 스냅샷 생성 기록**이 있습니다. 해결됐다고 영구 선언하지 말고 수집 주기, source_date, 누락/중복, 재실행 멱등성을 검사하십시오.
- **회사채:** 2026-10-27 로그에 `OperationalError: database is locked` (HTTP 502)와 `TimeoutError`가 있습니다. 같은 SQLite DB의 동시 쓰기, WAL/트랜잭션 잠금, 백필 작업 중첩, 작업 간 Lease/Mutex, API-수집기 분리, 재시도/배치 체크포인트를 점검하십시오. 장시간 비동기 작업 분할과 쿼리 적재 수량 검증을 우선하십시오.

## 21.2 인증/접근 제어 보존

- 운영 화면 공개 URL: `https://investment-n8n-operations-ui-production.up.railway.app/`; 과거 테스트에선 홈페이지 GET 200, 읽기 API 200, 관리자 변경 API POST 403.
- n8n 원본 에디터 게이트웨이: `https://investment-n8n-native-editor-production.up.railway.app/`; 보호 프록시 Caddy 소스 `n8n/Caddyfile.native-editor-gateway`, 빌드 `n8n/Dockerfile.native-editor-gateway`. 본체 `investment-n8n-main`과 별개입니다.
- 2026-10-25 원본 n8n `/rest/settings`의 `showSetupOnFirstLoad=true` 기록이 있습니다. 최초 소유자 계정이 아직 없을 가능성이 있어 **공개 직접 도메인은 제거한 이력**이 있습니다. Codex는 현재 설정 상태, 관리자 소유권, 역할 기반 접근, 편집/운영 권한을 확인하십시오.
- 과거 채팅에 임시 게이트웨이 아이디/비밀번호가 공개된 이력이 있습니다. **즉시 비밀번호와 관련 자격증명을 안전한 비밀 저장 경로에서 교체하고, 과거 값을 재사용하거나 문서에 재기재하지 마십시오.** 기존 해시/평문이 소스 또는 빌드 로그에 남았는지 검사하십시오.
- 공개 UI의 Caddy는 명시적인 GET 조회 및 합성 시나리오 실행만 공개합니다. 실패 시 다른 API로 우회하거나 프론트 버튼만 숨기는 방식은 금지합니다. 관리 API와 실거래 관련 endpoint에 서버 측 정책을 적용하고 HTTP 401/403·CSRF·권한 상승 테스트를 통과해야 합니다.
- **추가 검토:** 공개 운영 이벤트에 거래 정보, 전략 원문, 계좌/사용자 식별자 등이 노출될 수 있으므로 응답 필드 allowlist, 이벤트 데이터 마스킹, rate limit, 접근 로그를 점검하십시오.

# 22. 이미 수행한 검증과 *아직 검증하지 않은 것*

아래는 **2026-10-25 당시 GitHub Actions/Chromium 및 Railway 배포 기록**이며, 현재 새 환경에서도 성공한다는 뜻은 아닙니다. Codex는 GitHub Actions run ID·실행 일시·테스트 대상 commit hash·배포 환경을 연결해서 다시 실행하십시오.

| 항목 | 과거 실행 근거 | 검증된 범위 | 한계 |
|---|---|---|---|
| 공개 React + Caddy | `https://github.com/lyonbegin/autonomous-investor-backend/actions/runs/40172874533` | Docker image 빌드, Caddy 설정, 익명 HTML/차단 API 검증 | 실제 매매·모든 UI 경로 아님 |
| 실제 배포 API + 합성 10개 | `https://github.com/lyonbegin/autonomous-investor-backend/actions/runs/40172576444` | 비로그인 GET, 관리자 POST 403, 10개 합성 시나리오 완료 | n8n 원본 실행 증명이 아님 |
| Chromium 화면 검사 | `https://github.com/lyonbegin/autonomous-investor-backend/actions/runs/40172691900` | 실행 버튼→합성 시나리오 진행률·I/O 확인 | 나중 시점 재검증 필요 |
| n8n 게이트웨이 익명 접근 차단 | `https://github.com/lyonbegin/autonomous-investor-backend/actions/runs/40174764036` | 익명 n8n 에디터/REST/API 401 | 인증 뒤 편집·저장/내부 연결 검증은 별도 필요 |
| n8n 원본 연결 메뉴 | `https://github.com/lyonbegin/autonomous-investor-backend/actions/runs/40174978110` | 공개 운영 화면에서 원본 에디터 링크 존재 및 합성 UI 검사 | n8n 소유자 설정 후 네이티브 노드 실행 E2E 미검증 |

**빌드 회귀 방지:** 이전 React 공개 빌드에서 `investment_studio/.env.production`이 `.dockerignore`의 `**/.env.*`로 제외되어 `VITE_PUBLIC_DEMO=true`가 적용되지 않은 사례가 있었습니다. `!investment_studio/.env.production` 예외 및 `n8n/Dockerfile.web.railway`의 공개 모드 설정 검사가 추가되었습니다. 이 회귀 테스트를 반드시 유지하십시오. `VITE_*`에는 비밀값을 넣지 마십시오.

**완료로 보고하면 안 되는 항목:** 모든 엔진 원본 실제 설치/훈련/추론, 실거래 브로커 연결, TradingView Pine 원본 전수 합법 수집, 지표→실행전략 동등성, 전체 n8n 실행 이력의 브라우저 E2E, Horizon 및 회사채 수집 영속 정상화, 전체 서비스 통합 회귀 검증.

# 23. TradingView·Pine·AlphaForge 관련 보완 계약

TradingView의 `ideas/`, `markets/`, `scripts/`는 계속 수집되거나 갱신되는 콘텐츠이므로 **초기 전수 조사 + 증분 갱신 + 원본 버전 추적**을 따로 구현합니다. 사용자가 원하는 것은 실제 데이터/전략 연결이지 가상 전략 아이디어 목록이 아닙니다.

- 전략/지표 정보에는 `source_url`, 출처, 작성자, 게시·수정일, Pine 버전, 라이선스, 원본 수집 방식, 사용 허용 범위, code hash, revision, classification, 최초/최종 수집 시각, 캡처 결과를 분리 저장합니다.
- Pine v6에서 `indicator()`와 `strategy()`를 구분하고, **시각화 지표를 거래 신호/검증 완료 전략으로 자동 승격하지 않습니다**. 외부 Pine 소스를 Python으로 변환한다면 테스트 벡터와 TradingView 원본과의 신호 동등성 검증을 명시합니다.
- 사용자가 언급했던 BigBeluga `Dynamic Liquidity Clouds` 등 제3자 Pine 예시에서는 CC BY-NC-SA 4.0 같은 비상업적 라이선스가 있을 수 있습니다. 원문 출처·저작권·재배포·상업 이용 허용 여부를 저장하고, 라이선스가 허용하지 않으면 배포·상업 사용을 금지합니다.
- TradingView 웹 사이트의 로그인/약관/robots/공식 제공 데이터 접근 권한을 준수합니다. 브라우저를 이용해도 접근 제어나 제한을 우회하지 않습니다. 실시간 차트 원본 내부 데이터를 임의로 모두 가져올 수 있다고 가정하지 말고, 확보 가능한 데이터 소스·차트·시그널 근거를 구분하십시오.
- AlphaForge 및 TradingView UI는 **기능·사용성 벤치마킹 대상**입니다. `feature/alphaforge-react-clone-phase1` 및 프론트 브랜치의 실제 코드부터 비교하지만 UI/저작물의 무단 복제·브랜드 혼동·제3자 코드 무단 재배포는 금지합니다.
- 관리자가 전략을 선택할 때 다수 에이전트 후보를 제안하거나 자동 매칭할 수 있어도, 라이선스·신호 재현·독립 백테스트·리스크 승인·사람의 승인 없이 실거래로 배치하지 않습니다.

# 24. Codex 작업 환경으로 옮길 때의 실행 순서

**Codex에 이 문서를 제공한 다음 순서대로 실제 조사를 실행하도록 하십시오.** 한 번의 대화에서 마크다운을 붙여 넣었다고 전체 GitHub 코드/DB/실행 환경이 이미 복사된 것은 아닙니다.

## 24.1 세션 및 환경 준비

1. Codex 작업 폴더에서 저장소를 **읽기 전용 조사**부터 시작합니다. 도구·계정 연결이 필요한 경우 GitHub/Railway 자격증명을 공식 연결/비밀 관리 기능으로 설정하고, 연결이 안 된 영역은 별도로 보고합니다.
2. 로컬 변경분이 있다면 덮어쓰지 않고 `git status --porcelain=v1`, `git remote -v`, `git branch -avv`, `git worktree list`로 확인합니다. 기존 사용자의 변경 파일은 임의 폐기하지 않습니다.
3. `git fetch --all --prune`은 허용되지만, 기존 작업 트리에서 임의 `reset --hard`, `clean -fdx`, `push --force`, 직접 `main` 변경, `git merge` 일괄 실행은 금지합니다.
4. 각 관련 브랜치마다 분리된 `git worktree` 또는 안전한 검사 디렉터리를 사용하여 비교합니다. 통합 브랜치는 기존 HEAD를 손상시키지 않는 새 이름으로 만듭니다.
5. 날짜/시간, 시스템·Python/Node 버전, 네트워크 접근성, 실제 테스트 명령, 성공·실패·미실행을 로그와 함께 기록합니다. Codex 도구가 기존 ChatGPT의 연결 권한을 자동 공유한다고 가정하지 않습니다.

## 24.2 기능별 차이와 통합 리스크 확인

먼저 `docs/BRANCH_INTEGRATION_MATRIX.md`에 기능별 **브랜치 → 소스 경로 → 테스트 → 사용 중인 Railway 서비스 → 최종 선택 구현 → 충돌/손실 위험** 매핑을 만듭니다. 특히 12엔진 어댑터/137 API + 140 노드 명세, Python 운영 API, n8n 13개 JSON 및 실제 DB 워크플로, 공개 화면 Caddy/React, TradingView/시장/Pine, 회사채/거시경제 수집기, 인증 게이트웨이를 각각 독립 축으로 검사하십시오.

일관성을 위해 주요 계약 객체 및 테스트를 정의합니다.

- `StrategySource`, `StrategyVersion`, `LicenseEvidence`, `PineParseReport`, `EligibilityDecision`
- `MarketDataSnapshot`, `BacktestRun`, `Signal`, `RiskDecision`, `TargetPortfolio`
- `Agent`, `AssignmentLease`, `FencingEpoch`, `OrderIntent`, `ExecutionReport`, `AuditFinding`
- `WorkflowDefinition`, `WorkflowRun`, `NodeRun`, `ScenarioRun`, `EventEnvelope` (각각 `source`, `created_at`, 상관관계 ID, 스키마 버전 보유)

이는 신규 구현을 무조건 만들라는 뜻이 아니라 기존 모델과 비교하여 누락된 필드만 안전하게 보완하라는 요구입니다.

## 24.3 검증 수준 (혼동 금지)

| 등급 | 뜻 | 예시 |
|---|---|---|
| L0 | 소스/설정 존재 | 12개 어댑터 파일, n8n JSON 13개 |
| L1 | 빌드/구문/단위 테스트 통과 | Python pytest, TypeScript build, Caddy validate |
| L2 | 테스트 환경에서 실제 API/엔진·n8n 실행 성공 | 비밀정보 마스킹된 실행 로그와 trace |
| L3 | 스테이징에서 종단 간 통합 및 회귀 검증 | 데이터 수집→전략 검토→에이전트 PAPER→감사→UI |
| L4 | 운영 상태 검증 | 실제 서비스/DB/스케줄의 안정적 실행, 권한 검사, 데이터 적재 증거 |
| L5 | 실거래 활성화 | **별도 사용자 명시 승인 전 수행 금지** |

각 기능 상태는 `미조사`, `소스 존재`, `빌드 성공`, `테스트 성공`, `운영 검증`, `실패`, `보류` 중 실제 증거에 맞게 표시합니다.

## 24.4 배포 및 백업

- Production Postgres/Redis/SQLite 볼륨을 초기화·삭제·마이그레이션하기 전에 스냅샷, 되돌리기 계획, 롤백 기준을 준비합니다. 데이터 변경/파괴적 변경/실거래는 사용자 승인이 필요합니다.
- 개발/테스트 서비스에는 별도 DB·토큰·비밀을 사용하고 기존 운영 메인 n8n의 Owner/Credential/워크플로 데이터를 덮어쓰지 않습니다.
- Railway `source.branch`가 서비스별로 다르므로 대량 브랜치 전환은 금지합니다. 서비스별 배포 diff, 헬스 체크, 권한 테스트, 스모크 테스트, rollback 계획을 작성합니다.
- 비밀값은 Codex 응답·로그·파일 아티팩트에 노출하지 않습니다. 잠재적으로 노출된 값은 회전한 사실과 회전 대상 이름만 기록합니다.

# 25. Codex에게 요구할 첫 결과물과 작업 시작 지침

원본 16장의 `Phase 1` 지침과 아래 기준을 함께 수행하십시오. 첫 보고는 다음을 반드시 포함합니다.

1. **기존 문서의 10개 항목 통합 현황표** (12개 엔진 / Python / TradingView / Pine / n8n / React / 에이전트 / 시나리오 / Railway / DB). 각 행에 브랜치·파일 경로·증거·실제 실행 여부·남은 조치를 작성합니다.
2. **21개 브랜치 재조회 결과** (이름, SHA, 핵심 기능, 최종 유지 코드, 충돌 위험)와 통합 브랜치 후보.
3. **12개 엔진 정확한 이름과 상태** (위 18장 참조, 설치·테스트 미확인 사항은 `미확인`).
4. **Railway 최신 서비스 개수와 스케줄/환경/볼륨** (19개라는 2026-10-27 스냅샷에 얽매이지 말고 재조회).
5. **n8n 실제 워크플로 수와 ID**, 배포 JSON과 DB 워크플로의 차이 및 소유자 초기화/게이트웨이 보호 상태.
6. **Horizon, 거시경제, 회사채 작업**의 마지막 성공·실패 시각, 적재 결과, DB 동시성 문제.
7. **바로 실행한 테스트의 명령·출력·실패 원인**. 실행하지 않았다면 명확히 `미실행`으로 표시.
8. **다음 변경 대상과 롤백 방법**. production 직접 수정보다 비파괴적 브랜치/스테이징 검증 우선.

**Codex에 대한 마지막 우선순위:** (1) 기존 코드와 데이터 보존 → (2) 전체 브랜치/12엔진 전수 조사 → (3) 원본 n8n UI 연결 및 권한 → (4) 수집기 안정화·실제 데이터 → (5) Python/에이전트/React 통합 → (6) 검증 가능한 스테이징 배포. 이미 동작하는 기능의 UI를 임의로 다시 만드는 일을 가장 마지막으로 미루십시오.
