import {useEffect,useRef,useState} from 'react';
import {Vela} from '@luxalgo/vela';
import {PineWorkerEngine} from '@luxalgo/vela-pinets';
import type {PineVisualResponse} from '../types';

type Props={
  data:PineVisualResponse;
  source:string;
  onRuntime?:(x:{state:'loading'|'ready'|'error';message?:string;kind?:string})=>void;
};

export function NativePineChartControl({data,source,onRuntime}:Props){
  const host=useRef<HTMLDivElement>(null);
  const [localError,setLocalError]=useState('');

  useEffect(()=>{
    const el=host.current;
    if(!el||!source||!(data.bars||[]).length)return;

    let disposed=false;
    setLocalError('');
    onRuntime?.({state:'loading'});

    const bars=(data.bars||[]).map(b=>({
      time:Number(b.timestamp),
      open:Number(b.open),
      high:Number(b.high),
      low:Number(b.low),
      close:Number(b.close),
      volume:Number(b.volume||0),
    }));

    const chart=new Vela(el,{
      data:bars as any,
      timeframe:data.horizon||'1h',
      live:false,
      theme:'light',
    } as any);

    chart.registerEngine('pine',new PineWorkerEngine());

    const handle=chart.addIndicator(source);
    const offReady=handle.on('ready',()=>{
      if(disposed)return;
      onRuntime?.({state:'ready',kind:(handle as any).kind||data.kind});
    });
    const offError=handle.on('error',(payload:any)=>{
      if(disposed)return;
      const message=payload?.error?.message||payload?.message||String(payload?.error||payload||'Pine runtime error');
      setLocalError(message);
      onRuntime?.({state:'error',message,kind:data.kind});
    });

    chart.ready().then(()=>{
      if(!disposed) chart.resize();
    }).catch((err:any)=>{
      if(disposed)return;
      const message=err?.message||String(err);
      setLocalError(message);
      onRuntime?.({state:'error',message,kind:data.kind});
    });

    const ro=new ResizeObserver(()=>{if(!disposed)chart.resize()});
    ro.observe(el);

    return()=>{
      disposed=true;
      ro.disconnect();
      try{offReady?.()}catch{}
      try{offError?.()}catch{}
      chart.destroy();
      el.innerHTML='';
    };
  },[data,source,onRuntime]);

  return <div className="native-pine-shell">
    <div ref={host} className="native-pine-chart"/>
    {localError&&<div className="native-pine-error"><b>Native Pine 실행 오류</b><span>{localError}</span></div>}
  </div>;
}
