# 브랜치 통합 매트릭스

조사: 2026-10-27T21:32:36+09:00. 출처: origin 원격 refs 재조회 및 fetch, merge-base, 전체 tree/diff, Python 최상위 심볼 비교. 브랜치 21개.

통합 브랜치: `codex/full-system-integration-20261027`. 원래 `work`와 원격 `main` 보존. 공개 데모 계열 이력은 fast-forward로 포함하고, 갈라진 브랜치는 아래 기능 단위로 복원했다. 일괄 merge/push/production 배포는 하지 않았다.

심볼 존재 비교만으로 동작 동등성을 보장하지 않는다. 원본별 전체 diff와 snapshot은 `/workspace/integration-audit/`에 남겼고, 선택 파일의 출처는 `docs/integration/source-selections.json`에 보존한다.

| 브랜치 | HEAD SHA | 기능 | 유지 코드 | 충돌·손실 위험 | 기반 브랜치에 포함된 조상 |
|---|---|---|---|---|---|
| `dependency-lab` | `822887542b818d0f3bc76227965e7c2d7f43765b` | 구형 어댑터·의존성 실험 | `app/adapters/, patches/, scripts/dependency_probe.py` | 구형 계약과 현재 integrations 계약 혼용 금지 | 아니오; 기능별 비교 |
| `feature/alpha-node-api-first` | `5dcebdc9b53e142bfa9c0bdbb09803ed3d253094` | 엔진 함수 API·승인 게이트 | `app/alpha_nodes/api.py, runtime.py, palette.py` | 후속 DAG/보안 버전 우선 | 예 |
| `feature/alphaforge-react-clone-phase1` | `bf11e3a0a584a20b13abecfd3b107a77a4112d3b` | 기존 데모 DAG·공개 UI | `public_frontend/src/pages/AlphaForgeStudio.*` | 기존 데모만 보존; n8n UI로 사용하지 않음 | 아니오; 기능별 비교 |
| `feature/investment-12-engine-workflow` | `1c524a87d83c3254e27863f91c86f1d8b154a5eb` | 12엔진 DAG·실행 이력 | `app/alpha_nodes/investment_flow.py, investment_api.py` | 정의 삭제와 실행 감사 기록 구분 | 예 |
| `feature/n8n-real-worker-e2e` | `58e68a9391ee44ba67128f8186ab4645a8d366f8` | 큐 Worker 검증·합성 UI | `n8n/scripts/run_real_n8n_e2e.sh, investment_studio/` | 운영 DB 대신 별도 로컬 Compose 검증 | 예 |
| `feature/n8n-scenario-control-plane` | `16af59b98d65e9374be1e4d4960cb448bbd44145` | 단계별 콜백 제어 | `app/alpha_nodes/scenario_control_api.py, scenario_runtime.py, n8n_scenarios/` | scenarios 경로 충돌 → scenario-control 네임스페이스로 복원 | 아니오; 기능별 비교 |
| `feature/n8n-ten-scenario-console` | `6786d8298bc62958056fd72fbed569646939dde0` | 10개 합성 시나리오 | `app/alpha_nodes/scenario_simulator.py, investment_studio/src/ScenarioConsole.tsx` | n8n 실제 실행과 합성 결과 구분 | 예 |
| `feature/public-demo-readonly-20261025` | `6c1cbc457f8f0ccfece5b6adc355af56d7e1da1f` | 인증·공개 데모·원본 n8n 게이트웨이 | `n8n/Caddyfile.railway, Caddyfile.native-editor-gateway` | 통합 기반으로 이력 포함; 다른 브랜치 기능은 별도 복원 | 예 |
| `feature/secure-selfhost-deployment` | `744403a08451214e027d0a0fd3a3cad59264c774` | 안전한 서비스별 배포 | `n8n/Dockerfile.*, n8n/scripts/` | 공개 인증 정책은 후속 공개 데모 버전 보존 | 예 |
| `feature/strategy-registry-assignment-audit` | `c7790236c603f528cd15bffbb184b7784934836c` | 전략 버전·Lease·독립 감사 | `app/alpha_nodes/operations_core.py, operations_api.py` | 임의 승인·실거래 금지; 기존 원자적 할당 유지 | 예 |
| `frontend-vite` | `3c04fa1df32708bbec645b50fea1cbe036300fd0` | 시장·에이전트 관리 UI | `frontend/` | 기존 하드코딩 운영 URL과 데모 데이터를 운영 검증으로 오인 금지 | 아니오; 기능별 비교 |
| `integration-lab` | `62930972f2c47163b6fc77196e06fb46d83c6670` | 현재 12엔진 설치·브리지 | `lab/, scripts/install_integrated_stack.py, app/integrations/` | 의존성 오버레이 2개와 정확한 Nautilus 휠 보존 | 예 |
| `main` | `a9a904bfd20e6d279c556598241eade22bcc93b1` | 최소 FastAPI 운영 API | `app/core/contracts.py, app/api/routes.py` | 기존 main 변경·push 없음; 통합 브랜치에서 확장 | 예 |
| `predeploy-verify` | `ae950da07466e86a7622f31df00064e493a68dc0` | 검증 휠 기반 이미지 | `Dockerfile.release-wheel` | 원본 root Railway 설정은 일괄 복원하지 않음 | 아니오; 기능별 비교 |
| `public-frontend-react` | `b2d18836fe1883276e496fe8fc90ee56eb50891e` | 공개 React·Pine 런타임 | `public_frontend/` | 기존 ideas→scripts 리다이렉트로 사라진 아이디어 화면 재연결 | 아니오; 기능별 비교 |
| `public-platform` | `a45b5655730f85d3800d9c37b96221e5731be6b2` | 공개 API·이전 공개 UI | `public_api/, public-frontend/` | public_frontend와 public-frontend는 별도 앱; 구형도 보존 | 아니오; 기능별 비교 |
| `quant-lab-control` | `9f8b348a72932f23f6c9f7ad7c819601612cc3ec` | 실험·거시경제·시장 이력·Pine | `app/main_quant_lab.py, app/core/quant_lab.py, market_history.py, pine_visual.py` | 새 인증 게이트에 맞춰 서버 전용 서비스 토큰 전달 | 아니오; 기능별 비교 |
| `railway-deploy` | `25b53d5eb2ebee72733d9c33c188de8b18ae173d` | 구형 통합 이미지 | `Dockerfile.railway-legacy` | 역사적 빌드 방식 보존; 전체 서비스에 일괄 적용 금지 | 아니오; 기능별 비교 |
| `railway-integrated-deploy` | `564cffb33fb2c1247e63574443a60638f83acb16` | 브라우저 경유 데이터 egress | `app/core/browser_http.py, scripts/audit_external_egress.py` | 최신 TradingView 브라우저 기능과 병합 | 예 |
| `sqlite-recovery-temp` | `f489e27bac047bc15f421a5f0b985bb708d3af9e` | 수동 SQLite 복구 | `recovery/recover.sh` | 조사만 수행, 운영 DB에 실행 금지 | 아니오; 기능별 비교 |
| `tradingview-service` | `af9b07928a5be7b6b75a0c5d47cf8f4d37738af3` | 최신 시장·Pine·회사채·소스 레지스트리 | `app/main_tradingview.py, app/core/tradingview.py, source_registry.py, corporate_bonds.py, browser_worker/` | 초기 API보다 큰 확장; 오래된 파일로 역덮어쓰기 금지 | 아니오; 기능별 비교 |

