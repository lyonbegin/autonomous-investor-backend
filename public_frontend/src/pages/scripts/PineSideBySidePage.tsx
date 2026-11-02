import {useEffect,useState} from 'react';
import {api} from '../../api';
import type {PineSource,PineVisualResponse} from '../../types';
import {NativePineChartControl} from '../../components/NativePineChartControl';
import {PineChartControl} from '../../components/PineChartControl';

const clean=(v:string)=>String(v||'').trim().slice(0,160);
const horizons=['1m','3m','5m','10m','15m','30m','1h','2h','4h','6h','8h','12h','1d'];

export function PineSideBySidePage({id,go}:{id:string,go:(p:string)=>void}){
  const query=new URLSearchParams(location.search);
  const [symbol,setSymbol]=useState(clean(query.get('symbol')||'BINANCE:BTCUSDT'));
  const [horizon,setHorizon]=useState(clean(query.get('horizon')||'1h'));
  const expectedSha=clean(query.get('sha256')||'').toLowerCase();
  const [source,setSource]=useState<PineSource|null>(null);
  const [chart,setChart]=useState<PineVisualResponse|null>(null);
  const [error,setError]=useState('');
  const [fetching,setFetching]=useState(true);
  const [pine,setPine]=useState<{state:string,message?:string}>({state:'loading'});

  useEffect(()=>{
    let alive=true;
    setError('');setFetching(true);setSource(null);setChart(null);setPine({state:'loading'});
    api.scriptSource(id).then(s=>{
      if(!alive)return;
      if(!s.source)throw Error('기존 TradingView 데이터베이스에서 해당 Pine 원본을 찾지 못했습니다.');
      if(expectedSha&&s.source_hash?.toLowerCase()!==expectedSha)
        throw Error('선택한 PostgreSQL 원본 SHA-256과 TradingView 저장소의 원본 SHA-256이 다릅니다. 다른 버전의 차트는 실행하지 않습니다.');
      setSource(s);
      return api.scriptChart(id,symbol,horizon).then(d=>{
        if(!alive)return;
        if(d.script_id!==id)throw Error('전략 ID가 일치하지 않습니다.');
        if(d.source_hash&&s.source_hash&&d.source_hash!==s.source_hash)
          throw Error('계산에 사용된 전략 소스 해시가 일치하지 않습니다.');
        if(!d.bars?.length)throw Error('실제 OHLCV가 제공되지 않았습니다.');
        setChart(d);
      });
    }).catch(e=>{if(alive)setError(String(e))})
      .finally(()=>{if(alive)setFetching(false)});
    return()=>{alive=false};
  // Initial load only. Additional market changes use the explicit run button.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[id,expectedSha]);

  async function rerun(){
    if(!source?.source||!symbol.trim()||!horizons.includes(horizon))return;
    setError('');setFetching(true);setChart(null);setPine({state:'loading'});
    try{
      const d=await api.scriptChart(id,symbol.trim(),horizon);
      if(d.script_id!==id||!d.bars?.length)throw Error('실제 동일 전략·가격 데이터가 반환되지 않았습니다.');
      if(d.source_hash&&source.source_hash&&d.source_hash!==source.source_hash)
        throw Error('서로 다른 Pine 버전을 비교할 수 없습니다.');
      setChart(d);
    }catch(e){setError(String(e))}
    finally{setFetching(false)}
  }

  const supported=Boolean(chart?.visual&&chart.visual.adapter!=='unsupported'&&!chart.visual.error);
  const nativeReady=pine.state==='ready';
  const identicalData=Boolean(chart?.bars?.length);
  return <main className="pine-compare-page">
    <button className="back" onClick={()=>go('/scripts/'+encodeURIComponent(id))}>← 기존 전략 상세</button>
    <section className="panel">
      <h1>동일 원본 Pine · Python 전략 차트 나란히 확인</h1>
      <p>좌측은 저장된 Pine 원문을 Vela/PineTS로 실행한 차트, 우측은 기존 Python Quant 계산 결과입니다. 두 화면은 <b>동일한 OHLCV 데이터</b>를 사용합니다. 이 화면은 TradingView 웹사이트의 실제 렌더링 캡처나 정식 동등성 판정이 아닙니다.</p>
      <div><b>선택 전략 ID</b> <code>{id}</code>　<b>원본 SHA-256</b> <code>{source?.source_hash||'확인 중'}</code></div>
      <div className="runtime-controls" style={{marginTop:14}}>
        <label>종목 <input value={symbol} onChange={e=>setSymbol(e.target.value)} /></label>
        <label>시간봉 <select value={horizon} onChange={e=>setHorizon(e.target.value)}>{horizons.map(x=><option value={x} key={x}>{x}</option>)}</select></label>
        <button disabled={fetching||!source?.source} onClick={rerun}>{fetching?'실제 데이터 조회 중':'동일 OHLCV로 차트 다시 계산'}</button>
      </div>
      {expectedSha&&<p><b>DB 고정 원본 SHA 검증:</b> {source?'일치 — 변경된 소스는 차단':'검증 중'}</p>}
      {error&&<div className="empty-state">{error}</div>}
      {chart&&<div className="runtime-summary">
        <span>시장 데이터 <b>{chart.market_data?.provider}</b></span>
        <span>가격 캔들 <b>{chart.market_data?.count}</b></span>
        <span>시간봉 <b>{chart.market_data?.effective_interval||chart.horizon}</b></span>
        <span>같은 OHLCV <b>{identicalData?'사용':'불가'}</b></span>
      </div>}
      {chart?.market_data?.fallback_used&&<div className="runtime-note">원래 요청 데이터 대신 제공된 데이터: {chart.market_data.fallback_reason||'세부 사항 미확인'}</div>}
    </section>
    <div className="pine-compare-grid">
      <section className="panel">
        <h2>왼쪽 · 저장된 원본 Pine 실행</h2>
        <p>기존 Vela + PineTS 런타임 · {pine.state==='ready'?'실행 성공':pine.state==='error'?'실행 오류':fetching?'데이터 조회 중':'Pine 실행 중'}</p>
        {chart&&source?.source?<NativePineChartControl data={chart} source={source.source} onRuntime={x=>setPine({state:x.state,message:x.message})}/>:<div className="empty-state">원본 소스와 OHLCV 대기</div>}
        {pine.message&&<div className="runtime-note">런타임 진단: {pine.message}</div>}
      </section>
      <section className="panel">
        <h2>오른쪽 · 기존 Python Quant 전략 계산</h2>
        <p>{supported?'StrategySpec/Python 매매 신호 및 시계열':'변환 지원 범위 확인 필요'}</p>
        {chart&&supported?<PineChartControl data={chart}/>:<div className="empty-state">
          {chart?.visual?.error|| (fetching?'같은 OHLCV로 Python 계산 중':'Python 전략 계산 결과가 없습니다. 지원하지 않는 Pine을 임의로 대체하지 않습니다.')}
        </div>}
        {chart&&supported&&<p>거래 수 {chart.visual.trades?.length||0} · 데이터 소스 {chart.market_data.provider}</p>}
      </section>
    </div>
    <section className="panel">
      <h3>검증 상태</h3>
      <p>{!chart?'실제 데이터 또는 소스 부족 — 비교 불가':
        nativeReady&&supported?'동일 데이터의 두 실행 화면 준비 완료. TradingView 실제 차트 캡처·CSV 수치 동등성은 별도 검증 필요':
        '일부 런타임 미지원 또는 로드 중 — 원본과 Python 동등성 미확인'}</p>
      <p>TradingView 원문 그대로의 차트 캡처/플롯 CSV가 없으면 연구용 비교만 가능합니다. 검증 없이 에이전트 승격 또는 실거래를 허용하지 않습니다.</p>
    </section>
  </main>;
}
