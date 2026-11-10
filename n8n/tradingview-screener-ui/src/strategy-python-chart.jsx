/**
 * Reused/adapted from the existing VERIFIED site's lower Python chart:
 * public_frontend/src/components/DddsSharedChartCompare.tsx#PythonPlot
 * pinned source commit 1c26e090ee1ffcc8b549f70df843d4e2fa616d4f.
 *
 * IMPORTANT: This component ONLY renders verified Python-run output.
 * It never derives strategies or profits from price candles, never
 * substitutes fake ticks, and never claims TradingView trade parity.
 */
import React,{useEffect,useMemo,useRef,useState} from 'react';
import {ColorType,createChart,CandlestickSeries,LineSeries,HistogramSeries,createSeriesMarkers} from 'lightweight-charts';

function normalize(output){
  if(!output || output.execution_status!=='EXECUTED_REAL_MARKET_DATA')
    throw new Error('시장 시세를 사용한 실제 Python 실행 결과가 없습니다.');
  if(!output.python_sha256 || !/^[0-9a-f]{64}$/.test(output.python_sha256))
    throw new Error('DB에 저장된 Python 버전 해시가 누락되었습니다.');
  if(!output.source_dataset_sha256 || !/^[0-9a-f]{64}$/.test(output.source_dataset_sha256))
    throw new Error('시장 시세 데이터셋 해시가 누락되었습니다.');
  if(!output.symbol || !output.timeframe || !Array.isArray(output.bars) || output.bars.length<2)
    throw new Error('종목·시간봉·OHLCV가 누락되었습니다.');
  const bars=output.bars.map(b=>{
    const timestamp=Number(b.timestamp);
    const v={timestamp,open:Number(b.open),high:Number(b.high),
      low:Number(b.low),close:Number(b.close),volume:Number(b.volume??0)};
    if(!Object.values(v).every(Number.isFinite) || v.timestamp<1000000000 ||
       v.low>Math.min(v.open,v.close) || v.high<Math.max(v.open,v.close))
      throw new Error('유효하지 않은 Python 실행 OHLCV입니다.');
    return v;
  });
  for(let i=1;i<bars.length;i++)if(bars[i].timestamp<=bars[i-1].timestamp)
    throw new Error('중복·역순 시각으로 차트를 표시할 수 없습니다.');
  // Source DB API contract requires epoch-milliseconds, same as verified PythonPlot.
  if(bars.some(b=>b.timestamp<100000000000))
    throw new Error('Python 차트 시각 단위는 epoch-milliseconds여야 합니다.');
  const plots=output.plots||{};
  for(const [name,values] of Object.entries(plots)){
    if(!Array.isArray(values)||values.length!==bars.length)
      throw new Error('지표 시계열 길이 불일치: '+name);
    if(values.some(v=>v!==null && (typeof v!=='number'||!Number.isFinite(v))))
      throw new Error('잘못된 Python 지표 값: '+name);
  }
  const timestamps=new Set(bars.map(b=>b.timestamp));
  const fills=(output.fills||[]).map(f=>{
    if(!Number.isFinite(f.timestamp)||!timestamps.has(f.timestamp)||
      !['BUY','SELL'].includes(f.side)||!Number.isFinite(f.price)||
      !Number.isFinite(f.quantity)||f.quantity<=0)
      throw new Error('차트 봉에 연결되지 않은 Python 주문 체결이 있습니다.');
    return f;
  });
  return {...output,bars,plots,fills};
}
const colors=['#2563eb','#0f766e','#8b5cf6','#c2410c','#db2777','#16a34a','#b45309','#0891b2'];
const second=ms=>Math.floor(ms/1000);
export default function StrategyPythonChart({result,visibleWindow=null,showVolume=true,height=340,onApplied=()=>{}}){
  const root=useRef(null),instance=useRef(null),callbackRef=useRef(onApplied),windowRef=useRef(visibleWindow);
  const [error,setError]=useState('');
  const normalized=useMemo(()=>{try{return {data:normalize(result),error:''};}catch(e){return {data:null,error:String(e.message||e)};}},[result]);
  windowRef.current=visibleWindow;callbackRef.current=onApplied;
  useEffect(()=>{
    const element=root.current,run=normalized.data;
    if(!element||!run){setError(normalized.error);return;}
    setError('');
    const chart=createChart(element,{
      width:Math.max(100,element.clientWidth),height,
      layout:{background:{type:ColorType.Solid,color:'#ffffff'},textColor:'#475569'},
      timeScale:{timeVisible:true,secondsVisible:false},
      localization:{locale:'ko-KR'},
      handleScroll:true,handleScale:true
    });
    instance.current=chart;
    const candle=chart.addSeries(CandlestickSeries,{
      upColor:'#16a34a',downColor:'#dc2626',borderUpColor:'#16a34a',
      borderDownColor:'#dc2626',wickUpColor:'#16a34a',wickDownColor:'#dc2626'
    });
    candle.setData(run.bars.map(b=>({time:second(b.timestamp),
      open:b.open,high:b.high,low:b.low,close:b.close})));
    let n=0;
    for(const [name,values] of Object.entries(run.plots)){
      const points=values.flatMap((v,i)=>v===null?[]:[{
        time:second(run.bars[i].timestamp),value:v
      }]);
      if(points.length){
        chart.addSeries(LineSeries,{color:colors[n%colors.length],lineWidth:2,title:name}).setData(points);
        n++;
      }
    }
    if(showVolume){
      const volume=chart.addSeries(HistogramSeries,{
        priceScaleId:'',priceFormat:{type:'volume'},priceLineVisible:false,lastValueVisible:false
      });
      volume.setData(run.bars.map(b=>({
        time:second(b.timestamp),value:b.volume,
        color:b.close>=b.open?'rgba(22,163,74,.40)':'rgba(220,38,38,.40)'
      })));
      volume.priceScale().applyOptions({scaleMargins:{top:0.83,bottom:0}});
    }
    if(run.fills.length){
      const markers=run.fills.map(f=>({
        time:second(f.timestamp),
        position:f.side==='BUY'?'belowBar':'aboveBar',
        color:f.side==='BUY'?'#15803d':'#b91c1c',
        shape:f.side==='BUY'?'arrowUp':'arrowDown',
        text:(f.side==='BUY'?'매수':'매도')+' '+(f.leg||'')+' '+f.quantity,
      })).sort((a,b)=>a.time-b.time);
      createSeriesMarkers(candle,markers);
    }
    function applyWindow(w){
      if(w && Number.isFinite(w.from)&&Number.isFinite(w.to)&&w.from<w.to){
        const from=second(w.from),to=second(w.to);
        chart.timeScale().setVisibleRange({from,to});
        const actual=chart.timeScale().getVisibleRange();
        if(actual && typeof actual.from==='number' && typeof actual.to==='number')
          callbackRef.current({from:Number(actual.from)*1000,to:Number(actual.to)*1000});
      }else chart.timeScale().fitContent();
    }
    try{applyWindow(windowRef.current)}catch(e){setError('표시 기간 적용 실패: '+String(e.message||e));}
    const obs=new ResizeObserver(()=>{
      chart.applyOptions({width:Math.max(100,element.clientWidth)});
    });
    obs.observe(element);
    return()=>{obs.disconnect();instance.current=null;chart.remove()};
  },[normalized,height,showVolume]);
  useEffect(()=>{
    if(instance.current && visibleWindow){
      try{
        instance.current.timeScale().setVisibleRange({
          from:second(visibleWindow.from),to:second(visibleWindow.to)
        });
      }catch(e){setError('표시 구간 불일치: '+String(e.message||e));}
    }
  },[visibleWindow?.from,visibleWindow?.to]);
  if(!normalized.data)return <div role="alert" data-testid="python-chart-blocked">{normalized.error}</div>;
  return <section data-testid="verified-python-strategy-chart">
    <div style={{display:'flex',gap:12,flexWrap:'wrap',fontSize:12,color:'#64748b',marginBottom:6}}>
      <span>{normalized.data.symbol} · {normalized.data.timeframe}</span>
      <span>실제 입력 {normalized.data.bars.length}봉</span>
      <span>Python SHA {normalized.data.python_sha256.slice(0,12)}</span>
      <span>체결 {normalized.data.fills.length}건</span>
    </div>
    {error && <p role="alert">{error}</p>}
    <div ref={root} style={{width:'100%',height}}/>
    <p style={{fontSize:11,color:'#64748b',marginTop:5}}>
      DB 등록 Python 실행 그래프입니다. 거래소 공식 원본·논문 성과와의 동등성은 별도 검증입니다.
    </p>
  </section>;
}
