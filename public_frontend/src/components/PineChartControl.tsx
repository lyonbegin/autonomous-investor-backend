import {useEffect,useMemo,useRef} from 'react';
import {ColorType,CrosshairMode,createChart,type UTCTimestamp} from 'lightweight-charts';
import type {PineVisualResponse} from '../types';

const sec=(ms:number)=>Math.floor(ms/1000) as UTCTimestamp;

export function PineChartControl({data}:{data:PineVisualResponse}){
  const host=useRef<HTMLDivElement>(null);
  const canvas=useRef<HTMLCanvasElement>(null);

  const bars=useMemo(()=>data.bars||[],[data]);

  useEffect(()=>{
    const el=host.current;
    const cv=canvas.current;
    if(!el||!cv||!bars.length)return;

    const chart=createChart(el,{
      width:el.clientWidth,
      height:620,
      layout:{background:{type:ColorType.Solid,color:'#ffffff'},textColor:'#4b5563'},
      grid:{vertLines:{color:'#eef1f5'},horzLines:{color:'#eef1f5'}},
      rightPriceScale:{borderColor:'#d9dee7'},
      timeScale:{borderColor:'#d9dee7',timeVisible:true,secondsVisible:false},
      crosshair:{mode:CrosshairMode.Normal},
      localization:{locale:'ko-KR'},
    });

    const candle=chart.addCandlestickSeries({
      upColor:'#16a34a',downColor:'#dc2626',
      borderUpColor:'#16a34a',borderDownColor:'#dc2626',
      wickUpColor:'#16a34a',wickDownColor:'#dc2626',
    });
    candle.setData(bars.map(b=>({
      time:sec(b.timestamp),
      open:b.open,high:b.high,low:b.low,close:b.close,
    })));

    const volume=chart.addHistogramSeries({
      priceFormat:{type:'volume'},
      priceScaleId:'',
      color:'#9ca3af',
    });
    volume.priceScale().applyOptions({scaleMargins:{top:0.82,bottom:0}});
    volume.setData(bars.map(b=>({
      time:sec(b.timestamp),
      value:b.volume,
      color:b.close>=b.open?'rgba(22,163,74,.32)':'rgba(220,38,38,.28)',
    })));

    const markers=(data.visual?.markers||[]).map((m:any)=>({
      time:sec(Number(m.time)),
      position:m.position||'aboveBar',
      color:m.text==='LONG'?'#16a34a':m.text==='SHORT'?'#dc2626':'#475569',
      shape:m.shape||'circle',
      text:m.text||'',
    }));
    if(markers.length)candle.setMarkers(markers as any);

    const draw=()=>{
      const rect=el.getBoundingClientRect();
      const dpr=window.devicePixelRatio||1;
      cv.width=Math.max(1,Math.floor(rect.width*dpr));
      cv.height=Math.max(1,Math.floor(rect.height*dpr));
      cv.style.width=rect.width+'px';
      cv.style.height=rect.height+'px';
      const ctx=cv.getContext('2d');
      if(!ctx)return;
      ctx.setTransform(dpr,0,0,dpr,0,0);
      ctx.clearRect(0,0,rect.width,rect.height);

      const nodes=data.visual?.nodes||[];
      for(const node of nodes){
        const base=node.side==='BSL'?'229,115,115':'38,166,154';
        const swept='128,128,128';
        for(const layer of node.layers||[]){
          const x1=chart.timeScale().timeToCoordinate(sec(layer.from_time));
          const x2=chart.timeScale().timeToCoordinate(sec(layer.to_time));
          const yTop=candle.priceToCoordinate(layer.top);
          const yBottom=candle.priceToCoordinate(layer.bottom);
          if(x1==null||x2==null||yTop==null||yBottom==null)continue;
          const left=Math.min(x1,x2), top=Math.min(yTop,yBottom);
          const w=Math.max(1,Math.abs(x2-x1)), h=Math.max(1,Math.abs(yBottom-yTop));
          const alpha=node.swept?0.12:Math.max(.08,.30-(Number(node.volume_ratio||.5)*.10));
          ctx.fillStyle=`rgba(${node.swept?swept:base},${alpha})`;
          ctx.fillRect(left,top,w,h);
        }

        const lx=chart.timeScale().timeToCoordinate(sec(node.pivot_time));
        const ly=candle.priceToCoordinate(node.pivot_price);
        if(lx!=null&&ly!=null){
          ctx.font='700 11px Inter,system-ui,sans-serif';
          ctx.textAlign='center';
          ctx.textBaseline=node.side==='BSL'?'bottom':'top';
          ctx.fillStyle=node.swept?'#16a34a':node.side==='BSL'?'#b91c1c':'#0f766e';
          ctx.fillText(node.side+(node.swept?' ✓':''),lx,ly+(node.side==='BSL'?-4:4));
        }
      }
    };

    chart.timeScale().fitContent();
    const ro=new ResizeObserver(()=>{
      chart.applyOptions({width:el.clientWidth});
      requestAnimationFrame(draw);
    });
    ro.observe(el);
    chart.timeScale().subscribeVisibleTimeRangeChange(draw);
    requestAnimationFrame(()=>requestAnimationFrame(draw));

    return()=>{
      ro.disconnect();
      chart.timeScale().unsubscribeVisibleTimeRangeChange(draw);
      chart.remove();
    };
  },[bars,data]);

  return <div className="pine-chart-wrap">
    <div ref={host} className="pine-chart-host"/>
    <canvas ref={canvas} className="pine-chart-overlay"/>
  </div>;
}
