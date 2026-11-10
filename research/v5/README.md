# 주식 자동화 / 자동연구개발 엔진 v5 — 실제 Pine 기반 수직 슬라이스

**이 문서는 구현·검증 범위만 표시합니다. 자동 AI 발굴 엔진 전체 완성이 아닙니다.**

## 실제 확인

- 원본 아카이브: `03_Strategy4428_통합3455_Pine원본_전수상태_20261109.zip` (3455 실제 Pine 파일)와 발견 목록 `TradingView_Recursive_33890_20261108.zip` (33890 메타데이터)의 역할을 구분합니다.
- 세 실제 ID: `0CVvd49h` (1158행), `02yfhjiz` (592행), `a5uitxrd` (166행). 아카이브 manifest SHA를 원본 바이트에 대조합니다.
- `source_evidence.py`: 주문·외부 시세·실적발표 함수 호출을 코드 줄 번호와 함께 추출합니다. **AST·컴파일·Pine↔Python 동등성은 미증명**입니다.
- `hypothesis_engine.py`: 소스에 근거한 **규칙 기반 연구 가설**과 반증 조건을 제시합니다. 외부 자산 두 레그가 원본에 구현돼 있다고 주장하지 않습니다.
- `taxonomy_87x12.csv`: 87개 정본 전부 확인, 가설 근거가 있는 행과 근거가 없는 행 구분. 추가 12개 원문 정본은 미확보이며 임의 행으로 채우지 않습니다.
- `evidence_gate.py`, `auto_discovery.py`: 외부 OpenAlex 메타데이터 → 허용된 HTTPS 원문 → AI 후보 → 실제 원문에서 정확한 인용문 확인 → 명세 검증 → 코드 생성. **API/키·네트워크가 없는 환경에서는 차단**합니다. 외부 API 자동 발굴을 이번 로컬 실행에서 통과했다고 주장하지 않습니다.
- 기존 CME·Chan 2건과 새 PEAD 연구 1건은 **수동 검증 자료를 바탕으로 범용 생성기에서 코드를 생성한 사례**입니다. CME 거래는 산술, Chan/PEAD는 합성 데이터 기능시험입니다.
- 다섯 기존 13번 외부 사례는 삭제·합치지 않으며 세 사례 미구현/미검증을 그대로 표시합니다.
- 01~20 보고서는 `results/<ID>/cases/<CASE_ID>/v3_20_sections.json|md`에 실제 필드·누락 사유를 저장합니다.

## 같은 엔진을 다른 ID로 실행

```bash
python src/research_v5.py \
  --discovery /path/to/TradingView_Recursive_33890_20261108.zip \
  --pine-archive /path/to/03_Strategy4428_통합3455_Pine원본_전수상태_20261109.zip \
  --source-id a5uitxrd \
  --synthetic-input examples/earnings_synthetic_fixture.json

PYTHONPATH=src python -m unittest discover -s tests -v
```

13번은 `--source-id 0CVvd49h --synthetic-input examples/seasonal_synthetic_bars.json`; 다른 ID는 `--source-id 02yfhjiz`로 바꿉니다. 설정과 코드 경로는 동일합니다.

외부 자동 연구 시도는 `--auto-search --allowed-host www.cmegroup.com --allowed-host epchan.blogspot.com` 등을 명시해야 하며, `RESEARCH_AI_ENDPOINT`, `RESEARCH_AI_MODEL`, `RESEARCH_AI_KEY` 없이는 모델 기반 규칙 추출이 수행되지 않습니다. 외부 원문 수집은 이용약관과 재사용 권한이 확인된 도메인만 허용합니다.

## 실제 원본 파일 및 데이터 권리

`original.pine`은 개인 연구용 결과 ZIP에만 포함합니다. 원본 TradingView Pine은 공개 GitHub에 재게시하지 않습니다. 이 저장소에서 GitHub로 올리는 것은 자체 작성한 어댑터·테스트·스키마와 수동 확인한 출처 메타데이터뿐입니다.

## 현재 불합격(차단) 항목

실제 AI 모델 호출, 실제 자동 외부 논문 검색·원문 추출 성공, 12개 정본 비교, 실제 시장 Bid/Ask 검증 백테스트, 부분체결·증거금, Nautilus PAPER, 원본 Pine과 생성 Python 동등성, Railway UI 조회. 영구 운영 DB·Actions CI·실행기록 연결은 별도 검증이 필요합니다.
