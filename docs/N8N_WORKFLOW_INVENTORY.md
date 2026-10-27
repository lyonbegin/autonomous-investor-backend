# n8n 워크플로 인벤토리

소스 조사: 2026-10-27T21:37:36+09:00. 배포 JSON과 운영 DB를 명확히 구분한다.

| 파일 | 정의 ID | 이름 | 노드 수 |
|---|---|---|---|
| `n8n/workflows/operations/F01-strategy-sync.json` | `aiOperationF01` | F01 전략 풀 증분 수집 | 5 |
| `n8n/workflows/operations/F03-agent-allocation.json` | `aiOperationF03` | F03 유휴 PAPER 에이전트 원자적 할당 | 5 |
| `n8n/workflows/operations/F05-independent-audit.json` | `aiOperationF05` | F05 PAPER 이벤트 독립 감사/리스 확인 | 5 |
| `n8n/workflows/scenarios/01-new-strategy.json` | `autonomousScenario01` | AI-01 | 신규 전략 수집→검증→에이전트 할당 | 6 |
| `n8n/workflows/scenarios/02-version-update.json` | `autonomousScenario02` | AI-02 | 전략 버전 업데이트와 승인 배포 | 6 |
| `n8n/workflows/scenarios/03-capital-race.json` | `autonomousScenario03` | AI-03 | 두 에이전트 자금 충돌 | 6 |
| `n8n/workflows/scenarios/04-partial-fill.json` | `autonomousScenario04` | AI-04 | 부분체결과 중복 주문 방지 | 6 |
| `n8n/workflows/scenarios/05-long-backtest.json` | `autonomousScenario05` | AI-05 | 병렬 장시간 백테스트와 거래 지속 | 6 |
| `n8n/workflows/scenarios/06-strategy-drift.json` | `autonomousScenario06` | AI-06 | 전략 성과 악화 감사와 수정 | 6 |
| `n8n/workflows/scenarios/07-broker-timeout.json` | `autonomousScenario07` | AI-07 | 브로커 타임아웃과 주문 상태 복구 | 6 |
| `n8n/workflows/scenarios/08-agent-crash.json` | `autonomousScenario08` | AI-08 | 에이전트 장애와 Lease 복구 | 6 |
| `n8n/workflows/scenarios/09-unsupported-pine.json` | `autonomousScenario09` | AI-09 | 지원하지 않는 Pine 최신 전략 격리 | 6 |
| `n8n/workflows/scenarios/10-strategy-retire.json` | `autonomousScenario10` | AI-10 | 전략 폐기와 포지션 정리 | 6 |

위 13개는 기존 배포 정의다. 운영 n8n DB에서 확인한 수·ID·active 상태가 아니다.

별도 복원한 `n8n_scenarios/build_workflows.py`는 `INVESTSCENARIO01`~`INVESTSCENARIO10`을 생성한다. 기존 운영 정의와 ID/API 계약이 다르므로 자동으로 운영에 import하지 않는다. callback URL은 `/api/v1/alpha/scenario-control/internal/...`로 분리했다.

원본 UI: `n8n/Caddyfile.native-editor-gateway`가 기존 main을 인증 후 프록시한다. 기존 InvestmentStudio·AlphaForgeStudio는 원본 n8n UI가 아니다.

운영 owner 설정, DB 워크플로, credentials, 활성화, 실제 실행 이력 및 인증 후 브라우저 편집은 미검증이다. 과거 `showSetupOnFirstLoad=true` 기록은 현재 상태를 증명하지 않는다. 노출된 과거 임시 자격증명은 재사용 금지이며, 실제 회전은 승인 및 운영 접근 후 수행한다.

로컬 큐 검증 결과 및 실패 이력은 TEST_AND_DEPLOYMENT_PLAN을 참조한다. 로컬 성공을 운영 성공으로 바꾸어 기록하지 않는다.

로컬 실제 검증 최종 결과: n8n 2.44.5 Main+Worker / Redis / PostgreSQL에서 webhook 13개 등록, autonomousScenario01~10 각 1건 success, aiOperationF01/F03/F05 각 1건 success를 DB로 확인했다. 운영 DB와 owner 상태는 여전히 미검증이다.
