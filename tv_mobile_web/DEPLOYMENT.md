# 독립 모바일 웹 미리보기 배포

이 서비스만 Railway root directory `/tv_mobile_web` 및 전용 `Dockerfile`을 사용합니다. 저장소 루트의 기존 `railway.toml`을 읽지 않습니다.

서비스명: `tradingview-full-mobile-web-lab`

화면 URL은 Railway의 서비스 공개 도메인에서 확인합니다. 빌드 성공과 원본 Android 기능 동등성 검증은 별개입니다. 기존 n8n 및 시장 수집 서비스는 변경하지 않습니다.

자동 수집 Cron 없음. 원본 APK 자료나 로그인 쿠키 없이 실데이터 조회 API를 연결합니다. 기초 브라우저 테스트의 가격은 명시적 fixture입니다.
