# WF-04 실 SCAMP / 독립 10년 일봉 풀 운영 기준

## 현재 확인된 범위 (2026-11-05)
- 데이터 구축: \`global-daily-10yr-collector\` (Railway /data 4GB 기존 볼륨, 08:00 UTC 일일 Cron). 미국+홍콩 공식 목록의 15,943개 후보는 **목록**이지 적재 완료가 아님.
- 단일/배치 유사도: \`wf04_scamp.py\` / \`wf04_scamp_scan.py\`는 실제 \`pyscamp.abjoin\`(CPU, Pearson)으로 10년 1D 공통 거래일의 종가 로그수익률을 비교. 테스트 증거:
  - 실제 AAPL ↔ USDJPY 2,349개 공통 거래일, 상위 Pearson 약 0.714: Actions #41916223278
  - AAPL ↔ USDJPY/BTCUSD 2후보 실제 배치, 7개 테스트: Actions #41916793685
- **주의:** 이는 과거 형태 유사도이지 전략 성과/TradingView 결과/예측 정확도/PAPER 체결 검증이 아니다. 신호·타임프레임·체결 검증과 혼동 금지.
- 버전/출처: 각 소스 Parquet SHA256, 10년 시작/끝, 실제 공통 거래일, SCAMP 엔진 버전과 각 매칭 구간을 함께 기록한다.

## 역할 / 연결

\`\`\`
Yahoo(연구용) -> 공식 티커 목록 -> global-daily-10yr-collector
    -> /data/market_daily_10y/{catalog.sqlite3, daily/*.parquet}
    -> (선택: --mirror-s3) PRIVATE Railway bucket marketpool10y
       ├─ daily/v1/{file-id}/{sha256}.parquet [내용 주소 지정/불변]
       └─ manifests/v1/{asof}/latest.json + {manifest-sha256}.json
    -> 별도 WF-04 실행기: s3_bridge --hydrate (비공개 인증)
       -> 임시 Store와 SHA 재확인/10년 품질 검사
       -> wf04_scamp / wf04_scamp_scan -> JSON 결과
       -> 이후 n8n 실행 워커/API/관제센터로 연계 [아직 미구현]
\`\`\`

영구 볼륨 하나를 서로 다른 Railway 서비스에 억지로 동시에 연결하지 않는다. 버킷은 **비공개**이며 공개 URL, 무인증 HTTP OHLC 노출, 프런트엔드에 키 제공을 금지한다. 인증값은 Railway 서비스의 변수 참조로만 전달한다. 버킷 생성은 자동으로 기존 Parquet를 업로드하지 않는다.

## 수집기 업로드 활성화 (선택)
기존 정기 서비스 시작 명령:
\`\`\`bash
python -m market_daily_10y.collector --refresh-global-universe --queue --limit 100 --pause 1
\`\`\`
원격 적재 승인/권한 검토 후에만:
\`\`\`bash
python -m market_daily_10y.collector --refresh-global-universe --queue --limit 100 --pause 1 --mirror-s3
\`\`\`
환경변수: \`MARKET_POOL_S3_ENDPOINT\`, \`MARKET_POOL_S3_BUCKET\`, \`MARKET_POOL_S3_REGION\`, \`MARKET_POOL_S3_ACCESS_KEY_ID\`, \`MARKET_POOL_S3_SECRET_ACCESS_KEY\`, \`MARKET_POOL_S3_ADDRESSING_STYLE\`. Railway에는 bucket reference를 사용하고 로그에 키를 남기지 않는다.

원격 업로드 실패는 \`s3_mirror_failed\`, \`s3_mirror_status\`, \`s3_error\`로 분리해 기록. 로컬 수집 성공을 지우지 않으며, SQLite 큐는 1일 후 미러 재시도를 예약한다. 마지막 매니페스트 게시가 실패해도 이전 정상 snapshot의 파일은 삭제하지 않는다. 새로 수집되지 않은 종목은 매니페스트에 섞지 않는다.

수집기 CLI는 \`--status\`와 \`--progress\`로 실제 로컬 적재/품질을 조회 가능하며, 최초 100/일은 전체 15,943 후보의 7일 신선도 충족과 무관하므로 대량 완료로 보고하지 않는다.

## WF-04 별도 CPU 실행기 예
같은 비공개 버킷에 접근할 수 있는 **비공개 워커**에서만:
\`\`\`bash
python -m market_daily_10y.s3_bridge \
  --root /tmp/incoming-pool --hydrate --asof 2026-11-04 \
  --key equity:NASDAQ:AAPL:spot \
  --key fx:FX:USDJPY:spot --destination /tmp/wf04-pool

python -m market_daily_10y.wf04_scamp \
  --root /tmp/wf04-pool --asof 2026-11-04 \
  --left equity:NASDAQ:AAPL:spot --right fx:FX:USDJPY:spot \
  --window 60 --feature log_returns --threshold 0 --top 5 --threads 2 \
  --output /tmp/wf04-match.json
\`\`\`

설치 분리: 수집기 \`requirements.txt\`는 boto3를 제공하지만 SCAMP를 빌드하지 않는다. WF-04는 \`wf04-environment.yml\`로 별도 CPU pyscamp 환경을 구성한다. 프로젝트의 기존 12엔진 소스/관제센터/n8n/PG/SQLite를 덮어쓰지 않는다. LIVE 주문은 계속 금지한다.

## 검수 수준 (혼동 금지)
- GitHub 소스 작성 / 오프라인 단위 테스트 / GitHub Actions 실제 외부 데이터+SCAMP 검증 / Railway 빌드 성공 / Railway 실제 Cron 실행+볼륨 적재 / 버킷 업로드 / WF-04 운영 워커 / n8n 노드 실행 / 전략 승인 / PAPER 실행은 모두 별개.
- 금일 GitHub Actions의 Yahoo 적재는 CI 임시 볼륨이다. 운영 Railway \`catalog.sqlite3\`의 누적 적격 종목 수를 직접 확인하기 전에는 '전 세계 데이터 완료' 표시 금지.
- Yahoo Finance 원천 가격의 상업적 장기 저장·제3자 제공은 별도 권리/라이선스를 확보해야 한다. 본 구현은 비공개 연구용 실험이고 이 제약을 자동으로 해결하지 않는다.

## 다음 우선 작업
1. 운영 S3 미러 실 업로드/재수화 해시 동일성 확인 (버킷은 비공개).
2. 분리된 WF-04 워커가 비공개 버킷에서 가져와 실제 SCAMP를 실행한 결과를 DB에 저장.
3. 기존 n8n 편집기 WF-04 노드/API에서 승인된 run_id와 결과를 표시하고, 사용자가 직접 클릭→실행→결과 조회 E2E 검증.
4. JPX/KRX 공식 종목명부 확보, 유럽/인도/호주 등 확장, 배치 수집 속도/공급원 정책/저장 비용 검증.
