# 실제 서버 배포 안내 — Railway 미사용

## 지금 검증된 범위와 현재 배포 상태

- 이 브랜치의 `docker-compose.production.yml`은 **실제 React 정적 사이트 + Caddy HTTPS + 내부 FastAPI + n8n + PostgreSQL + Redis/Worker**를 한 대의 VPS에 설치한다.
- 사이트 진입과 `/studio-api/*`는 모두 Caddy 비밀번호 인증이 필요하다. FastAPI 전용 Bearer 키는 서버의 Caddy→FastAPI 요청에서만 추가된다.
- n8n UI는 SSH 포워딩을 통한 `127.0.0.1:5678`에서만 열며 Postgres/Redis는 외부 포트가 없다.
- CI는 임시 GitHub Runner 안에서 **실제 production container 이미지**를 빌드하고 React HTML/서버 API 인증 401·200을 검증할 수 있다. CI 서버는 요청이 끝나면 제거된다.
- **사용자 VPS 계정·IP·SSH Key·실제 도메인을 제공받지 않은 상태에서 상시 인터넷 서버로 배포했다고 주장하면 안 된다.**
- Railway를 통한 배포는 하지 않는다. 이번 작업은 실제 VPS용 구성이고, Render는 연결을 선택할 때만 배포할 수 있다.

## 요구 조건

본인 소유 Ubuntu 24.04 VPS 또는 Docker Engine + Compose를 설치한 Linux 서버, 고정 공인 IP, 도메인 DNS A/AAAA 레코드, 인바운드 TCP 80/443 및 UDP 443 오픈, Git, Docker Compose, curl, openssl. DB/Worker가 항상 켜져 있어야 하므로 무료 CI 러너만으로 운영 서버를 대신할 수 없다.

## 처음 1회 준비

1. GitHub 리포지토리 `lyonbegin/autonomous-investor-backend`의 `feature/secure-selfhost-deployment` 브랜치를 본인 서버에 체크아웃한다.
2. `cp n8n/.env.example n8n/.env` 실행 후 운영 서버에서만 서로 다른 강력한 비밀번호와 고정된 암호화 키를 생성한다.
3. `INVESTMENT_DOMAIN`에 실제 도메인을 적는다. `invest.example.com` 그대로는 설치 스크립트가 거부한다.
4. `INVESTMENT_ADMIN_PASSWORD_HASH`는 평문이 아니라 Caddy bcrypt 해시여야 한다.

예:

```bash
cd "$HOME/apps/autonomous-investor-backend"
git checkout feature/secure-selfhost-deployment
cp n8n/.env.example n8n/.env
openssl rand -hex 32
docker run --rm caddy:2.10-alpine caddy hash-password --plaintext 'USE_A_STRONG_UNIQUE_PASSWORD'
chmod 600 n8n/.env
# 편집기에서 n8n/.env 모든 REPLACE_*와 도메인 값을 안전하게 설정
bash n8n/scripts/deploy_selfhost.sh
```

실제 비밀번호·API 키·DB 암호는 GitHub에 업로드하거나 이 대화에 붙여넣지 않는다. 해시의 `$`가 손상되지 않도록 `.env`에 홑따옴표로 묶는다. 해시를 공개하더라도 평문 비밀번호를 함께 공개하지 말 것.

## UI / 백엔드 / n8n 접근

| 서비스 | 접근 경로 | 외부 노출 |
|---|---|---|
| 실제 React 운영 UI | `https://<설정한-도메인>/` | 관리자 HTTP Basic Auth 필요 |
| 서버 인증 BFF API | `https://<도메인>/studio-api/api/v1/ops/overview` | 관리자 인증 후 Caddy가 Bearer 토큰 추가 |
| 기존 10개 시나리오 | `https://<도메인>/studio-api/api/v1/alpha/scenarios` | 관리자 인증 필수 |
| n8n 관리자 | SSH 포트포워딩 `127.0.0.1:5678` | 외부에 공개하지 않음 |
| FastAPI | 서버 자체 `127.0.0.1:8000` | 외부에 공개하지 않음 |
| PostgreSQL / Redis | Docker 내부 네트워크 | 외부에 공개하지 않음 |

n8n 관리자 접근:

```bash
ssh -L 5678:127.0.0.1:5678 YOUR_VPS_USER@YOUR_VPS_IP
# 로컬 브라우저에서 http://127.0.0.1:5678 접속
```

