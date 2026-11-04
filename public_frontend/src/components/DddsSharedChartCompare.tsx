import {useEffect,useMemo,useRef,useState} from 'react';
import {ColorType,createChart,type UTCTimestamp,type IChartApi} from 'lightweight-charts';
import type {PineVisualResponse} from '../types';
import {NativePineChartControl} from './NativePineChartControl';
import type {NativePineCapture} from './nativePineCapture';

export const DDDS_ID='PUB;5442675d418140c58486eb4a7ae12768';
export const DDDS_SHA='5a245e99447f13012dd026528235fc2c299cad5cb7b228653c684886dcba6507';
const PY_SHA='ef27e69cbb71bc101431a2f9f71783c37f1f8094a7a77e080032ca3bbd7994a1';
const API='https://investment-n8n-native-editor-production.up.railway.app/api/investment/free-pyne/ddds/chart/compare-input';
const TV_URL='https://www.tradingview.com/script/LkgKT3TG-Displaced-Donchian-Decycler-Trend-Breakout-Strategy-with-MFI/';
type Result={status:string;source_id:string;pine_source_sha256:string;python_sha256:string;symbol:string;timeframe:string;bar_count:number;time_ms:number[];close:number[];plots:Record<string,(number|null)[]>;market_data_same_as_python_input:boolean;official_tradingview_publication_parity_verified:boolean;live_orders_enabled:boolean};
const PLOT_NAMES=['Decycler','Price anchor','Gradient','Lower band','Upper band','Stop','Target'];
type ChartWindow={from:number;to:number};
const HOUR_MS=60*60*1000;
const SHOW_BARS_DEFAULT=80;
const formatUtc=(ms:number)=>new Date(ms).toISOString().replace('T',' ').slice(0,16)+' UTC';
const windowOf=(bars:PineVisualResponse['bars'],count:number):ChartWindow|null=>
 bars.length>=2?{from:bars[Math.max(0,bars.length-count)].timestamp,
                 to:bars[bars.length-1].timestamp}:null;
const validWindow=(v:ChartWindow|null):v is ChartWindow=>
 !!v&&Number.isFinite(v.from)&&Number.isFinite(v.to)&&v.from<v.to&&
 v.from>946684800000&&v.to<4102444800000;


export function comparePlotValues(capture:NativePineCapture|null,result:Result|null,visibleWindow?:ChartWindow|null){
 let compared=0,matched=0,mismatched=0,maxDifference=0;
 if(!capture||!result)return {compared,matched,mismatched,maxDifference,status:'차트 지표 미수집'};
 if(capture.script_id!==DDDS_ID||capture.source_hash!==DDDS_SHA||capture.bars.length!==result.bar_count||!capture.complete||capture.forming)
   return {compared,matched,mismatched,maxDifference,status:'Pine 원본 또는 봉 수 불일치'};
 const names=PLOT_NAMES.filter(x=>capture.plot_names.includes(x));
 for(let i=0;i<capture.bars.length;i++){
   if(capture.bars[i].time_ms!==result.time_ms[i]||capture.bars[i].close!==result.close[i])
     return {compared,matched,mismatched,maxDifference,status:'시각·종가 불일치'};
   if(visibleWindow&&(capture.bars[i].time_ms<visibleWindow.from||capture.bars[i].time_ms>visibleWindow.to))continue;
   for(const name of names){
      const a=capture.bars[i].plots[name],b=result.plots[name]?.[i];
      if(typeof a!=='number'||typeof b!=='number'||!Number.isFinite(a)||!Number.isFinite(b))continue;
      const difference=Math.abs(a-b);
      const tolerance=Math.max(0.0001,Math.max(Math.abs(a),Math.abs(b))*0.00001);
      compared++;maxDifference=Math.max(maxDifference,difference);
      if(difference<=tolerance)matched++;else mismatched++;
   }
 }
 return {compared,matched,mismatched,maxDifference,
  status:compared===0?'공통 지표값 없음':mismatched===0?'공통 지표값 일치':'공통 지표값 불일치'};
}

