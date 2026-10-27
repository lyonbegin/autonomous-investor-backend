# 테스트 및 배포 계획

검증 환경: Codex Linux x86_64, Python 3.13.16, Node 24.19.0, CPU torch 2.14.1+cpu, Docker 28.4.0, Chromium `/usr/bin/chromium`. 일시: 2026-10-27T21:41:26+09:00.

명령은 별도 표시가 없으면 저장소 루트에서 실행했다. Python은 `/workspace/.onboarding/autonomous-investor-backend/py313/bin/python`을 사용했다. 원본 21개 브랜치의 SHA는 BRANCH_INTEGRATION_MATRIX를 참조한다. 변경은 통합 브랜치의 작업 트리에서 검증했다.

| 실행 명령 | 실제 결과 | 검증 수준 / 한계 |
|---|---|---|
| `python scripts/install_integrated_stack.py --skip-nautilus --source-dir /workspace/integration-audit/upstream-src` | 기존 11엔진 설치 성공 | L1 설치, 원본 2개 메타데이터 오버레이 유지 |
| 저장소 release wheel 다운로드 + SHA-256 검증 + `pip install --no-deps <wheel>` | Nautilus 정확한 wheel 설치 성공 | TLS·체크섬 검증 유지 |
| 공식 PyTorch CPU index에서 `torch==2.14.1+cpu` 설치 + 불필요 GPU 의존성 제거 | 성공, `pip check` 통과 | 로컬 CPU 개발 범위 |
| `python scripts/verify_integrated_stack.py` | 12 import / 브리지 / native demo / FastAPI probe 모두 성공 | L2 소규모 계산, 실제 시장/브로커/LLM 연구 아님 |
| `python -m pytest -q -p no:cacheprovider` | 117 passed, 2 deprecation warnings | 콜백 테스트의 n8n 호출은 일부 mock; 별도 실제 큐 검증도 수행 |
| 각 `investment_studio`, `public_frontend`, `frontend`, `public-frontend`의 `npm install --package-lock=false` + `npm run build` | 4개 TypeScript/Vite 빌드 성공 | 대형 JS bundle 경고; 모든 운영 화면 E2E 아님 |
| `python scripts/verify_local_ui.py` | Chromium 4 passed; 10개 합성 시나리오, F01/F03/F05 UI 검증 | 로컬 임시 DB·fixture; 실제 주문 없음 |
| `COMPOSE_PROJECT_NAME=codex-integration-20261027 bash n8n/scripts/run_real_n8n_e2e.sh` | 등록 13, 시나리오 큐 성공 10, 운영 큐 성공 3 | 원본 n8n 2.44.5 + Redis + PostgreSQL, fixture 출처·PAPER·감사 |
| `python scripts/audit_external_egress.py` / `python app/core/egress_audit.py` | 모두 통과 | 정적 검사이며 모든 동적 HTTP 호출의 포괄 증명 아님 |
| `BUILDX_CONFIG=/workspace/.onboarding/buildx docker build --secret id=cloud_ca,src="$SSL_CERT_FILE" -f Dockerfile.tradingview ...` | 성공 | 프록시 CA를 BuildKit secret으로 제공, 이미지에 CA/키 저장 안 함 |
| 동일 명령의 `Dockerfile.quant-lab` | 성공 | 서비스별 이미지 |
| 각 이미지 기동 후 `/health`, 익명 관리 GET, 인증 GET | 두 서비스 모두 200 / 401 / 200 | 실제 컨테이너 + 임시 DB; 운영 배포 아님 |
| `/workspace/.onboarding/autonomous-investor-backend/install-integrated.sh` | 재실행 성공: 12엔진 verifier / 당시 116 tests / egress / 4개 UI 빌드; 최종 suite는 117 tests | 기존 설치 상태에서 재실행; 새 작업 snapshot 복원은 미검증 |

## 재현할 환경 초기화

```bash
export PATH=/workspace/.onboarding/autonomous-investor-backend/py313/bin:$PATH
export PYTHONDONTWRITEBYTECODE=1
export XDG_CACHE_HOME=/workspace/.onboarding/cache
export MPLCONFIGDIR=/workspace/.onboarding/matplotlib
export ARTIFACT_SIGNING_KEY_PATH=/workspace/.onboarding/rdagent/artifact_signing.key
export PICKLE_CACHE_FOLDER_PATH_STR=/workspace/.onboarding/rdagent/pickle-cache
export WORKSPACE_PATH=/workspace/.onboarding/rdagent/workspace
export LOG_TRACE_PATH=/workspace/.onboarding/rdagent/log
```

