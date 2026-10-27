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
