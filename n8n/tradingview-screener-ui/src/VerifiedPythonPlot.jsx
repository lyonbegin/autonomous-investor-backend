import React,{useEffect,useRef} from 'react';
import {ColorType,createChart,CandlestickSeries,LineSeries,createSeriesMarkers} from 'lightweight-charts';

/**
 * Extracted from our existing verified Python chart:
 * autonomous-investor-backend@1c26e090ee1ffcc8b549f70df843d4e2fa616d4f
 * public_frontend/src/components/DddsSharedChartCompare.tsx:49-110 (PythonPlot).
 *
 * The existing data -> actual candlesticks + Python numeric plots and the
 * exact visible-window application/ResizeObserver behaviour are retained.
 * Removed only DDDS/AMZN ID restrictions and fixed DDDS-specific plot names.
 * This component never calculates prices, trades, signals or P/L.
 */
export const validWindow=v=>!!v&&Number.isFinite(v.from)&&Number.isFinite(v.to)
 &&v.from<v.to&&v.from>946684800000&&v.to<4102444800000;
export const windowOf=(bars,count)=>bars.length>=2?{
 from:bars[Math.max(0,bars.length-count)].timestamp,
 to:bars[bars.length-1].timestamp
}:null;
const PALETTE=['#2563eb','#0f766e','#8b5cf6','#c2410c','#db2777','#16a34a'];
const isNum=v=>typeof v==='number'&&Number.isFinite(v);

export function validatePythonChart(payload){
 if(!payload||payload.market_data_verified!==true)return '실제 시세 데이터 검증이 완료된 실행이 없습니다.';
 if(!payload.python_runtime_executed||payload.status!=='PYTHON_EXECUTED')
  return '실제 Python 실행이 확인되지 않았습니다.';
 if(!/^[a-f0-9]{64}$/i.test(payload.python_sha256||''))
  return '실행한 Python 소스 SHA-256이 없습니다.';
 const data=payload.data,result=payload.result;
 if(!Array.isArray(data?.bars)||data.bars.length<2)return 'OHLCV 데이터가 없습니다.';
 if(!result||typeof result.plots!=='object'||!Array.isArray(result.time_ms))
  return 'Python 출력 시계열과 타임스탬프가 없습니다.';
 if(result.time_ms.length!==data.bars.length)return '시계열 봉 수가 다릅니다.';
 let prev=0;
 for(let i=0;i<data.bars.length;i++){
  const b=data.bars[i];
  if(![b.timestamp,b.open,b.high,b.low,b.close].every(isNum)||
      b.timestamp<=prev||b.low>b.high||b.open>b.high||b.close>b.high||b.open<b.low||b.close<b.low)
   return 'OHLCV 가격·순서·범위가 올바르지 않습니다.';
  if(b.timestamp!==result.time_ms[i])return 'Python 결과와 가격 데이터의 시각이 다릅니다.';
  prev=b.timestamp;
 }
 for(const [name,values] of Object.entries(result.plots)){
  if(!Array.isArray(values)||values.length!==data.bars.length)
   return 'Python 지표 "'+name+'"의 봉 수가 일치하지 않습니다.';
  if(values.some(v=>v!==null&&!isNum(v)))
   return 'Python 지표 "'+name+'"에 비정상적인 값이 있습니다.';
 }
 return '';
}

// Exact same core as previous PythonPlot, with plot names supplied by the
// saved Python run. No hardcoded symbol, period, values, or fabricated markers.
export default function VerifiedPythonPlot({
 data,result,visibleWindow,onApplied=()=>{},height=330,showTrades=true
}){
 const root=useRef(null),instance=useRef(null),appliedRef=useRef(onApplied);
 const latestWindowRef=useRef(visibleWindow);
 latestWindowRef.current=visibleWindow;
 useEffect(()=>{appliedRef.current=onApplied},[onApplied]);
 function applyWindow(chart,el,r){
  if(!validWindow(r))return;
  const from=Math.floor(r.from/1000),to=Math.floor(r.to/1000);
  el.dataset.requestedFrom=String(r.from);
  el.dataset.requestedTo=String(r.to);
  chart.timeScale().setVisibleRange({from,to});
  const actual=chart.timeScale().getVisibleRange();
  if(actual&&typeof actual.from==='number'&&typeof actual.to==='number'){
   const checked={from:Number(actual.from)*1000,to:Number(actual.to)*1000};
   el.dataset.visibleFrom=String(checked.from);
   el.dataset.visibleTo=String(checked.to);
   appliedRef.current(checked);
  }else appliedRef.current(null);
 }
 useEffect(()=>{
  const el=root.current;if(!el||!data?.bars?.length)return;
  const chart=createChart(el,{
   width:Math.max(200,el.clientWidth),height,
   layout:{background:{type:ColorType.Solid,color:'#ffffff'},textColor:'#475569'},
   timeScale:{timeVisible:true,secondsVisible:false},
   localization:{locale:'ko-KR'},
   handleScroll:false,handleScale:false
  });
  instance.current=chart;
  const candle=chart.addSeries(CandlestickSeries,{
   upColor:'#16a34a',downColor:'#dc2626',
   borderUpColor:'#16a34a',borderDownColor:'#dc2626',
   wickUpColor:'#16a34a',wickDownColor:'#dc2626'
  });
  candle.setData(data.bars.map(b=>({
   time:Math.floor(b.timestamp/1000),open:b.open,high:b.high,low:b.low,close:b.close
  })));
  const allowedPricePlots=result.price_plot_names||Object.keys(result.plots||{});
  for(const [index,name] of allowedPricePlots.entries()){
   const values=result.plots?.[name];
   if(!Array.isArray(values)||values.length!==data.bars.length)continue;
   const pts=values.flatMap((v,i)=>isNum(v)?[{
    time:Math.floor(data.bars[i].timestamp/1000),value:v
   }]:[]);
   if(pts.length)chart.addSeries(LineSeries,{
    color:PALETTE[index%PALETTE.length],lineWidth:2,title:name
   }).setData(pts);
  }
  // Added only for saved, real Python fills; never synthesise a trade marker.
  if(showTrades&&Array.isArray(result.fills)&&result.fills.length){
   const available=new Set(data.bars.map(b=>Math.floor(b.timestamp/1000)));
   const markers=result.fills.flatMap(f=>{
    const t=Math.floor(Number(f.timestamp)/1000),qty=Number(f.qty);
    if(!available.has(t)||!isNum(qty)||qty===0)return [];
    return [{time:t,position:qty>0?'belowBar':'aboveBar',
      shape:qty>0?'arrowUp':'arrowDown',
      color:qty>0?'#16a34a':'#dc2626',
      text:(qty>0?'매수 ':'매도 ')+Math.abs(qty)}];
   }).sort((a,b)=>a.time-b.time);
   if(markers.length)createSeriesMarkers(candle,markers);
  }
  // NO fitContent(): original DDDS code intentionally keeps the chosen window.
  applyWindow(chart,el,latestWindowRef.current);
  const ro=new ResizeObserver(()=>{
   chart.applyOptions({width:Math.max(100,el.clientWidth)});
   applyWindow(chart,el,latestWindowRef.current);
  });
  ro.observe(el);
  return()=>{ro.disconnect();instance.current=null;chart.remove()};
 },[data,result,height,showTrades]);
 useEffect(()=>{
  if(instance.current&&root.current)applyWindow(instance.current,root.current,visibleWindow);
 },[visibleWindow?.from,visibleWindow?.to]);
 return <div data-testid="verified-python-chart" ref={root}
  style={{width:'100%',height}}/>;
}