네이티브 SB3 demo는 CPU CartPole 16 step만 학습하며 외부 비용/거래를 발생시키지 않는다. native demo와 모든 엔진을 사용한 실제 시장 전체 DAG는 다르다.

## 실패 진단 이력

- RD-Agent read-only home → upstream이 지원하는 artifact/cache/workspace/log 경로 재지정, 서명 유지 후 성공.
- 원래 egress 정적 검사에서 n8n gateway 직접 urlopen 감지 → 기존 내부 HTTP client로 합쳐 응답 크기 제한과 인증 계약 보존 후 통과.
- 원래 복원한 AlphaForge 데모의 의존성 누락 → 원본 @xyflow/react 의존성 복원, 새 편집기 제작 없이 빌드 통과.
- Docker buildx read-only home → BUILDX_CONFIG 변경. 컨테이너 TLS CA 누락 → optional cloud_ca secret 지원, TLS 검증 유지 후 빌드·실행 성공.
- n8n worker 내부 요청 프록시 403 → Compose의 NO_PROXY/no_proxy에 로컬 서비스 이름만 지정. 외부 정책은 우회하지 않았다.
- 32GiB 디스크의 설치·컨테이너 동시 사용으로 PostgreSQL migration/initdb ENOSPC → 공식 CPU torch로 교체, 의존성 역참조 검사 후 GPU-only 18개 제거. 해당 변경 뒤 12엔진 verifier와 실제 n8n 큐 검증 성공. 전체 12엔진 모놀리식 이미지 재빌드는 이 환경에서 수행하지 않았다.
- n8n의 선택적 외부 MCP registry 조회 api.n8n.io는 403을 기록했으나 로컬 핵심 13개 실행은 성공했다. 이를 운영 네트워크 정상으로 해석하지 않는다.

## 스테이징·운영 배포와 롤백

1. 먼저 Railway 읽기 권한으로 서비스별 실제 branch/image/Dockerfile·DB·volume·schedule·backups를 재조회한다.
2. 별도 staging DB/Redis/n8n owner/credentials로 서비스 하나씩 배포한다. 운영 데이터·볼륨에 test fixture를 적재하지 않는다.
3. 관리 endpoint의 새 인증과 서비스 전용 token bindings를 확인한다. 공개 Caddy allowlist·관리 POST 401/403·실거래 금지·원본 n8n owner와 gateway 인증을 검증한다.
4. 수집→전략 라이선스/동등성 검토→PAPER 할당→독립 감사→UI까지 staging E2E를 확보한다. 엔진별 lifecycle/resource isolation과 실행 ID 상관관계도 보완한다.
5. Production 변경·스키마/데이터 migration·비밀 회전·실거래는 승인과 롤백 계획을 준비한 후 수행한다.
6. 롤백은 서비스별 이전 배포 SHA/image를 기록하고 그 배포로 복구한다. 운영 DB 복구는 사전 snapshot과 호환성 검증 후 별도 승인한다. 로컬 source 롤백은 새 분리 브랜치에서 이전 SHA를 조사하며 reset/clean으로 사용자 파일을 지우지 않는다.

## 미실행 / 미검증

Railway live 19개 재조회, 최신 Horizon·macro·회사채 cron 결과와 데이터 적재, 운영 n8n owner/credentials/DB workflow 대조·인증 후 native editor 브라우저 E2E, 완전한 L3 staging·L4 production, 실거래 L5. 새 task에서 snapshot 복원은 미검증이다.

원본 보존 참고: `patches/rdagent-pydantic-ai-1.70.patch`의 빈 context 행은 유효한 unified diff의 공백 한 글자다. git whitespace 검사는 이를 경고하지만 원본 패치 형식을 보존했다.

## 사용자 확인 단계 추가 검증

122개 Python 테스트, 12개 엔진 실제 worker lifecycle/demo, 실제 API 응답을 사용하는 브라우저 13개 항목, n8n 노드별 입력/출력, Caddy 설정 검증을 완료했다. n8n repeated-test DB 재사용 및 worker readiness를 보완했다. 기존 Compose 프로젝트 재사용 차단도 실제로 확인했고 기존 실행 세션을 보존했다. 테스트와 캡처·실행 경계·실패 이력은 REVIEW_READY.md를 참조한다.
