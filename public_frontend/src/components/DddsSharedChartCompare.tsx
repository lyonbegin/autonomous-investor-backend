import {useEffect,useMemo,useRef,useState} from 'react';
import {ColorType,createChart,type UTCTimestamp} from 'lightweight-charts';
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

export function comparePlotValues(capture:NativePineCapture|null,result:Result|null){
 let compared=0,matched=0,mismatched=0,maxDifference=0;
 if(!capture||!result)return {compared,matched,mismatched,maxDifference,status:'차트 지표 미수집'};
 if(capture.script_id!==DDDS_ID||capture.source_hash!==DDDS_SHA||capture.bars.length!==result.bar_count||!capture.complete||capture.forming)
   return {compared,matched,mismatched,maxDifference,status:'Pine 원본 또는 봉 수 불일치'};
 const names=PLOT_NAMES.filter(x=>capture.plot_names.includes(x));
 for(let i=0;i<capture.bars.length;i++){
   if(capture.bars[i].time_ms!==result.time_ms[i]||capture.bars[i].close!==result.close[i])
     return {compared,matched,mismatched,maxDifference,status:'시각·종가 불일치'};
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

function PythonPlot({data,result}:{data:PineVisualResponse;result:Result}){
 const root=useRef<HTMLDivElement>(null);
 useEffect(()=>{
  const el=root.current;if(!el)return;
  const chart=createChart(el,{width:el.clientWidth,height:520,
   layout:{background:{type:ColorType.Solid,color:'#ffffff'},textColor:'#475569'},
   timeScale:{timeVisible:true,secondsVisible:false}});
  chart.addCandlestickSeries({upColor:'#16a34a',downColor:'#dc2626',borderUpColor:'#16a34a',borderDownColor:'#dc2626',wickUpColor:'#16a34a',wickDownColor:'#dc2626'})
   .setData(data.bars.map(b=>({time:Math.floor(b.timestamp/1000) as UTCTimestamp,open:b.open,high:b.high,low:b.low,close:b.close})));
  for(const [name,color] of [['Decycler','#2563eb'],['Lower band','#8b5cf6'],['Upper band','#c2410c']]){
   const values=result.plots[name];if(!Array.isArray(values)||values.length!==data.bars.length)continue;
   const pts=values.flatMap((v,i)=>typeof v==='number'&&Number.isFinite(v)?[{time:Math.floor(data.bars[i].timestamp/1000) as UTCTimestamp,value:v}]:[]);
   if(pts.length)chart.addLineSeries({color,lineWidth:2,title:name}).setData(pts);
  }
  chart.timeScale().fitContent();
  const ro=new ResizeObserver(()=>chart.applyOptions({width:Math.max(100,el.clientWidth)}));ro.observe(el);
  return()=>{ro.disconnect();chart.remove()};
 },[data,result]);
 return <div data-testid="ddds-python-chart" ref={root} style={{width:'100%',height:520}}/>;
}

export function DddsSharedChartCompare({id,source,sourceSha,chart}:{id:string;source:string;sourceSha:string;chart:PineVisualResponse}){
 const [capture,setCapture]=useState<NativePineCapture|null>(null);
 const [runtime,setRuntime]=useState('Pine 실행 준비');
 const [mpl,setMpl]=useState(false);
 const [running,setRunning]=useState(false);
 const [result,setResult]=useState<Result|null>(null);
 const [error,setError]=useState('');
 const sameData=useMemo(()=>({...chart,bars:chart.bars.slice(-300),market_data:{...chart.market_data,count:Math.min(300,chart.bars.length)}}),[chart]);
 const bars=sameData.bars;
 const ready=id===DDDS_ID&&sourceSha===DDDS_SHA&&sameData.source_hash===DDDS_SHA&&sameData.symbol==='NASDAQ:AMZN'&&sameData.horizon==='2h'&&sameData.market_data.fallback_used!==true&&bars.length>=40&&bars.every(b=>[b.timestamp,b.open,b.high,b.low,b.close,b.volume].every(Number.isFinite));
 const aligned=result!==null&&result.status==='EXACT_SITE_CHART_INPUT_PYTHON_EXECUTED'&&result.source_id===DDDS_ID&&result.pine_source_sha256===DDDS_SHA&&result.python_sha256===PY_SHA&&result.symbol==='NASDAQ:AMZN'&&result.timeframe==='120'&&result.bar_count===bars.length&&result.market_data_same_as_python_input===true&&result.official_tradingview_publication_parity_verified===false&&result.live_orders_enabled===false&&result.time_ms.length===bars.length&&result.close.length===bars.length&&result.time_ms.every((v,i)=>v===bars[i].timestamp)&&result.close.every((v,i)=>v===bars[i].close);
 const stats=comparePlotValues(capture,aligned?result:null);
 async function execute(){
  if(!ready||!mpl||running)return;
  setError('');setResult(null);setRunning(true);
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),130000);
  try{
   const response=await fetch(API,{method:'POST',headers:{'Content-Type':'application/json'},signal:controller.signal,
    body:JSON.stringify({source_id:DDDS_ID,pine_source_sha256:DDDS_SHA,symbol:'NASDAQ:AMZN',timeframe:'120',acknowledge_mpl:true,
      bars:bars.map(b=>({time_ms:b.timestamp,open:b.open,high:b.high,low:b.low,close:b.close,volume:b.volume}))})});
   const body=await response.json();
   if(!response.ok)throw Error(body.reason||body.status||('HTTP '+response.status));
   if(body.status!=='EXACT_SITE_CHART_INPUT_PYTHON_EXECUTED'||body.python_sha256!==PY_SHA||body.bar_count!==bars.length||!Array.isArray(body.time_ms)||!Array.isArray(body.close)||!body.time_ms.every((v:number,i:number)=>v===bars[i].timestamp)||!body.close.every((v:number,i:number)=>v===bars[i].close))throw Error('DDDS_PYTHON_INPUT_DIFFERENT_FROM_REACT_CHART');
   setResult(body as Result);
  }catch(e){setError(String(e))}
  finally{clearTimeout(timer);setRunning(false)}
 }
 return <div className="pine-compare-page" data-testid="ddds-shared-chart-comparison">
   <section className="panel">
     <h1>DDDS · 기존 우리 사이트 Pine 차트와 Python 차트</h1>
     <p>동일한 {bars.length}개 OHLCV 봉(종목·시간축·시각 포함)을 두 실행 엔진에 입력합니다. 왼쪽은 기존 Vela/PineWorkerEngine, 오른쪽은 DDDS 141줄을 변환한 Python입니다.</p>
     <p><a href={TV_URL} target="_blank" rel="noopener noreferrer">원본 TradingView 전략 실제 차트 열기</a> · 이 비교의 시세는 TradingView 원본 페이지에서 추출한 값이 아닌 <b>우리 사이트 기존 차트 API의 값</b>입니다.</p>
     <p>데이터 제공자: {sameData.market_data.provider||'알 수 없음'} · {sameData.symbol} · {sameData.horizon}</p>
     {!ready&&<div className="empty-state">정확한 DDDS Pine SHA, NASDAQ:AMZN 2h, 대체 시세 없는 40~300봉을 확보하지 못해 실행을 차단했습니다.</div>}
     <label><input type="checkbox" checked={mpl} onChange={e=>setMpl(e.target.checked)}/> DDDS 원본 MPL-2.0 출처·저작권 표시 확인 및 Python 변환 실행 승인</label>
     <div className="runtime-controls"><button disabled={!ready||!mpl||running} onClick={execute}>{running?'같은 봉으로 계산 중…':'▶ 같은 봉을 Python에 전달해 비교'}</button></div>
     {error&&<div className="empty-state">DDDS Python 실행 실패: {error}</div>}
     <div className="runtime-note" data-testid="ddds-same-bar-status">{aligned?'두 엔진 입력 데이터 '+bars.length+'/'+bars.length+'봉 동일':'동일 시장 데이터 Python 실행 확인 전'}</div>
   </section>
   <div className="pine-compare-grid">
    <section className="panel"><h2>왼쪽 · 기존 NativePineChartControl</h2>
     <p>DDDS Pine 원본 실행, 스냅샷 이미지가 아닙니다.</p>
     {ready&&<NativePineChartControl key={sameData.symbol+sameData.horizon+bars[0]?.timestamp} data={sameData} source={source} onCapture={setCapture} onRuntime={x=>setRuntime(x.state+(x.message?' · '+x.message:''))}/>}
     <p data-testid="ddds-vela-status">{runtime} · {capture?'지표 '+capture.plot_names.length+'개 추출':'지표 출력 확인 전'}</p>
    </section>
    <section className="panel"><h2>오른쪽 · 동일 봉의 DDDS 생성 Python</h2>
     {aligned&&result?<PythonPlot data={sameData} result={result}/>:<div className="empty-state">Python 실행 결과 미확인. 별도 시세를 가져오지 않습니다.</div>}
    </section>
   </div>
   <section className="panel" data-testid="ddds-plot-comparison">
    <h3>시각별 DDDS 지표값 간단 비교</h3>
    <p>{stats.status} · 공통 지표값 {stats.compared}개 · 허용오차 내 {stats.matched}개 · 불일치 {stats.mismatched}개 · 최대 차이 {stats.maxDifference.toFixed(6)}</p>
    <p>Vela가 DDDS 전체 문법을 실행하지 못하면 오류를 표시하고 지표 일치를 주장하지 않습니다. TradingView 원본 사이트 지표 및 과거 거래 299건 비교와는 별개입니다.</p>
   </section>
 </div>;
}
