import {useEffect,useMemo,useState} from 'react';
import {api} from '../../api';
import type {CommunityScript,PineSource,PineVisualResponse,ScriptDetail} from '../../types';
import {PineChartControl} from '../../components/PineChartControl';
import {NativePineChartControl} from '../../components/NativePineChartControl';

function label(kind?:string){
  const x=(kind||'').toLowerCase();
  if(x.includes('strateg'))return '전략';
  if(x.includes('librar'))return '라이브러리';
  return '지표';
}

function intervalToHorizon(v?:string){
  const x=String(v||'').toUpperCase();
  if(x==='1D'||x==='D'||x==='1440')return '1d';
  if(x==='1W'||x==='W')return '1d';
  if(x==='1M'||x==='M')return '1d';
  const n=Number(x);
  if(!Number.isFinite(n))return '1h';
  if(n<=1)return '1m';
  if(n<=3)return '3m';
  if(n<=5)return '5m';
  if(n<=10)return '10m';
  if(n<=15)return '15m';
  if(n<=30)return '30m';
  if(n<=60)return '1h';
  if(n<=120)return '2h';
  if(n<=240)return '4h';
  if(n<=360)return '6h';
  if(n<=480)return '8h';
  if(n<=720)return '12h';
  return '1d';
}

const HORIZONS=['1m','3m','5m','10m','15m','30m','1h','2h','4h','6h','8h','12h','1d'];

