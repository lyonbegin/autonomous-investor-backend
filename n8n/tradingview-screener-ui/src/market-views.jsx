import React,{useEffect,useMemo,useState} from 'react';
import {createPortal} from 'react-dom';
import {Activity,BarChart3,ChevronDown,LayoutGrid} from 'lucide-react';
import './market-views.css';
import LightweightPriceChart from './lightweight-price-chart.jsx';

const PERIODS=[['1D','1d'],['5D','5d'],['1M','1mo'],['3M','3mo'],['6M','6mo'],['YTD','ytd'],['1Y','1y'],['5Y','5y'],['All','max']];
const format=(n,d=2)=>Number.isFinite(n)?n.toLocaleString('en-US',{maximumFractionDigits:d,minimumFractionDigits:d}):'—';
function symbolDetails(row){
 const info=row.values['ticker-view']||{};
 return {symbol:row.id||'',code:info.name||row.id?.split(':').pop()||'—',name:info.description||info.name||row.id||'—',logo:info.logo?.logoid};
}
function PointChart({row,period,type,scale,volume,refresh}){
 const {symbol,code,name}=symbolDetails(row);
 const [result,setResult]=useState(null),[loading,setLoading]=useState(true),[error,setError]=useState('');
 const [hover,setHover]=useState(null);
 useEffect(()=>{
  const ac=new AbortController();
  setLoading(true);setError('');setResult(null);setHover(null);
  fetch('/api/chart?symbol='+encodeURIComponent(symbol)+'&range='+encodeURIComponent(period),{signal:ac.signal})
   .then(async r=>{const j=await r.json();if(!r.ok)throw Error(j.error||('HTTP '+r.status));return j})
   .then(j=>{if(!ac.signal.aborted){setResult(j);setLoading(false)}})
   .catch(e=>{if(!ac.signal.aborted){setError(String(e.message||e));setLoading(false)}});
  return()=>ac.abort();
 },[symbol,period,refresh]);
 const series=useMemo(()=>{
  const bars=result?.bars||[];if(!bars.length)return null;
  const valid=bars.filter(b=>Number.isFinite(b.c)&&Number.isFinite(b.t));
  if(!valid.length)return null;
  const baseline=valid[0].c;
  const transform=v=>scale==='Percent'?(v/baseline-1)*100:scale==='Log'?Math.log(v):v;
  const values=valid.flatMap(b=>type==='Candles'?[b.l,b.h]:[b.c]).filter(v=>Number.isFinite(v)&&v>0||scale!=='Log'&&Number.isFinite(v)).map(transform).filter(Number.isFinite);
  if(!values.length)return null;
  const minimum=Math.min(...values),maximum=Math.max(...values),spread=Math.max(maximum-minimum,Math.abs(maximum)*.005,0.0001);
  const bottom=minimum-spread*.1,top=maximum+spread*.1,W=600,chartH=189;
  const x=i=>5+i*(W-10)/Math.max(valid.length-1,1);
  const y=v=>6+(1-(transform(v)-bottom)/(top-bottom))*chartH;
  const points=valid.map((b,i)=>[x(i),y(b.c)]);
  const line=points.map((p,i)=>(i?'L':'M')+p[0].toFixed(2)+' '+p[1].toFixed(2)).join(' ');
  const area=line+' L'+x(valid.length-1).toFixed(2)+' 204 L5 204 Z';
  const maxVolume=Math.max(...valid.map(b=>b.v||0),1);
  const axis=format(Math.max(...valid.map(b=>b.c)),2);
  return {valid,W,chartH,x,y,line,area,maxVolume,top,bottom,baseline,transform,axis};
 },[result,type,scale]);
 const last=series?.valid.at(-1),previous=series?.valid.at(-2);
 const falling=last&&previous&&last.c<previous.c;
 const picked=hover===null?last:series?.valid[hover];
 const selectedDate=picked?new Intl.DateTimeFormat('ko-KR',{timeZone:result?.timezone||'UTC',month:'2-digit',day:'2-digit',hour:period==='1d'||period==='5d'?'2-digit':undefined,minute:period==='1d'||period==='5d'?'2-digit':undefined}).format(new Date(picked.t*1000)):'';
 return <article className="stock-chart-card" data-testid="chart-card" data-symbol={symbol} data-data-source={result?.provider||''}>
  <div className="stock-chart-title"><span className="stock-symbol">{code}</span><span className="stock-name" title={name}>{name}</span><a title="원본 종목 정보" target="_blank" rel="noreferrer" href={'https://kr.tradingview.com/symbols/'+encodeURIComponent(symbol.replace(':','-'))+'/'}>↗</a></div>
  {loading?<div className="stock-chart-status" role="status">실제 시계열 데이터 조회 중…</div>:
   error?<div className="stock-chart-status chart-error" role="alert">차트 데이터 없음<br/><small>{error}</small></div>:
   !series?<div className="stock-chart-status" role="alert">유효한 시계열 데이터가 없습니다.</div>:
  <>
   <div className="stock-chart-plot"><LightweightPriceChart bars={series.valid} type={type} scale={scale} volume={volume} period={period}/></div>
   <div className="stock-chart-dates"><span>{new Date(series.valid[0].t*1000).toLocaleDateString('ko-KR',{timeZone:result.timezone,month:'numeric',day:'numeric'})}</span><span>{selectedDate}</span><span>{new Date(last.t*1000).toLocaleDateString('ko-KR',{timeZone:result.timezone,month:'numeric',day:'numeric'})}</span></div>
   <div className="chart-data-source" title={'종목 '+symbol+' → '+result.resolvedSymbol+' · 제공자 '+result.provider+' · 데이터 지연 및 사용권 확인 필요'}>{result.provider} · {result.resolvedSymbol} · {series.valid.length}봉 · {result.interval}{result.delayed?' · 지연 가능':''}</div>
  </>}
 </article>;
}
function Heatmap({rows,product}){
 const pctField=product==='coin'||product==='cex'||product==='dex'?'24h_close_change|5':'change';
 const capField=product==='coin'?'market_cap_calc':product==='etf'?'aum':'market_cap_basic';
 const items=rows.map(r=>({row:r,change:Number(r.values[pctField]),cap:Number(r.values[capField])}))
  .filter(x=>Number.isFinite(x.change)&&x.row.values[pctField]!=null)
  .sort((a,b)=>(Number.isFinite(b.cap)?b.cap:0)-(Number.isFinite(a.cap)?a.cap:0));
 if(!items.length)return <div className="stock-chart-status" role="alert">히트맵에 필요한 가격 변동률 데이터가 없습니다. 해당 필드를 컬럼에 추가해 주세요.</div>;
 return <div className="stock-heatmap" data-testid="screener-heatmap">{items.slice(0,80).map(({row,change,cap})=>{
   const {symbol,code,name}=symbolDetails(row);
   const strength=Math.min(1,Math.abs(change)/8),opacity=.45+strength*.5;
   return <a key={symbol} style={{background:change>=0?'rgba(8,153,129,'+opacity+')':'rgba(242,54,69,'+opacity+')',gridColumn:Number.isFinite(cap)&&cap>0?'span '+(cap>1e12?3:cap>1e11?2:1):'span 1'}} href={'https://kr.tradingview.com/symbols/'+encodeURIComponent(symbol.replace(':','-'))+'/'} target="_blank" rel="noreferrer" title={name+' '+format(change,2)+'%'}><strong>{code}</strong><span>{format(change,2)}%</span></a>;
 })}</div>;
}
export default function MarketViews({view,rows,product}){
 const [period,setPeriod]=useState('5d'),[type,setType]=useState('Area'),[scale,setScale]=useState('Auto'),[volume,setVolume]=useState(true),[showCount,setShowCount]=useState(8),[refresh,setRefresh]=useState(0),[toolbarTarget,setToolbarTarget]=useState(null);
 useEffect(()=>{setToolbarTarget(document.getElementById('chart-toolbar-target'))},[view]);
 useEffect(()=>{setShowCount(8)},[product,view,rows?.[0]?.id]);
 const selectable=rows||[];
 const toolbar=<div className="chart-toolbar" data-testid="chart-toolbar">
   <label className="chart-view-label"><Activity size={18}/> Charts</label>
   <label> <span className="sr-only">차트 가격 축</span><select aria-label="차트 가격 축" value={scale} onChange={e=>setScale(e.target.value)}><option>Auto</option><option>Log</option><option>Percent</option></select><ChevronDown size={12}/></label>
   <label><span className="sr-only">차트 유형</span><select aria-label="차트 유형" value={type} onChange={e=>setType(e.target.value)}><option>Area</option><option>Line</option><option>Candles</option></select><ChevronDown size={12}/></label>
   <label><BarChart3 size={17}/><span className="sr-only">거래량 표시</span><select aria-label="거래량 표시" value={volume?'show':'hide'} onChange={e=>setVolume(e.target.value==='show')}><option value="show">Vol</option><option value="hide">Vol off</option></select><ChevronDown size={12}/></label>
   <div className="chart-timeframes">{PERIODS.map(([name,value])=><button key={name} type="button" className={value===period?'selected':''} data-testid={'chart-range-'+value} onClick={()=>setPeriod(value)}>{name}</button>)}</div>
   <button title="차트 새로고침" onClick={()=>setRefresh(v=>v+1)} className="chart-reload">↻</button>
  </div>;
 return <section className="chart-content" aria-label={view==='charts'?'종목 차트 보기':'종목 히트맵 보기'}>
  {view==='charts'&&(toolbarTarget?createPortal(toolbar,toolbarTarget):toolbar)}
  {view==='heatmap'?<Heatmap rows={selectable} product={product}/>:<>
   <div className="stock-chart-grid" data-testid="screener-chart-grid">
    {selectable.slice(0,showCount).map(row=><PointChart key={row.id} row={row} period={period} type={type} scale={scale} volume={volume} refresh={refresh}/>)}
   </div>
   {selectable.length>showCount&&<button className="chart-more" data-testid="chart-more" onClick={()=>setShowCount(v=>v+8)}>차트 더 보기 ({showCount}/{selectable.length})</button>}
  </>}
  {!selectable.length&&<div className="stock-chart-status">조회된 종목이 없습니다.</div>}
 </section>;
}
