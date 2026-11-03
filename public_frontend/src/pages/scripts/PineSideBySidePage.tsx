import {useEffect,useState} from 'react';
import {api,API} from '../../api';
import type {PineSource,PineVisualResponse} from '../../types';
import {PineChartControl} from '../../components/PineChartControl';

type TradingViewPublication={
  title:string;
  page_url:string;
  image_url:string;
  publication_id:string;
  pine_editor_source_id:string;
  published_chart_symbol:string;
  published_chart_timeframe:string;
  evidence:string;
  verified_on:string;
  source_byte_match_verified:boolean;
  strategy_report_parity_verified:boolean;
  published_snapshot_not_live_chart:boolean;
};

const clean=(v:string)=>String(v||'').trim().slice(0,160);
const horizons=['1m','3m','5m','10m','15m','30m','1h','2h','4h','6h','8h','12h','1d'];
function initialHorizon(interval:string|undefined){
 const value=String(interval||'').toUpperCase();
 if(value==='D'||value==='1D'||value==='1440')return '1d';
 const mins=Number(value);
 if(Number.isFinite(mins)&&mins>0){
  const available=[1,3,5,10,15,30,60,120,240,360,480,720];
  const nearest=available.find(x=>mins<=x)||1440;
  return nearest===1440?'1d':nearest<60?nearest+'m':nearest/60+'h';
 }
 return '1h';
}