## n8n 워크플로 가져오기 및 인증

```bash
cd n8n
docker compose -f docker-compose.yml -f docker-compose.backend.yml -f docker-compose.production.yml exec -T n8n \
  n8n import:workflow --separate --input=/srv/n8n-workflows
docker compose -f docker-compose.yml -f docker-compose.backend.yml -f docker-compose.production.yml exec -T n8n \
  n8n import:workflow --separate --input=/srv/n8n-operation-flows
```

위 명령은 JSON 10개 시나리오와 운영 플로우 3개를 n8n DB에 저장할 뿐이다. **자동으로 API Credential이 설정되거나 활성화되지는 않는다.** n8n 관리자 UI에서 HTTP Header Auth Credential을 `Authorization: Bearer <서버의 ALPHA_NODE_API_KEY>`로 만들고 HTTP Request 노드에 연결해 저장·게시한다. 최초 설정 후 n8n에 실제 성공 실행 로그가 남는지 확인해야 한다. 기존 JSON을 재수입하면 수정사항이 덮일 수 있으므로 최초 구축 이후에는 무작정 import를 재실행하지 않는다.

## 실제 배포 검증

```bash
# 비로그인 요청은 HTTP 401이어야 함
curl -I https://YOUR_DOMAIN/
# 관리자 계정 로그인 시 React HTML 반환
curl -u 'ADMIN_USER:ADMIN_PASSWORD' https://YOUR_DOMAIN/
# 서버가 Bearer를 안전하게 전달하여 운영 DB 응답 반환
curl -u 'ADMIN_USER:ADMIN_PASSWORD' https://YOUR_DOMAIN/studio-api/api/v1/ops/overview
```

로그는 본인 VPS에서 `docker compose ... logs -f`로 확인한다. TLS 인증서 발급을 위해 공인 DNS와 80/443 포트가 필요하다. 인증서 자동발급이 안되면 프록시 컨테이너 로그와 DNS/방화벽을 확인한다. 비밀번호는 CI 로그나 GitHub 저장소에 남기지 않는다.

## GitHub에서 명시적으로 내 VPS에 배포

`.github/workflows/deploy-own-vps.yml`은 `workflow_dispatch` + 실제 서버 SSH 접속 + 특정 커밋 체크아웃 + 실제 Docker Compose 기동 + 외부 HTTPS 401 검증까지 진행한다. 이 액션은 **VPS 연결 설정 없이는 배포되지 않는다.**

GitHub Repository → Settings → Environments에서 `selfhost-production` 환경을 만들고 배포 승인 규칙 설정, Actions secrets에 `VPS_HOST`, `VPS_USER`, `VPS_SSH_PRIVATE_KEY`, `VPS_KNOWN_HOSTS` 등록이 필요하다. SSH의 host key는 대상 VPS의 실제 공개 호스트 키와 일치하는 것으로 핀한다. 서버에는 프로젝트 Git 소스 및 비공개 `n8n/.env`가 있어야 한다.

GitHub UI에서 **Deploy to OWN VPS** 실행 시 confirm_deploy=`DEPLOY`, public_https_url=`https://본인도메인`을 입력한다. 이 workflow가 기본 브랜치에서 처음부터 수동 실행 목록에 표시되려면 GitHub 정책상 워크플로 파일이 기본 브랜치에도 존재해야 한다. 검증되지 않은 다른 코드를 병합하지 말고 별도 배포 워크플로 변경만 검토하여 올릴 수 있다.

## 현재 기능 경계

운영 F01은 실제 TradingView 업스트림에 접근 가능한 경우에만 수집한다. `ALPHA_TRADINGVIEW_BASE`가 없으면 라이브 수집은 HTTP 503으로 막히며, 자동으로 기존 Railway 주소를 사용하지 않는다. F03은 **PAPER 배정 상태**만 관리하고 NautilusTrader의 실제 전략 프로세스/브로커 연결까지 시작하지 않는다. F05는 관측 이벤트 감사이지 독립적인 브로커 원장 조회가 아니다. LIVE 실거래와 주문은 어떤 배포 환경에서도 활성화하지 않는다.

본 문서는 실제 사용자 서버 배포 전후를 구분하며 CI에서만 띄운 임시 Docker 컨테이너를 '실제 운영 서버'로 부르지 않는다.
