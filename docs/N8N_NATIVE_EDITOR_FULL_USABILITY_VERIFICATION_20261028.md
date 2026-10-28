# n8n 공식 원본 편집기 사용성 검증 최종 보고서 — 2026-10-28

## 검증 범위와 배포 대상
- 공식 원본: https://github.com/n8n-io/n8n (tag n8n@2.44.5, commit e993c789c83dba66030f3b0259b42e452b64c3b9)
- 소스 수정 브랜치: feature/n8n-native-editable-test-20261028
- 검증 URL: https://investment-n8n-native-editor-production.up.railway.app/
- Railway 격리된 Vue 원본 소스 서버: investment-n8n-source-editor (f41f099f-1d8f-4213-a32b-88fae08d3689)
- 최신 검증 배포: 6371aa68-946c-4225-a8a6-6912f64460fc, SUCCESS, source commit 607922554a8be12590b1e5966e02615b8aceafa8
- 공개 프록시/선택 포털: investment-n8n-native-editor, SUCCESS
- 테스트 워크플로: scenarios/01-new-strategy.json, 합성 데이터만 사용
- **운영 n8n과 실제 매매는 테스트하지 않음; 변경 없음**

## 실제 사용자 브라우저 검사 결과

최종 원본 소스 서버 배포 후, 아래 GitHub Actions 5개를 재실행했고 모두 completed/success.

| 항목 | 실조작 합격 조건 | 증거 |
|---|---|---|
| 노드 추가/삭제·Undo/Redo | 기본 6 → NoOp 추가 7 → Delete 6 → Ctrl+Z 7 → Ctrl+Shift+Z 6; 상단 Undo/Redo 버튼도 검사 | https://github.com/lyonbegin/autonomous-investor-backend/actions/runs/40651471500 |
| 원본 노드 선택기·추가·브라우저 저장·재접속 | 13개 워크플로 메뉴, 원본 NodeCreator 표시, 6→7, 직렬화된 NoOp 타입 확인, 새로고침 후 7개 | https://github.com/lyonbegin/autonomous-investor-backend/actions/runs/40651496368 |
| 실제 Chrome 마우스로 노드 이동·연결선 | 노드 좌표 368,240 → 544,352; 엣지 기본 5, 노드 추가 자동 연결 6, 실제 핸들 드래그 후 7; JSON에 7개 연결 및 새 위치 저장 | https://github.com/lyonbegin/autonomous-investor-backend/actions/runs/40651478025 |
| 노드 설정값 수정·저장·새로고침·JSON 다운로드 | HTTP Request URL http://example.invalid/usability-regression-check 로 입력; 좌표 480,320 저장; 새로고침 후 URL/위치 동일; 다운로드한 01-new-strategy.json에서 변경 URL 확인 | https://github.com/lyonbegin/autonomous-investor-backend/actions/runs/40651485155 |
| 복제·이름 변경·연결선 삭제 | NoOp 복제 시 총 8개, rename 모달로 NoOp UX renamed, 직렬화 JSON에도 저장; 선 추가 5→6, 원본 엣지 툴바 삭제 버튼으로 6→5 | https://github.com/lyonbegin/autonomous-investor-backend/actions/runs/40651489861 |

모든 테스트는 GitHub Actions의 실제 headless Chrome 마우스/키보드 조작이며, 프론트 HTML이나 정적 함수 존재 여부만 확인한 결과가 아니다. 각 실행에서 업로드한 이미지·JSON 아티팩트는 링크의 Actions Artifacts에서 확인 가능하다.

## TinyFish 사용성 교차 검사
- https://agent.tinyfish.ai/runs/44b3534e-1144-43c5-8845-897684d66479
- iframe 내 HTTP Request 설정 URL 입력 변경 성공.
- 해당 TinyFish 런에서는 복잡한 VueFlow 마우스 드래그/엣지 연결을 검증하지 못했으나, 위의 **동일 URL에 대한 Playwright/Chrome 실제 마우스 조작**으로 별도 교차 검증 성공.
- TinyFish 런이 수행하지 않은 항목을 TinyFish 자체 성공으로 표시하지 않는다.

## 남은 기능·범위의 명확한 구분
1. '변경 저장'은 테스트 브라우저 localStorage에 워크플로 JSON 초안을 저장하고 동일 브라우저에서 복원한다. **n8n 서버 DB에 영구 저장하는 기능은 아님.**
2. 편집/연결/Undo와 실제 노드 실행/워크플로 스케줄링은 다르다. 현재 프리뷰 편집 환경에서 실제 투자 주문이나 외부 웹훅을 실행하지 않는다.
3. 별도 운영 n8n 인스턴스의 입력·출력·실시간 실행 시각화 및 서버 측 워크플로 버전/공동 편집은 이번 검증 범위가 아니며 아직 완료로 판단하지 않는다.
4. 로그인 없는 테스트용 원본 Vue 모드는 운영 사용자/권한/자격증명을 노출하기 위한 기능이 아니다.

**판정: 격리된 테스트 원본 n8n Vue 편집기에서 사용자 편집→저장→복원 UX 시나리오 전체 통과(5/5). 운영 n8n의 완전한 영구 저장·실행 편집기라고 보고해서는 안 된다.**
