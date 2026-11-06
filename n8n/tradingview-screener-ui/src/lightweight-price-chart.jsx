import React,{useEffect,useRef} from 'react';
import {createChart,AreaSeries,LineSeries,CandlestickSeries,HistogramSeries,PriceScaleMode,ColorType} from 'lightweight-charts';

/** TradingView open-source Lightweight Charts v5, fed ONLY by real OHLCV received upstream. */
export default function LightweightPriceChart({bars,type='Area',scale='Auto',volume=true,period='5d'}){
 const container=useRef(null);
 useEffect(()=>{
  const el=container.current;
  if(!el||!Array.isArray(bars)||!bars.length)return;
  const data=bars.filter(b=>Number.isFinite(b.t)&&Number.isFinite(b.o)&&Number.isFinite(b.h)&&Number.isFinite(b.l)&&Number.isFinite(b.c))
    .map(b=>({time:b.t,open:b.o,high:b.h,low:b.l,close:b.c,volume:Number.isFinite(b.v)?b.v:0}))
    .sort((a,b)=>a.time-b.time).filter((b,i,all)=>i===0||b.time!==all[i-1].time);
  if(!data.length)return;
  const rising=data.at(-1).close>=data[0].close;
  const color=rising?'#089981':'#f23645';
  const chart=createChart(el,{
   autoSize:true,
   layout:{background:{type:ColorType.Solid,color:'#ffffff'},textColor:'#59616b',fontSize:11,attributionLogo:true},
   grid:{vertLines:{visible:false},horzLines:{visible:false}},
   rightPriceScale:{borderVisible:false,visible:true,scaleMargins:{top:.08,bottom:.2}},
   leftPriceScale:{visible:false},
   timeScale:{borderVisible:false,timeVisible:period==='1d'||period==='5d',secondsVisible:false,rightOffset:1},
   crosshair:{vertLine:{labelVisible:true},horzLine:{labelVisible:true}},
   handleScroll:true,handleScale:true
  });
  const seriesType=type==='Candles'?CandlestickSeries:type==='Line'?LineSeries:AreaSeries;
  const options=type==='Candles'?{upColor:'#089981',downColor:'#f23645',borderUpColor:'#089981',borderDownColor:'#f23645',wickUpColor:'#089981',wickDownColor:'#f23645'}:
   type==='Line'?{color,lineWidth:2}:{
    lineColor:color,topColor:rising?'rgba(8,153,129,.30)':'rgba(242,54,69,.30)',
    bottomColor:rising?'rgba(8,153,129,.015)':'rgba(242,54,69,.015)',lineWidth:2
   };
  const price=chart.addSeries(seriesType,{...options,priceLineVisible:true,lastValueVisible:true});
  price.setData(data.map(b=>type==='Candles'?{time:b.time,open:b.open,high:b.high,low:b.low,close:b.close}:{time:b.time,value:b.close}));
  price.priceScale().applyOptions({mode:scale==='Log'?PriceScaleMode.Logarithmic:scale==='Percent'?PriceScaleMode.Percentage:PriceScaleMode.Normal,scaleMargins:{top:.08,bottom:.23}});
  if(volume){
   const vols=chart.addSeries(HistogramSeries,{priceScaleId:'',priceFormat:{type:'volume'},priceLineVisible:false,lastValueVisible:false});
   vols.setData(data.map((b,i)=>({time:b.time,value:b.volume,color:i>0&&b.close<data[i-1].close?'rgba(242,54,69,.48)':'rgba(8,153,129,.45)'})));
   vols.priceScale().applyOptions({scaleMargins:{top:.83,bottom:0}});
  }
  chart.timeScale().fitContent();
  return()=>chart.remove();
 },[bars,type,scale,volume,period]);
 return <div ref={container} data-testid="lightweight-chart" data-chart-type={type} data-chart-scale={scale} data-chart-volume={volume?'show':'hide'} className="lightweight-price-chart" aria-label="TradingView Lightweight Charts 실가격 차트"/>;
}