export function ScriptDetailPage({id,go}:{id:string;go:(p:string)=>void}){
  const [detail,setDetail]=useState<ScriptDetail|null>(null);
  const [source,setSource]=useState<PineSource|null>(null);
  const [meta,setMeta]=useState<CommunityScript|null>(null);
  const [chart,setChart]=useState<PineVisualResponse|null>(null);
  const [symbol,setSymbol]=useState('BINANCE:BTCUSDT');
  const [horizon,setHorizon]=useState('1h');
  const [error,setError]=useState('');
  const [chartError,setChartError]=useState('');
  const [chartLoading,setChartLoading]=useState(false);
  const [copied,setCopied]=useState(false);
  const [nativeState,setNativeState]=useState<'loading'|'ready'|'error'>('loading');
  const [nativeMessage,setNativeMessage]=useState('');

  useEffect(()=>{
    let alive=true;
    setError('');
    Promise.all([api.scriptDetail(id),api.scriptSource(id),api.scriptMeta(id)])
      .then(([d,s,m])=>{
        if(!alive)return;
        setDetail(d);setSource(s);setMeta(m);
        const initialSymbol=m.symbol||'BINANCE:BTCUSDT';
        const initialHorizon=intervalToHorizon(m.interval);
        setSymbol(initialSymbol);
        setHorizon(initialHorizon);
        setChartLoading(true);
        api.scriptChart(id,initialSymbol,initialHorizon)
          .then(v=>{if(alive)setChart(v)})
          .catch(e=>{if(alive)setChartError(String(e))})
          .finally(()=>{if(alive)setChartLoading(false)});
      })
      .catch(e=>{if(alive)setError(String(e))});
    return()=>{alive=false};
  },[id]);

  const license=useMemo(()=>{
    const lines=(source?.source||'').split(/\r?\n/).slice(0,12).filter(x=>/license|licensed|copyright|©|mozilla|creative commons/i.test(x));
    return lines.join('\n');
  },[source]);

  const copy=async()=>{
    if(!source?.source)return;
    await navigator.clipboard.writeText(source.source);
    setCopied(true);setTimeout(()=>setCopied(false),1200);
  };

  const runChart=async()=>{
    setChartLoading(true);setChartError('');setNativeState('loading');setNativeMessage('');
    try{setChart(await api.scriptChart(id,symbol.trim(),horizon))}
    catch(e){setChartError(String(e))}
    finally{setChartLoading(false)}
  };

  if(error)return <main><button className="back" onClick={()=>go('/scripts')}>← 스크립트 목록</button><div className="empty-state">{error}</div></main>;
  if(!detail||!source||!meta)return <main><div className="loading">Pine Script 상세를 불러오는 중...</div></main>;

  return <main className="script-detail-page">
    <button className="back" onClick={()=>go('/scripts')}>← TradingView 스크립트 목록</button>

    <section className="panel script-detail-head">
      <div>
        <div className="script-badges">
          <span className={'type-badge '+label(source.kind)}>{label(source.kind)}</span>
          <span>Pine v{source.pine_version||'-'}</span>
          {source.version&&<span>Script {source.version}</span>}
          {meta.author&&<span>{meta.author}</span>}
        </div>
        <h1>{detail.title||source.script_name}</h1>
        <p>TradingView Pine 원문을 트레이딩부 OHLCV 데이터에 실행해서 같은 화면에서 결과를 확인합니다.</p>
      </div>
      {detail.source_url&&<a className="external-link" href={detail.source_url} target="_blank" rel="noreferrer">TradingView 원본 ↗</a>}
    </section>

    <section className="panel runtime-panel">
      <div className="runtime-head">
        <div>
          <b>Pine 실행 컨트롤</b>
          <span>트레이딩부 Market Data → Pine Runtime → Chart</span>
        </div>
        {chart?.market_data?.provider&&<div className="runtime-provider">
          <strong>{chart.market_data.provider}</strong>
          <span>{chart.market_data.provider_symbol} · {chart.market_data.effective_interval||chart.market_data.base_interval}</span>
        </div>}
      </div>

      <div className="runtime-controls">
        <label>종목
          <input value={symbol} onChange={e=>setSymbol(e.target.value)} placeholder="BINANCE:BTCUSDT"/>
        </label>
        <label>시간축
          <select value={horizon} onChange={e=>setHorizon(e.target.value)}>
            {HORIZONS.map(x=><option key={x} value={x}>{x}</option>)}
          </select>
        </label>
        <button onClick={runChart} disabled={chartLoading||!symbol.trim()}>{chartLoading?'계산 중...':'스크립트 실행'}</button>
      </div>

      {chartLoading&&!chart?<div className="loading runtime-loading">트레이딩부 데이터를 가져와 Pine 계산 중...</div>:null}
      {chartError?<div className="empty-state">{chartError}</div>:null}
      {chart?<>
        <div className="runtime-summary">
          <span>Engine <b>Native Pine v5/v6</b></span>
          <span>상태 <b>{nativeState==='ready'?'실행 성공':nativeState==='error'?'실행 오류':'실행 중'}</b></span>
          <span>Bars <b>{chart.market_data.count}</b></span>
          <span>Data <b>{chart.market_data.provider||'-'}</b></span>
          <span>Pine <b>{source.kind||'script'} v{source.pine_version||'-'}</b></span>
        </div>
        <NativePineChartControl
          data={chart}
          source={source.source||''}
          onRuntime={x=>{setNativeState(x.state);setNativeMessage(x.message||'')}}
        />
        {nativeState==='error'&&chart.visual.adapter!=='unsupported'&&<>
          <div className="runtime-fallback-head">
            <b>보조 렌더링</b>
            <span>Native Pine 실행이 실패한 경우에만 서버 계산 결과를 표시합니다.</span>
          </div>
          <PineChartControl data={chart}/>
        </>}
        {nativeState==='error'&&nativeMessage&&<div className="runtime-note">Pine 원문 실행 진단: {nativeMessage}</div>}
        {chart.market_data.fallback_used&&<div className="runtime-note">대체 데이터 사용: {chart.market_data.fallback_reason}</div>}
      </>:null}
    </section>

    {license&&<section className="panel license-panel"><b>라이선스 / 저작권 표기</b><pre>{license}</pre></section>}

    <section className="panel pine-panel">
      <div className="pine-head">
        <div><b>Pine Script Source</b><span>{source.source_hash?.slice(0,12)}</span></div>
        <button onClick={copy}>{copied?'복사됨':'코드 복사'}</button>
      </div>
      {source.source?<pre className="pine-code"><code>{source.source}</code></pre>:<div className="empty-state">{source.reason||'Pine 소스를 사용할 수 없습니다.'}</div>}
    </section>

    <section className="panel script-description">
      <h2>TradingView 설명</h2>
      <div>{detail.full_text}</div>
    </section>
  </main>
}
