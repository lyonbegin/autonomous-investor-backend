# 확인된 한계와 외부 차단

1. 운영 Railway/n8n: 사용 가능한 Railway 도구·CLI·RAILWAY_TOKEN·RAILWAY_API_TOKEN·N8N_API_KEY 바인딩이 없었다. 이는 Git 인증 부재와 다르다. Git origin read/fetch는 성공했다. 운영 서비스 수·DB 워크플로·owner 설정·자격증명 회전은 미검증이다.
2. 운영 화면·게이트웨이 HTTPS와 GitHub Actions API는 프록시 `403 Domain forbidden` / `Tunnel connection failed: 403 Forbidden`으로 차단됐다. api.github.com 및 문서에 명시된 운영 화면·게이트웨이 두 hostname을 환경 초안에 추가했다. 저장은 현재 런타임 반영·게시를 뜻하지 않는다.
3. Horizon 오류, 회사채 SQLite lock/timeout, macro 성공 이력은 첨부 문서의 과거 기록이다. 최근 성공·실패 시각/레코드는 현재 조회하지 못했으므로 현재 장애나 해결로 단정하지 않는다.
4. 복원한 서비스 entrypoint의 관리·수집 API에 인증을 추가했다. 기존 내부 호출 주체는 대응 서버 토큰을 설정해야 한다. 운영 연결 변경 전 서비스별 검증·롤백이 필요하다. 공개 프론트에 토큰을 넣지 않는다.
5. 기존 frontend는 운영 URL과 일부 데모 데이터를 포함한다. public-frontend는 이전 UI이고 public_frontend가 최신 공개 화면이다. 둘의 보존은 모든 화면의 실데이터 통합 완료를 뜻하지 않는다.
6. 기존 AlphaForgeStudio/InvestmentStudio는 별도 연구·데모 화면으로 보존한다. 신규 n8n 복제 UI로 확장하거나 원본 실행 증거로 보고하지 않는다.
7. 프로세스 메모리 기반 DAG handle/job 상태, 엔진별 프로세스 격리·기동/정지·자원 제한은 통합 완료 조건 중 미완료다.
8. 엔진 설치의 의존성 오버레이(RD-Agent/Finnhub)는 기존 installer 동작이며 원본 프로젝트 코드는 별도 upstream 소스 디렉터리에 있다. 버전/실행 검증 결과는 ENGINE_12_INVENTORY를 참조한다.
9. 로컬 검증에서 최초 n8n worker callback은 프록시 403, 다음 시도는 엔진 설치 중 일시적 디스크 부족으로 실패했다. 내부 NO_PROXY 설정과 설치 종료 후 재검증 결과는 TEST_AND_DEPLOYMENT_PLAN에 별도로 기록한다.
10. Docker 최초 빌드는 read-only buildx cache, 이후 프록시 CA 미설정으로 실패했다. BUILDX_CONFIG를 workspace에 두고 선택적 BuildKit cloud_ca secret으로 TLS 검증을 유지하여 TradingView 이미지를 빌드했다. CA나 토큰을 이미지/저장소에 저장하지 않는다.