function PythonPlot({data,result,visibleWindow,onApplied}:
 {data:PineVisualResponse;result:Result;visibleWindow:ChartWindow|null;
  onApplied:(range:ChartWindow|null)=>void}){
 const root=useRef<HTMLDivElement>(null);
 const instance=useRef<IChartApi|null>(null);
 const appliedRef=useRef(onApplied);
 const latestWindowRef=useRef(visibleWindow);
 latestWindowRef.current=visibleWindow;
 useEffect(()=>{appliedRef.current=onApplied},[onApplied]);
 function applyWindow(chart:IChartApi,el:HTMLDivElement,r:ChartWindow|null){
   if(!validWindow(r))return;
   // Vela is in epoch milliseconds; lightweight-charts takes UTC seconds.
   const from=Math.floor(r.from/1000) as UTCTimestamp;
   const to=Math.floor(r.to/1000) as UTCTimestamp;
   el.dataset.requestedFrom=String(r.from);
   el.dataset.requestedTo=String(r.to);
   chart.timeScale().setVisibleRange({from,to});
   const actual=chart.timeScale().getVisibleRange();
   if(actual && typeof actual.from==='number' && typeof actual.to==='number'){
     const checked={from:Number(actual.from)*1000,to:Number(actual.to)*1000};
     el.dataset.visibleFrom=String(checked.from);
     el.dataset.visibleTo=String(checked.to);
     appliedRef.current(checked);
   }else appliedRef.current(null);
 }
 useEffect(()=>{
  const el=root.current;if(!el)return;
  const chart=createChart(el,{width:el.clientWidth,height:620,
   layout:{background:{type:ColorType.Solid,color:'#ffffff'},textColor:'#475569'},
   timeScale:{timeVisible:true,secondsVisible:false},
   localization:{locale:'ko-KR'},
   handleScroll:false,handleScale:false});
  instance.current=chart;
  chart.addCandlestickSeries({upColor:'#16a34a',downColor:'#dc2626',borderUpColor:'#16a34a',borderDownColor:'#dc2626',wickUpColor:'#16a34a',wickDownColor:'#dc2626'})
   .setData(data.bars.map(b=>({time:Math.floor(b.timestamp/1000) as UTCTimestamp,open:b.open,high:b.high,low:b.low,close:b.close})));
  // These are original Python-computed plot points, not a substitute indicator.
  for(const [name,color] of [
    ['Decycler','#2563eb'],['Price anchor','#0f766e'],
    ['Lower band','#8b5cf6'],['Upper band','#c2410c'],
    ['Stop','#db2777'],['Target','#16a34a']
  ]){
   const values=result.plots[name];if(!Array.isArray(values)||values.length!==data.bars.length)continue;
   const pts=values.flatMap((v,i)=>typeof v==='number'&&Number.isFinite(v)?[{time:Math.floor(data.bars[i].timestamp/1000) as UTCTimestamp,value:v}]:[]);
   if(pts.length)chart.addLineSeries({color,lineWidth:2,title:name}).setData(pts);
  }
  // Deliberately NO fitContent(): that showed all 300 Python bars while
  // native Vela displayed just the latest ~80; the screenshot was misleading.
  applyWindow(chart,el,latestWindowRef.current);
  const ro=new ResizeObserver(()=>{
    chart.applyOptions({width:Math.max(100,el.clientWidth)});
    // Never restore the initial 80-bar window after a user changes it to 40.
    // The observer was created at mount; only the live ref is current.
    applyWindow(chart,el,latestWindowRef.current);
  });ro.observe(el);
  return()=>{ro.disconnect();instance.current=null;chart.remove()};
 },[data,result]);
 useEffect(()=>{
   if(instance.current&&root.current)applyWindow(instance.current,root.current,visibleWindow);
 },[visibleWindow?.from,visibleWindow?.to]);
 return <div data-testid="ddds-python-chart" ref={root}
   style={{width:'100%',height:620}}/>;
}

