# n8n 공식 GitHub 원본 소스 기반 Railway 빌드

2026-10-27 기준

## 사용자 요구

기존 n8nio/n8n 완성 이미지나 별도 React Flow 복제 화면을 최종 노드 편집기로 취급하지 않는다.
공식 n8n 원본의 Vue 노드 편집기, CLI, 기본 노드 구현을 설치 및 검증한다.

## 원본 출처

- 저장소: https://github.com/n8n-io/n8n
- 태그: n8n@2.44.5
- 커밋: e993c789c83dba66030f3b0259b42e452b64c3b9
- 실행 정의: n8n/Dockerfile.upstream-source.railway
- Node.js: 26.10.0
- pnpm: 12.4.2
- 빌드: pnpm install --frozen-lockfile --trust-lockfile && pnpm build:deploy
- Railway: AUTONOMOUS-INVESTOR / investment-n8n-source-editor
- 서비스 ID: f41f099f-1d8f-4213-a32b-88fae08d3689

## 현재 확인된 기록

첫 시도: zx 미설치 상태에서 build:deploy 실행으로 실패.
두 번째 시도: pnpm 선행 설치를 추가하여 72/72 패키지 빌드 성공. Vue editor 및 CLI 빌드 통과. Docker 런타임과 브라우저 접속은 배포 완료 후 별도 확인한다.

## 앞으로 확인할 것

1. compiled 프로덕션 산출물 생성 및 Docker 이미지 완성
2. n8n 독립 테스트 인스턴스 기동과 /healthz 응답
3. 브라우저에서 공식 Vue 노드 캔버스가 표시되는지 검증
4. 기존 F01/F03/F05 및 10개 시나리오 JSON 가져오기
5. 개발용 로그인 없는 편집 경험: 실제 소스 변경 범위와 데이터·네트워크 격리 조건 별도 검증. 운영 인스턴스의 인증을 변경하지 않는다.
6. 실행/저장/편집 테스트 결과를 GitHub Actions와 Railway 로그로 보존

## 데이터 보호 및 기능 구분

기존 운영 n8n, PostgreSQL, Redis, 인증 정보에 접근하거나 이관하지 않는다. 새 소스 인스턴스에는 운영 거래용 자격 증명을 주입하지 않는다. n8n의 공식 미리보기나 합성 시뮬레이터를 '완전한 노드 편집기'로 보고하지 않는다. 소스 컴파일 성공, 컨테이너 배포 성공, 실제 브라우저 편집 성공은 각각 다른 검증 항목이다.


## 실제 배포 및 브라우저 검증 결과 (2026-10-27 15:38 UTC)

- Railway 소스 빌드 서비스: `investment-n8n-source-editor` (f41f099f-1d8f-4213-a32b-88fae08d3689)
- 적용 소스 커밋: `cb7d512c427434f9213b6d6e5589212e1c209a64`
- 원본 n8n 버전: `2.44.5`, 컴파일 성공 72/72
- Node 26.10용 `isolated-vm` 재컴파일 성공(`UPSTREAM_NATIVE_ISOLATED_VM_BUILT`)
- 최종 Railway 배포: `8093cb09-75c5-488b-9fb6-b3b869a23200`, SUCCESS. 로그에 `Editor is now accessible via: http://0.0.0.0:5678`
- 공개 원본 노드 캔버스 포털: https://investment-n8n-native-editor-production.up.railway.app/
- 포털은 13개 저장소 JSON을 `openWorkflow` 포스트메시지로 **공식 n8n Vue 데모 노드 캔버스**로 로드한다. React Flow 대체 그래프를 사용하지 않는다.
- 로그인 없음: 격리된 원본 소스 인스턴스에 `N8N_PREVIEW_MODE=true` 적용, 브라우저 기본 인증 사용하지 않음
- 원본 노드 정의 API 및 Vue SPA HTTP 200 확인: https://github.com/lyonbegin/autonomous-investor-backend/actions/runs/40532105119
- Chrome 실브라우저: F01 노드 5, 엣지 4; 시나리오 01 노드 5; 워크플로 버튼 13 확인: https://github.com/lyonbegin/autonomous-investor-backend/actions/runs/40532910219
- Chrome 스크린샷 아티팩트: `original-n8n-chrome-fast-proof`, 아티팩트 ID `12746043106`
- 운영 관리 화면도 원본 노드 캔버스 바로가기 복구 배포 완료, 빌드 검사 https://github.com/lyonbegin/autonomous-investor-backend/actions/runs/40530996637

### 아직 구현하지 않은 범위 — 완료라고 표현하지 말 것

공개된 원본 Vue 화면은 `/workflows/demo` 경로의 **로그인 없는 노드 미리보기 캔버스**다. 소스 기반으로 만든 진짜 n8n UI지만 전체 관리자 편집/DB 영속 저장/임의 노드 실행은 제공하지 않는다. 별도의 운영 n8n에서 돌린 10개 합성 워크플로의 실제 Webhook 테스트 결과는 기존 React 운영 대시보드에서 확인한다. 13개 JSON은 포털이 로드하며 이 새 소스 인스턴스의 n8n DB에 import된 것은 아니다. 이 구분을 다음 Codex 인수인계와 사용자 보고에서 유지할 것.