## 공통 조상과 변경량

| 브랜치 | 공개 데모 기반과 공통 조상 | 파일 수 | 기반과 다른 경로 수 |
|---|---|---|---|
| `dependency-lab` | `92da6d3965cc116dc1d448ee25d5e6e3c695ab97` | 38 | 187 |
| `feature/alpha-node-api-first` | `5dcebdc9b53e142bfa9c0bdbb09803ed3d253094` | 89 | 86 |
| `feature/alphaforge-react-clone-phase1` | `b2b5eb79e1661426b59f136323b5f8d54694bc08` | 110 | 140 |
| `feature/investment-12-engine-workflow` | `1c524a87d83c3254e27863f91c86f1d8b154a5eb` | 101 | 78 |
| `feature/n8n-real-worker-e2e` | `58e68a9391ee44ba67128f8186ab4645a8d366f8` | 128 | 58 |
| `feature/n8n-scenario-control-plane` | `1c524a87d83c3254e27863f91c86f1d8b154a5eb` | 118 | 91 |
| `feature/n8n-ten-scenario-console` | `6786d8298bc62958056fd72fbed569646939dde0` | 119 | 75 |
| `feature/public-demo-readonly-20261025` | `6c1cbc457f8f0ccfece5b6adc355af56d7e1da1f` | 168 | 0 |
| `feature/secure-selfhost-deployment` | `744403a08451214e027d0a0fd3a3cad59264c774` | 159 | 15 |
| `feature/strategy-registry-assignment-audit` | `c7790236c603f528cd15bffbb184b7784934836c` | 141 | 35 |
| `frontend-vite` | `b2b5eb79e1661426b59f136323b5f8d54694bc08` | 79 | 109 |
| `integration-lab` | `62930972f2c47163b6fc77196e06fb46d83c6670` | 69 | 104 |
| `main` | `a9a904bfd20e6d279c556598241eade22bcc93b1` | 14 | 165 |
| `predeploy-verify` | `fe354e0bcf95648f218d6ad685668b5afa558440` | 74 | 108 |
| `public-frontend-react` | `b2b5eb79e1661426b59f136323b5f8d54694bc08` | 106 | 136 |
| `public-platform` | `b2b5eb79e1661426b59f136323b5f8d54694bc08` | 104 | 134 |
| `quant-lab-control` | `4b3cadcd5f1b5afb1bfd1e142e7defea763b776d` | 86 | 109 |
| `railway-deploy` | `62930972f2c47163b6fc77196e06fb46d83c6670` | 71 | 105 |
| `railway-integrated-deploy` | `564cffb33fb2c1247e63574443a60638f83acb16` | 76 | 96 |
| `sqlite-recovery-temp` | `4b3cadcd5f1b5afb1bfd1e142e7defea763b776d` | 78 | 107 |
| `tradingview-service` | `4b3cadcd5f1b5afb1bfd1e142e7defea763b776d` | 84 | 108 |

## 검토 범위와 미통합 항목

- Python 심볼 비교에서 남은 경로상 차이는 기존 scenario_api의 콜백 구현이며, 동일 기능을 scenario_control_api로 이동했다. 함수 이름이 남아 있다는 사실은 모든 구현 버전의 동등성을 뜻하지 않는다.
- 브랜치별 CI/루트 railway.toml은 서비스별 설정이므로 무조건 합치지 않았다. 기존 원격 refs와 조사 snapshot에서 복구 가능하다.
- Workbench와 AlphaForge 데모의 대체 main.tsx는 활성화하지 않았다. 현재 원본 n8n 링크와 운영·합성 화면을 보존한다.
- 운영 Railway 서비스별 연결 브랜치·DB·볼륨 및 인증 이후 원본 n8n 실행은 접근 권한 확보 뒤 재검증해야 한다.