export function DddsSharedChartCompare({id,source,sourceSha,chart}:{id:string;source:string;sourceSha:string;chart:PineVisualResponse}){
 const [capture,setCapture]=useState<NativePineCapture|null>(null);
 const [runtime,setRuntime]=useState('Pine 실행 준비');
 const [retryCount,setRetryCount]=useState(0);
 const [running,setRunning]=useState(false);
 const [result,setResult]=useState<Result|null>(null);
 const [error,setError]=useState('');
 const [visibleBars,setVisibleBars]=useState(SHOW_BARS_DEFAULT);
 const [observedWindow,setObservedWindow]=useState<ChartWindow|null>(null);
 const [pythonWindow,setPythonWindow]=useState<ChartWindow|null>(null);
 const sameData=useMemo(()=>({...chart,bars:chart.bars.slice(-300),market_data:{...chart.market_data,count:Math.min(300,chart.bars.length)}}),[chart]);
 const bars=sameData.bars;
 const chosenWindow=useMemo(()=>windowOf(bars,visibleBars),[bars,visibleBars]);
 const viewport=observedWindow||chosenWindow;
 const windowBars=validWindow(viewport)?bars.filter(b=>b.timestamp>=viewport.from&&b.timestamp<=viewport.to).length:0;
 const rangeStatus=validWindow(viewport)&&validWindow(pythonWindow)&&
     Math.abs(viewport.from-pythonWindow.from)<=HOUR_MS*2&&
     Math.abs(viewport.to-pythonWindow.to)<=HOUR_MS*2;
 const formatWindow=validWindow(viewport)?formatUtc(viewport.from)+' ~ '+formatUtc(viewport.to):'구간 확인 전';
 const ready=id===DDDS_ID&&sourceSha===DDDS_SHA&&sameData.source_hash===DDDS_SHA&&sameData.symbol==='NASDAQ:AMZN'&&sameData.horizon==='2h'&&sameData.market_data.fallback_used!==true&&bars.length>=40&&bars.every(b=>[b.timestamp,b.open,b.high,b.low,b.close,b.volume].every(Number.isFinite));
 const aligned=result!==null&&result.status==='EXACT_SITE_CHART_INPUT_PYTHON_EXECUTED'&&result.source_id===DDDS_ID&&result.pine_source_sha256===DDDS_SHA&&result.python_sha256===PY_SHA&&result.symbol==='NASDAQ:AMZN'&&result.timeframe==='120'&&result.bar_count===bars.length&&result.market_data_same_as_python_input===true&&result.official_tradingview_publication_parity_verified===false&&result.live_orders_enabled===false&&result.time_ms.length===bars.length&&result.close.length===bars.length&&result.time_ms.every((v,i)=>v===bars[i].timestamp)&&result.close.every((v,i)=>v===bars[i].close);
 const nativeOhlcvMatches=!!capture&&capture.script_id===DDDS_ID&&
    capture.source_hash===DDDS_SHA&&capture.symbol==='NASDAQ:AMZN'&&
    capture.timeframe==='2h'&&capture.bars.length===bars.length&&
    capture.bars.every((item,i)=>{
      const price=bars[i];
      return item.time_ms===price.timestamp&&item.open===price.open&&
       item.high===price.high&&item.low===price.low&&
       item.close===price.close&&item.volume===price.volume;
    });
 const visualVerified=aligned&&nativeOhlcvMatches&&rangeStatus;
 const stats=comparePlotValues(capture,aligned?result:null);
 const visibleStats=comparePlotValues(capture,aligned?result:null,viewport);
 function handleNativeViewport(v:ChartWindow){
   if(!validWindow(v))return;
   setObservedWindow(old=>old&&Math.abs(old.from-v.from)<1000&&Math.abs(old.to-v.to)<1000?old:v);
 }
 function chooseWindow(n:number){
   setVisibleBars(n);
   setObservedWindow(windowOf(bars,n));
   setPythonWindow(null);
 }
 useEffect(()=>{
  if(!ready){setResult(null);setRunning(false);return;}
  let active=true;
  const controller=new AbortController();
  // Deferred start avoids duplicate requests during React StrictMode mount.
  const start=setTimeout(()=>{
    if(!active)return;
    setError('');setResult(null);setRunning(true);
    const limit=setTimeout(()=>controller.abort(),120000);
    void (async()=>{
      try{
        const response=await fetch(API,{method:'POST',headers:{'Content-Type':'application/json'},
          signal:controller.signal,
          body:JSON.stringify({source_id:DDDS_ID,pine_source_sha256:DDDS_SHA,
            symbol:'NASDAQ:AMZN',timeframe:'120',acknowledge_mpl:true,
            bars:bars.map(b=>({time_ms:b.timestamp,open:b.open,high:b.high,
              low:b.low,close:b.close,volume:b.volume}))})});
        const output=await response.json();
        if(!response.ok)throw Error(output.reason||output.status||('HTTP '+response.status));
        if(output.status!=='EXACT_SITE_CHART_INPUT_PYTHON_EXECUTED'||
            output.source_id!==DDDS_ID||output.pine_source_sha256!==DDDS_SHA||
            output.python_sha256!==PY_SHA||output.bar_count!==bars.length||
            !Array.isArray(output.time_ms)||!Array.isArray(output.close)||
            output.time_ms.length!==bars.length||output.close.length!==bars.length||
            !output.time_ms.every((v:number,i:number)=>v===bars[i].timestamp)||
            !output.close.every((v:number,i:number)=>v===bars[i].close))
          throw Error('DDDS_PYTHON_INPUT_DIFFERENT_FROM_REACT_CHART');
        if(active)setResult(output as Result);
      }catch(e){if(active)setError(e instanceof Error?e.message:String(e))}
      finally{clearTimeout(limit);if(active)setRunning(false)}
    })();
  },200);
  return()=>{active=false;clearTimeout(start);controller.abort()};
 },[ready,sameData,retryCount]);
 return <div className="pine-compare-page ddds-shared-compare" data-testid="ddds-shared-chart-comparison">
   <section className="panel">
     <h1>DDDS · 기존 우리 사이트 Pine 차트와 Python 차트</h1>
     <p>동일한 {bars.length}개 OHLCV 봉(종목·시간축·시각 포함)을 두 실행 엔진에 입력합니다. 왼쪽은 기존 Vela/PineWorkerEngine, 오른쪽은 DDDS 141줄을 변환한 Python입니다.</p>
     <p><a href={TV_URL} target="_blank" rel="noopener noreferrer">원본 TradingView 전략 실제 차트 열기</a> · 이 비교의 시세는 TradingView 원본 페이지에서 추출한 값이 아닌 <b>우리 사이트 기존 차트 API의 값</b>입니다.</p>
     <p>데이터 제공자: {sameData.market_data.provider||'알 수 없음'} · {sameData.symbol} · {sameData.horizon}</p>
     <div className="ddds-viewport-controls">
       <label htmlFor="ddds-visible-bars">양쪽 차트에 표시할 구간</label>
       <select id="ddds-visible-bars" data-testid="ddds-visible-bars-select"
         value={visibleBars} onChange={e=>chooseWindow(Number(e.target.value))}>
         {[40,80,120,200,300].map(n=><option key={n} value={n}>최근 {n}봉</option>)}
       </select>
       <span data-testid="ddds-shared-symbol-timeframe"><b>왼쪽 = 오른쪽: NASDAQ:AMZN · 2시간봉</b></span>
     </div>
     <p data-testid="ddds-visible-interval" className="runtime-note">
       <b>실제 표시 날짜(양쪽 동일): {formatWindow}</b> · 현재 보이는 OHLCV {windowBars}봉 / 계산 입력 총 {bars.length}봉
     </p>
     <p data-testid="ddds-viewport-sync" className="runtime-note">
       화면 구간: {rangeStatus?'양쪽 차트 날짜 동기화 확인':'날짜 범위 동기화 중 또는 불일치'}
       {' '}· 왼쪽 차트를 확대/이동하면 오른쪽 표시 날짜를 따라갑니다.
     </p>
     {!ready&&<div className="empty-state">정확한 DDDS Pine SHA, NASDAQ:AMZN 2h, 대체 시세 없는 40~300봉을 확보하지 못해 실행을 차단했습니다.</div>}
     <p className="ddds-license-note">원본 DDDS Pine: MPL-2.0 · 원작자 출처는 위 TradingView 링크에서 확인할 수 있습니다. Python 계산은 차트 준비 시 자동으로 실행됩니다.</p>
     <div className="runtime-controls ddds-auto-controls"><span data-testid="ddds-python-auto-status">{running?'Python에서 동일 봉 자동 계산 중…':aligned?'Python 계산 완료 · 실제 차트 표시':'Python 자동 계산 준비'}</span>
       <button type="button" disabled={!ready||running} onClick={()=>setRetryCount(v=>v+1)}>↻ 다시 계산</button>
     </div>
     {error&&<div className="empty-state" role="alert">DDDS Python 자동 실행 실패: {error} · 다시 계산 버튼으로 재실행할 수 있습니다.</div>}
     <div className="runtime-note" data-testid="ddds-same-bar-status">{aligned&&nativeOhlcvMatches?
       'Pine·Python 종목/시간봉/시각/OHLCV '+bars.length+'/'+bars.length+'봉 동일 확인':
       '두 엔진 실제 OHLCV 전체 일치 검증 대기 또는 실패'}</div>
   </section>
   <div className="pine-compare-grid">
    <section className="panel"><h2>왼쪽 · 기존 NativePineChartControl</h2>
     <p>DDDS Pine 원본 실행 · <b>NASDAQ:AMZN · 120분 · {formatWindow}</b></p>
     {ready&&<NativePineChartControl key={sameData.symbol+sameData.horizon+bars[0]?.timestamp}
       data={sameData} source={source} visibleRange={viewport||undefined}
       onViewport={handleNativeViewport} onCapture={setCapture}
       onRuntime={x=>setRuntime(x.state+(x.message?' · '+x.message:''))}/>}
     <p data-testid="ddds-vela-status">{runtime} · {capture?'지표 '+capture.plot_names.length+'개 추출':'지표 출력 확인 전'}</p>
    </section>
    <section className="panel"><h2>오른쪽 · 동일 봉의 DDDS 생성 Python</h2>
     <p>Python 변환 실행 · <b>NASDAQ:AMZN · 120분 · {formatWindow}</b></p>
     {aligned&&result?<PythonPlot key={'python-window-'+visibleBars} data={sameData} result={result}
          visibleWindow={viewport} onApplied={setPythonWindow}/>:<div className="empty-state" data-testid="ddds-python-loading">{error?'Python 실행 오류: '+error:running?'동일한 '+bars.length+'개 봉으로 실제 DDDS Python 계산 중…':'동일 시장 데이터 확인 및 Python 자동 계산 준비 중…'}</div>}
    </section>
   </div>
   <section className="panel" data-testid="ddds-plot-comparison">
    <h3>시각별 DDDS 지표값 간단 비교</h3>
    <p data-testid="ddds-visible-plot-stats">
     {visualVerified?<><b>현재 표시 구간 {windowBars}봉:</b> {visibleStats.status}
       · 공통 수치 {visibleStats.compared}개 · 일치 {visibleStats.matched}개
       · 불일치 {visibleStats.mismatched}개
       · 최대 차이 {visibleStats.maxDifference.toExponential(3)}</>:
       <b>표시 날짜·종목·시간봉·OHLCV 전체 검증 전이므로 시각적 일치 판정 보류</b>}
    </p>
    <p data-testid="ddds-total-plot-stats"><b>전체 입력 {bars.length}봉:</b> {stats.status}
       · 공통 수치 {stats.compared}개 · 일치 {stats.matched}개
       · 불일치 {stats.mismatched}개 (NULL 위치는 일치 계산에서 제외)</p>
    <p>Vela가 DDDS 전체 문법을 실행하지 못하면 오류를 표시하고 지표 일치를 주장하지 않습니다. TradingView 원본 사이트 지표 및 과거 거래 299건 비교와는 별개입니다.</p>
   </section>
 </div>;
}
