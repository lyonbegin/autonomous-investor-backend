/*
 * Passive proof that official TradingView chart WebSocket series frames carry
 * typed numeric OHLCV bars. Public, unauthenticated chart only.
 * No network requests outside normal user-browser navigation. No cookies,
 * credentials, authorization tokens, raw WS frames or API replay are saved.
 * This is not a licensed TradingView market data feed or a strategy-trade ledger.
 */
const {chromium}=require('playwright');
const fs=require('fs');
const path=require('path');
const OUTPUT=process.env.TV_BAR_AUDIT_DIR||'/tmp/tv-bar-audit';
fs.mkdirSync(OUTPUT,{recursive:true});
const WAIT=Number(process.env.TV_BAR_WAIT_MS||15000);
function extractMessages(frame) {
 if(typeof frame!=='string')return [];
 const parsed=[];
 let cursor=0;
 for(let i=0;i<500;i++){
  const pos=frame.indexOf('~m~',cursor);
  if(pos<0)break;
  const marker=frame.indexOf('~m~',pos+3);
  if(marker<0)break;
  const lengthText=frame.slice(pos+3,marker);
  if(!/^\d{1,8}$/.test(lengthText))break;
  const len=Number(lengthText),start=marker+3;
  if(len>2_000_000||start+len>frame.length)break;
  const part=frame.slice(start,start+len);
  cursor=start+len;
  if(part[0]!=='{')continue;
  try {
   const obj=JSON.parse(part);
   if(obj&&typeof obj.m==='string')parsed.push(obj);
  }catch{}
 }
 if(!parsed.length&&frame.startsWith('{')){
  try{const obj=JSON.parse(frame);if(obj&&typeof obj.m==='string')parsed.push(obj);}catch{}
 }
 return parsed;
}
function isOHLCV(v) {
 if(!Array.isArray(v)||v.length<5||v.length>8)return false;
 if(v.slice(0,5).some(x=>typeof x!=='number'||!Number.isFinite(x)))return false;
 const [t,o,h,l,c]=v;
 if(t<100000000||t>5000000000||o<=0||c<=0||h<Math.max(o,c)||l>Math.min(o,c)||l<0)return false;
 return true;
}
function harvest(obj,barMap,stats,method){
 const stack=[{node:obj,depth:0}],seen=new WeakSet();
 while(stack.length){
  const {node,depth}=stack.pop();
  if(depth>15||node===null||typeof node!=='object'||seen.has(node))continue;
  seen.add(node);
  if(Array.isArray(node.v)&&isOHLCV(node.v)&&/series|timescale|^du$/.test(method)){
    const v=node.v;
    const t=Math.round(v[0]*1000),o=v[1],h=v[2],l=v[3],c=v[4];
    const volume=(typeof v[5]==='number'&&Number.isFinite(v[5]))?v[5]:null;
    const key=String(t);
    const prev=barMap.get(key);
    barMap.set(key,{time_ms:t,open:o,high:h,low:l,close:c,volume});
    stats.acceptedSeriesBars++;
    if(prev&&prev.close!==c)stats.replacedBars++;
  }
  for(const val of Object.values(node)){
    if(val&&typeof val==='object')stack.push({node:val,depth:depth+1});
  }
 }
}
async function main(){
 const browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
 const context=await browser.newContext({viewport:{width:1310,height:840},locale:'en-US'});
 const page=await context.newPage();
 const bars=new Map(),stats={seenWSFrames:0,seenWSMessages:{},wsDomains:{},acceptedSeriesBars:0,replacedBars:0,
  maxPayloadBytes:{},errors:[],responseStatus:null};
 const count=(o,k)=>{o[k]=(o[k]||0)+1;};
 page.on('websocket',ws=>{
  const host=new URL(ws.url()).hostname;
  if(!['data.tradingview.com','widgetdata.tradingview.com'].includes(host))return;
  count(stats.wsDomains,host);
  ws.on('framereceived',e=>{
    stats.seenWSFrames++;
    const payload=e.payload;
    const size=typeof payload==='string'?Buffer.byteLength(payload):payload.length||0;
    for(const msg of extractMessages(payload)){
      count(stats.seenWSMessages,msg.m);
      stats.maxPayloadBytes[msg.m]=Math.max(stats.maxPayloadBytes[msg.m]||0,size);
      if(['series_loading','timescale_update','du'].includes(msg.m))
        harvest(msg.p,bars,stats,msg.m);
    }
  });
 });
 page.on('pageerror',e=>stats.errors.push(String(e).slice(0,180)));
 try{
  const res=await page.goto('https://www.tradingview.com/chart/?symbol=NASDAQ%3AAAPL',
    {waitUntil:'domcontentloaded',timeout:45000});
  stats.responseStatus=res?.status()||0;
  await page.waitForTimeout(WAIT);
  const series=[...bars.values()].sort((a,b)=>a.time_ms-b.time_ms);
  const samples=series.length?{oldest:series[0],newest:series[series.length-1]}:null;
  const invalid=series.some(v=>v.open>v.high||v.low>v.close||v.close>v.high);
  const result={
    provenance:'TRADINGVIEW_PUBLIC_OFFICIAL_CHART_WEBSOCKET_PASSIVE',
    title:await page.title(),
    user_authenticated:false,
    symbol:'NASDAQ:AAPL',selected_timeframe:'D',
    official_strategy_report_provided:false,
    official_strategy_trades_provided:false,
    is_supported_marketdata_api:false,
    browser_chart_http_status:stats.responseStatus,
    collected_unique_ohlcv_bars:series.length,
    numeric_samples:samples,
    series_time_range:series.length?[new Date(series[0].time_ms).toISOString(),new Date(series[series.length-1].time_ms).toISOString()]:[],
    numeric_validation_ok:!invalid&&series.length>=20,
    stats,
    recorded_at:new Date().toISOString()
  };
  fs.writeFileSync(path.join(OUTPUT,'bar-proof.json'),JSON.stringify(result,null,2));
  // Evidence summary only, not a bulk TradingView feed redistributed as CSV.
  console.log('TV_OFFICIAL_NUMERIC_BAR_PROOF',JSON.stringify(result).slice(0,17000));
  if(stats.responseStatus!==200||series.length<20||invalid)
    process.exitCode=2;
 }finally{
  await context.close();await browser.close();
 }
}
main().catch(err=>{console.error(err);process.exitCode=2;});
