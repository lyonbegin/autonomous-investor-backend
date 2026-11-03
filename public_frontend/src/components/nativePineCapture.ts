/** Lossless chart-control output bridge: Vela/PineTS, not TradingView web export. */
export type CapturedBar = {
  time_ms:number;open:number;high:number;low:number;close:number;volume:number;
  plots:Record<string,number|null>;
};
export type NativePineCapture = {
  provenance:'VELA_PINETS_CHART_CONTROL';
  tv_original_export:false;
  script_id:string;
  source_hash:string|null;
  symbol:string;
  timeframe:string;
  data_provider:string|null;
  runtime:'Vela + PineWorkerEngine';
  kind:'indicator'|'strategy';
  plot_names:string[];
  bars:CapturedBar[];
  trades:unknown[];
  broker_state:unknown;
  execution_settings:unknown;
  complete:boolean;
  forming:boolean;
  captured_at:string;
};
export type CapturableRun = {
  kind:'indicator'|'strategy';
  plots:Readonly<Record<string,number|null>>;
  strategy?:unknown;
  complete:boolean;
  forming:boolean;
  series(key:string):Promise<ReadonlyArray<{time:number;value:number|null}>>;
  trades():Promise<readonly unknown[]>;
};

function numberOrNull(v:unknown):number|null {
  if(v===null||v===undefined)return null;
  const n=Number(v);
  return Number.isFinite(n)?n:null;
}

export async function captureNativeRun(
  run:CapturableRun,
  inputBars:readonly {timestamp:number;open:number;high:number;low:number;close:number;volume:number}[],
  identity:{script_id:string;source_hash?:string|null;symbol:string;timeframe:string;provider?:string|null;settings?:unknown},
):Promise<NativePineCapture> {
  if(!run.complete||run.forming)throw Error('CHART_RUN_INCOMPLETE_OR_FORMING');
  if(!inputBars.length||inputBars.length>50000)throw Error('CHART_BAR_COUNT_UNSUPPORTED');
  const names=Object.keys(run.plots);
  const plotValues=await Promise.all(names.map(async name=>{
    const seq=await run.series(name);
    return [name,new Map(seq.map(x=>[Number(x.time),numberOrNull(x.value)]))] as const;
  }));
  const maps=new Map(plotValues);
  const bars=inputBars.map(b=>{
    const time_ms=Number(b.timestamp);
    if(!Number.isFinite(time_ms))throw Error('INVALID_CHART_TIMESTAMP');
    const plots:Record<string,number|null>={};
    for(const key of names)plots[key]=maps.get(key)?.get(time_ms)??null;
    return {time_ms,open:b.open,high:b.high,low:b.low,close:b.close,volume:b.volume,plots};
  });
  if(bars.some((b,i)=>i>0&&b.time_ms<=bars[i-1].time_ms))
    throw Error('CHART_TIMESTAMPS_NOT_INCREASING');
  const trades=run.kind==='strategy'?[...await run.trades()]:[];
  return {
    provenance:'VELA_PINETS_CHART_CONTROL',tv_original_export:false,
    script_id:identity.script_id,source_hash:identity.source_hash||null,
    symbol:identity.symbol,timeframe:identity.timeframe,
    data_provider:identity.provider||null,runtime:'Vela + PineWorkerEngine',
    kind:run.kind,plot_names:names,bars,trades,
    broker_state:run.strategy||null,execution_settings:identity.settings||null,
    complete:true,forming:false,captured_at:new Date().toISOString()
  };
}

function csvCell(v:unknown):string {
  if(v===null||v===undefined)return '';
  const s=String(v);
  return /[",\r\n]/.test(s)?'"'+s.replace(/"/g,'""')+'"':s;
}

export function captureToCSV(c:NativePineCapture):string {
  const cols=['time','open','high','low','close','volume',...c.plot_names];
  return [cols.map(csvCell).join(','),
    ...c.bars.map(b=>[
      new Date(b.time_ms).toISOString(),b.open,b.high,b.low,b.close,b.volume,
      ...c.plot_names.map(k=>b.plots[k]),
    ].map(csvCell).join(','))].join('\n')+'\n';
}
