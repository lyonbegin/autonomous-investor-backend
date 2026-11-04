# 거래소 종목 목록 확장 — 미국 1단계

`universe_discovery.py`는 기존 28개 종목을 보존하고 Nasdaq Trader가 공표하는 `nasdaqlisted.txt`, `otherlisted.txt`를 결합한다. 미국 상장 목록을 대상으로 하며 **전 세계 거래소 완성이라고 주장하지 않는다.**

```bash
python -m market_daily_10y.universe_discovery \
  --allow-network \
  --output /data/market_daily_10y/universe-expanded.csv \
  --metadata /data/market_daily_10y/universe-report.json

python -m market_daily_10y.collector \
  --universe /data/market_daily_10y/universe-expanded.csv --limit 20
```

별도 네트워크 허가 없이 검증하려면 `--nasdaq-file`과 `--other-file`로 양쪽 파일 스냅샷을 명시한다. 목록 획득 실패 시 기존 CSV는 유지되며, 보고서는 목록 해시와 시각·미해결 매핑 건수를 남긴다. 우선 자동 매핑이 단순한 티커만 포함한다. 점·하이픈/복잡한 종목은 격리하며 Yahoo 가격 확인과 라이선스 적격성은 별개의 게이트다. 자동으로 WF-04 적격 심볼로 승격하지 않는다.

**주의:** 기본 20개/일 배치로는 수천 개의 종목을 신속히 채울 수 없다. 다운로드 처리량·약관·스토리지 여유·요청 제한을 측정하기 전에 전 종목 동시 수집을 켜지 않는다. Nasdaq 자료의 이용조건과 Yahoo 상업 사용 조건을 별도 검토한다.

다음 단계는 한국·일본·홍콩·유럽 등 거래소별 라이선스가 확인된 마스터 목록 공급자 어댑터 추가 및 전역 완료율 관측이다.
