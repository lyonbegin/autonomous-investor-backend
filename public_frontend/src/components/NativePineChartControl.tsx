import {useEffect,useRef,useState} from 'react';
import {Vela} from '@luxalgo/vela';
import {PineWorkerEngine} from '@luxalgo/vela-pinets';
import type {PineVisualResponse} from '../types';

function upgradeLegacyInputs(source:string){
  const typeMap:Record<string,string>={
    integer:'int',float:'float',bool:'bool',string:'string',source:'source',
    color:'color',time:'time',session:'session',symbol:'symbol',resolution:'timeframe'
  };
  let out='';
  let cursor=0;
  const startRe=/(^|[^\w.])input\s*\(/gm;
  while(true){
    startRe.lastIndex=cursor;
    const m=startRe.exec(source);
    if(!m)break;
    const prefix=m[1]||'';
    const callStart=m.index+prefix.length;
    const open=source.indexOf('(',callStart);
    if(open<0)break;

    let depth=0, quote='', escaped=false, close=-1;
    for(let i=open;i<source.length;i++){
      const ch=source[i];
      if(quote){
        if(escaped){escaped=false;continue}
        if(ch==='\\'){escaped=true;continue}
        if(ch===quote)quote='';
        continue;
      }
      if(ch==='"'||ch==="'"){quote=ch;continue}
      if(ch==='(')depth++;
      else if(ch===')'){
        depth--;
        if(depth===0){close=i;break}
      }
    }
    if(close<0)break;

    const body=source.slice(open+1,close);
    const tm=body.match(/(?:^|,)\s*type\s*=\s*input\.(integer|float|bool|string|source|color|time|session|symbol|resolution)\s*(?=,|$)/);
    let inferredKind:string|undefined;
    if(!tm&&/\boptions\s*=\s*\[/.test(body)){
      const named=body.match(/(?:^|,)\s*defval\s*=\s*([^,]+)/);
      const first=body.match(/^\s*([^,]+)/);
      const raw=String((named?.[1]||first?.[1]||'')).trim();
      const options=body.match(/\boptions\s*=\s*\[([\s\S]*?)\]/)?.[1]||'';
      if(/^["']/.test(raw)||/["']/.test(options)) inferredKind='string';
      else if(/^(true|false)\b/i.test(raw)) inferredKind='bool';
      else if(/[-+]?\d+\.\d+/.test(raw)||/[-+]?\d+\.\d+/.test(options)) inferredKind='float';
      else inferredKind='int';
    }
    if(!tm&&!inferredKind&&/\b(minval|maxval|step)\s*=/.test(body)){
      const named=body.match(/(?:^|,)\s*defval\s*=\s*([^,]+)/);
      const first=body.match(/^\s*([^,]+)/);
      const raw=String((named?.[1]||first?.[1]||'')).trim();
      const numericHints=[
        raw,
        body.match(/\bminval\s*=\s*([^,]+)/)?.[1]||'',
        body.match(/\bmaxval\s*=\s*([^,]+)/)?.[1]||'',
        body.match(/\bstep\s*=\s*([^,]+)/)?.[1]||'',
      ].join(' ');
      inferredKind=/[-+]?\d+\.\d+/.test(numericHints)?'float':'int';
    }
    if(!tm&&!inferredKind){
      out+=source.slice(cursor,close+1);
      cursor=close+1;
      continue;
    }

    const kind=tm?(typeMap[tm[1]]||tm[1]):inferredKind!;
    let nextBody=tm
      ? body
          .replace(/(^|,)\s*type\s*=\s*input\.(integer|float|bool|string|source|color|time|session|symbol|resolution)\s*(?=,|$)/,'$1')
          .replace(/^\s*,\s*/,'')
          .replace(/,\s*,/g,',')
      : body;
    out+=source.slice(cursor,callStart)+`input.${kind}(${nextBody})`;
    cursor=close+1;
  }
  out+=source.slice(cursor);
  return out;
}

function upgradeLegacyPine(source:string){
  const version=Number((source.match(/\/\/@version\s*=\s*(\d+)/)||[])[1]||0);
  if(!version||version>=5)return {source,legacy:false,from:version||undefined};

  let out=source.replace(/\/\/@version\s*=\s*4\b/,'//@version=5');
  out=upgradeLegacyInputs(out);
  out=out.replace(/(^|[^\w.])study\s*\(/gm,'$1indicator(');
  out=out.replace(/(^|[^\w.])security\s*\(/gm,'$1request.security(');
  out=out.replace(/(^|[^\w.])tostring\s*\(/gm,'$1str.tostring(');
  out=out.replace(/(^|[^\w.])tonumber\s*\(/gm,'$1str.tonumber(');

  const ta=[
    'sma','ema','wma','vwma','rma','rsi','atr','highest','lowest','stdev','variance',
    'change','crossover','crossunder','rising','falling','barssince','valuewhen',
    'pivothigh','pivotlow','sum','cum','correlation','linreg','percentile_nearest_rank',
    'percentile_linear_interpolation','percentrank','alma','bb','bbw','cci','cmo',
    'dmi','hma','kc','kcw','macd','mfi','mom','sar','supertrend','swma','tsi','vwap'
  ];
  for(const name of ta){
    const re=new RegExp('(^|[^\\w.])'+name+'\\s*\\(','gm');
    out=out.replace(re,'$1ta.'+name+'(');
  }

  const math=['abs','max','min','round','ceil','floor','sqrt','pow','log','exp','sign'];
  for(const name of math){
    const re=new RegExp('(^|[^\\w.])'+name+'\\s*\\(','gm');
    out=out.replace(re,'$1math.'+name+'(');
  }

  return {source:out,legacy:true,from:version};
}

type Props={
  data:PineVisualResponse;
  source:string;
  onRuntime?:(x:{state:'loading'|'ready'|'error';message?:string;kind?:string})=>void;
};

export function NativePineChartControl({data,source,onRuntime}:Props){
  const host=useRef<HTMLDivElement>(null);
  const runtimeRef=useRef(onRuntime);
  const [localError,setLocalError]=useState('');

  useEffect(()=>{runtimeRef.current=onRuntime},[onRuntime]);

  useEffect(()=>{
    const el=host.current;
    if(!el||!source||!(data.bars||[]).length)return;

    let disposed=false;
    setLocalError('');
    runtimeRef.current?.({state:'loading'});

    const bars=(data.bars||[]).map(b=>({
      time:Number(b.timestamp),
      open:Number(b.open),
      high:Number(b.high),
      low:Number(b.low),
      close:Number(b.close),
      volume:Number(b.volume||0),
    }));

    const compatible=upgradeLegacyPine(source);

    const chart=new Vela(el,{
      data:bars as any,
      timeframe:data.horizon||'1h',
      live:false,
      theme:'light',
    } as any);

    chart.registerEngine('pine',new PineWorkerEngine());

    const handle=chart.addIndicator(compatible.source);
    const offReady=handle.on('ready',()=>{
      if(disposed)return;
      runtimeRef.current?.({
        state:'ready',
        kind:(handle as any).kind||data.kind,
        message:compatible.legacy?`Pine v${compatible.from} compatibility mode`:undefined,
      });
    });
    const offError=handle.on('error',(payload:any)=>{
      if(disposed)return;
      const message=payload?.error?.message||payload?.message||String(payload?.error||payload||'Pine runtime error');
      setLocalError(message);
      runtimeRef.current?.({state:'error',message,kind:data.kind});
    });

    chart.ready().then(()=>{
      if(!disposed) chart.resize();
    }).catch((err:any)=>{
      if(disposed)return;
      const message=err?.message||String(err);
      setLocalError(message);
      runtimeRef.current?.({state:'error',message,kind:data.kind});
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
  },[data,source]);

  return <div className="native-pine-shell">
    <div ref={host} className="native-pine-chart"/>
    {localError&&<div className="native-pine-error"><b>Native Pine 실행 오류</b><span>{localError}</span></div>}
  </div>;
}