export function PineSideBySidePage({id,go}:{id:string,go:(p:string)=>void}){
  const query=new URLSearchParams(location.search);
  const [symbol,setSymbol]=useState(clean(query.get('symbol')||'BINANCE:BTCUSDT'));
  const [horizon,setHorizon]=useState(clean(query.get('horizon')||'1h'));
  const expectedSha=clean(query.get('sha256')||'').toLowerCase();
  const pinnedVersion=clean(query.get('version')||'1.0');
  const exactMode=/^[0-9a-f]{64}$/.test(expectedSha);
  const [source,setSource]=useState<PineSource|null>(null);
  const [chart,setChart]=useState<PineVisualResponse|null>(null);
  const [error,setError]=useState('');
  const [fetching,setFetching]=useState(true);
  const [original,setOriginal]=useState<TradingViewPublication|null>(null);
  const [originalImage,setOriginalImage]=useState<'pending'|'loaded'|'error'>('pending');

  async function exactLoad(targetSymbol:string,targetHorizon:string){
    const params=new URLSearchParams({
       version:pinnedVersion,sha256:expectedSha,symbol:targetSymbol,horizon:targetHorizon});
    const response=await fetch(API+'/api/public/scripts/'+encodeURIComponent(id)+
      '/compare-exact?'+params.toString(),{headers:{Accept:'application/json'}});
    if(!response.ok)throw Error('현재 DB 원본 차트 연결 실패 '+response.status+' · '+(await response.text()).slice(0,350));
    const result=await response.json();
    if(result.mode!=='EXACT_PINNED_STUDIO_SOURCE'||
       result.source?.source_sha256!==expectedSha||
       result.chart?.source_hash!==expectedSha||
       result.chart?.script_id!==id)
      throw Error('서로 다른 버전의 전략 원본으로 차트를 만들 수 없습니다.');
    return result as {source:{source:string;source_sha256:string;
      tradingview_publication?:TradingViewPublication|null},chart:PineVisualResponse};
  }

  useEffect(()=>{
    let alive=true;
    setError('');setFetching(true);setSource(null);setChart(null);
    setOriginal(null);setOriginalImage('pending');
    if(exactMode){
      const actualSymbol=clean(query.get('symbol')||'NASDAQ:NVDA');
      const actualHorizon=clean(query.get('horizon')||'2h');
      setSymbol(actualSymbol);setHorizon(actualHorizon);
      exactLoad(actualSymbol,actualHorizon).then(result=>{
        if(!alive)return;
        const p=result.source.tradingview_publication||null;
        if(p&&(!/^https:\/\/www\.tradingview\.com\/script\/[A-Za-z0-9]{8}[-/]/.test(p.page_url)||
          !/^https:\/\/s3\.tradingview\.com\/[A-Za-z0-9]\/\w+_mid\.webp$/.test(p.image_url)||
          p.pine_editor_source_id!==id)){
          throw Error('TradingView 공개 게시물 신원 또는 이미지 호스트 검증 실패');
        }
        setOriginal(p);
        setSource({script_id_part:id,version:pinnedVersion,kind:'strategy',
                   source:result.source.source,source_hash:result.source.source_sha256});
        setChart(result.chart);
      }).catch(e=>{if(alive)setError(String(e))})
        .finally(()=>{if(alive)setFetching(false)});
    }else{
      Promise.all([api.scriptSource(id),api.scriptMeta(id)]).then(([s,m])=>{
        if(!alive)return;
        const currentSymbol=clean(query.get('symbol')||m.symbol||'BINANCE:BTCUSDT');
        const currentHorizon=clean(query.get('horizon')||initialHorizon(m.interval));
        setSymbol(currentSymbol);setHorizon(currentHorizon);
        if(!s.source)throw Error('기존 TradingView 데이터베이스에서 Pine 원본을 찾지 못했습니다.');
        setSource(s);
        return api.scriptChart(id,currentSymbol,currentHorizon).then(d=>{
          if(!alive)return;
          if(d.script_id!==id||!d.bars?.length)throw Error('원본 ID 또는 실제 OHLCV가 일치하지 않습니다.');
          if(d.source_hash&&s.source_hash&&d.source_hash!==s.source_hash)
            throw Error('계산에 사용된 Pine 원본 해시가 일치하지 않습니다.');
          setChart(d);
        });
      }).catch(e=>{if(alive)setError(String(e))})
        .finally(()=>{if(alive)setFetching(false)});
    }
    return()=>{alive=false};
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[id,expectedSha,pinnedVersion]);
 
  async function rerun(){
    if(!source?.source||!symbol.trim()||!horizons.includes(horizon))return;
    setError('');setFetching(true);setChart(null);
    try{
      const d=exactMode?(await exactLoad(symbol.trim(),horizon)).chart:
          await api.scriptChart(id,symbol.trim(),horizon);
      if(d.script_id!==id||!d.bars?.length)throw Error('실제 동일 전략·가격 데이터가 반환되지 않았습니다.');
      if(d.source_hash&&source.source_hash&&d.source_hash!==source.source_hash)
        throw Error('서로 다른 Pine 버전을 비교할 수 없습니다.');
      setChart(d);
    }catch(e){setError(String(e))}
    finally{setFetching(false)}
  }

  const supported=Boolean(chart?.visual&&chart.visual.adapter!=='unsupported'&&!chart.visual.error);
  const previewReady=original!==null&&originalImage==='loaded'&&supported;  return <main className="pine-compare-page">
    <button className="back" onClick={()=>go('/scripts/'+encodeURIComponent(id))}>← 기존 전략 상세</button>
    <section className="panel">
      <h1>TradingView 원본 게시 차트 ↔ Python 전략 차트</h1>
      <p>왼쪽은 <b>TradingView 원본 사이트에 작성자가 게시한 전략 적용 차트 이미지</b>입니다. Vela/PineTS나 자체 제작 차트가 아닙니다. 오른쪽은 고정한 Pine 버전으로 Python Quant가 계산한 결과입니다. 게시 당시 TradingView 데이터와 현재 Python OHLCV 구간은 같다고 가정하지 않습니다.</p>
      <div><b>선택 전략 ID</b> <code>{id}</code>　<b>원본 SHA-256</b> <code>{source?.source_hash||'확인 중'}</code></div>
      <div className="runtime-controls" style={{marginTop:14}}>
        <label>종목 <input value={symbol} onChange={e=>setSymbol(e.target.value)} /></label>
        <label>시간봉 <select value={horizon} onChange={e=>setHorizon(e.target.value)}>{horizons.map(x=><option value={x} key={x}>{x}</option>)}</select></label>
        <button disabled={fetching||!source?.source} onClick={rerun}>{fetching?'실제 데이터 조회 중':'오른쪽 Python 차트 다시 계산'}</button>
      </div>
      {expectedSha&&<p><b>DB 고정 원본 SHA 검증:</b> {source?'일치 — 변경된 소스는 차단':'검증 중'}</p>}
      {error&&<div className="empty-state">{error}</div>}
      {chart&&<div className="runtime-summary">
        <span>시장 데이터 <b>{chart.market_data?.provider}</b></span>
        <span>가격 캔들 <b>{chart.market_data?.count}</b></span>
        <span>시간봉 <b>{chart.market_data?.effective_interval||chart.horizon}</b></span>
        <span>Python 데이터셋 <b>실제 OHLCV · 게시 차트 구간 동일성 미검증</b></span>
      </div>}
      {chart?.market_data?.fallback_used&&<div className="runtime-note">원래 요청 데이터 대신 제공된 데이터: {chart.market_data.fallback_reason||'세부 사항 미확인'}</div>}
    </section>
    <div className="pine-compare-grid">
      <section className="panel">
        <h2>왼쪽 · TradingView 공식 원본 게시 차트</h2>
        {original?<>
          <p><b>{original.title}</b> · TradingView 공개 전략 게시물</p>
          <a href={original.page_url} target="_blank" rel="noopener noreferrer" className="external-link">TradingView 원본 전략 페이지 및 Strategy Report 직접 보기</a>
          <a href={original.page_url} target="_blank" rel="noopener noreferrer" title="TradingView에서 공개한 실제 전략 차트 열기">
            <img data-testid="tradingview-original-chart" className="tv-original-publication-image"
              src={original.image_url} alt={'TradingView가 공개한 '+original.title+' 전략 적용 차트 이미지'}
              onLoad={()=>setOriginalImage('loaded')} onError={()=>setOriginalImage('error')}/>
          </a>
          <p>{originalImage==='loaded'?'TradingView 게시 차트 이미지 로드 완료':
             originalImage==='error'?'원본 TradingView 이미지 로드 실패 — 위 원본 페이지 링크에서 확인':
             'TradingView 원본 게시 차트 이미지 로드 중'}</p>
          <p>게시 차트: {original.published_chart_symbol} · {original.published_chart_timeframe} · 게시 당시 고정 화면</p>
          <p>TradingView Pine Editor 스크립트 ID와 저장 전략 ID 일치 확인. <b>게시 버전의 전체 소스 바이트 일치·정식 수치 동등성은 미검증</b>입니다.</p>
        </>:<div className="empty-state">해당 저장 Pine 버전에 연결된 TradingView 원본 게시물과 차트 이미지가 확인되지 않았습니다. 임의의 차트나 PineTS로 대신 표시하지 않습니다.</div>}
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
      <p>{previewReady?
        'TradingView 원본 게시 차트 이미지와 Python 계산 차트가 모두 실제로 표시되었습니다. 서로 다른 데이터 구간·설정일 수 있으므로 수치 동등성은 검증되지 않았습니다.':
        !original?'원본 TradingView 게시 차트가 아직 연결되지 않았습니다.':
        originalImage==='error'?'TradingView 공식 이미지 로드 실패. 원본 페이지를 직접 열어 확인하세요.':
        !chart?'Python 원본 데이터 또는 계산 결과가 없어 비교할 수 없습니다.':
        '원본 게시 이미지 또는 Python 차트를 로드 중이거나 실행 지원이 제한됩니다.'}</p>
      <p>원본 게시 스냅샷은 TradingView 사이트의 게시물 그대로이며 현재 시장에 같은 Pine을 다시 적용한 실시간 차트가 아닙니다. TradingView CSV·플롯·전략 입력값과 Python 결과의 정확성 판정은 별도입니다.</p>
    </section>
  </main>;
}
