import fs from 'node:fs/promises';
const BASE=process.env.CHART_BASE_URL||'http://127.0.0.1:4173';
const probes=[];
const blocked=await fetch(BASE+'/api/chart?symbol=UNKNOWN%3AAAPL&range=5d');
const block=await blocked.json();
probes.push({name:'unknown exchange never silently maps to other exchange',pass:blocked.status===422,status:blocked.status,body:block});
const badRange=await fetch(BASE+'/api/chart?symbol=NASDAQ%3AAAPL&range=broken');
probes.push({name:'unknown range is rejected',pass:badRange.status===400,status:badRange.status});
for(const range of ['5d','1y']){
 try{
  const response=await fetch(BASE+'/api/chart?symbol=NASDAQ%3AAAPL&range='+range,{signal:AbortSignal.timeout(35000)});
  const payload=await response.json();
  const bars=payload.bars||[];
  const valid=bars.length>=5&&bars.every((b,i)=>Number.isFinite(b.t)&&Number.isFinite(b.o)&&Number.isFinite(b.h)&&Number.isFinite(b.l)&&Number.isFinite(b.c)&&b.h>=Math.max(b.o,b.c)-.000001&&b.l<=Math.min(b.o,b.c)+.000001&&(i===0||b.t>bars[i-1].t));
  const ageDays=bars.length?(Date.now()-bars.at(-1).t*1000)/86400000:null;
  probes.push({name:'live Yahoo OHLCV '+range,pass:response.ok&&valid&&ageDays>=-2&&ageDays<30,status:response.status,provider:payload.provider,sourceTicker:payload.resolvedSymbol,interval:payload.interval,rows:bars.length,ageDays,error:payload.error||null});
 }catch(err){probes.push({name:'live Yahoo OHLCV '+range,pass:false,error:String(err)})}
}
await fs.mkdir('artifacts',{recursive:true});
await fs.writeFile('artifacts/chart-live-provider.json',JSON.stringify({probes,scope:'Real provider network, never local fixture',at:new Date().toISOString()},null,2));
for(const p of probes)console.log((p.pass?'PASS':'FAIL')+' '+JSON.stringify(p));
if(probes.some(x=>!x.pass))process.exitCode=1;
