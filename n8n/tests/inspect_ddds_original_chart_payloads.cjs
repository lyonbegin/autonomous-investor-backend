/* Inspect price-data transport of the ORIGINAL published DDDS chart only.
 * No unrelated chart, no private API replay, no account/session tokens saved.
 * This script does not claim chart series exists unless observed in transport.
 */
const {chromium}=require('playwright');
const fs=require('fs'), path=require('path');
const URL_PUBLIC='https://www.tradingview.com/script/LkgKT3TG-Displaced-Donchian-Decycler-Trend-Breakout-Strategy-with-MFI/';
const OUT=process.env.DDDS_ORIGINAL_CHART_PROBE_DIR||'/tmp/ddds-original-chart-probe';
const now=()=>new Date().toISOString();
const valid=(arr)=>Array.isArray(arr)&&arr.length>=5&&arr.slice(0,5).every(x=>typeof x==='number'&&Number.isFinite(x))&&arr[0]>946684800&&arr[0]<2147483647&&arr[1]>0&&arr[4]>0&&arr[3]<=Math.min(arr[1],arr[4])&&arr[2]>=Math.max(arr[1],arr[4]);
function frames(raw){
 const msgs=[];
 if(typeof raw!=='string'||raw.length>5000000)return msgs;
 let offset=0;
 while(offset<raw.length&&msgs.length<120){
  let a=raw.indexOf('~m~',offset);if(a<0)break;
  let b=raw.indexOf('~m~',a+3);if(b<0)break;
  const length=Number(raw.slice(a+3,b));if(!Number.isInteger(length)||length>5e6||length<1)break;
  const start=b+3,end=start+length;if(end>raw.length)break;offset=end;
  try{const item=JSON.parse(raw.slice(start,end));if(item&&typeof item.m==='string')msgs.push(item)}catch(e){}
 }
 return msgs;
}
function scanBars(value,rows,depth=0,budget={n:0}){
 if(depth>16||budget.n++>200000||!value||typeof value!=='object')return;
 if(Array.isArray(value)){
   if(valid(value)){
    const [ts,o,h,l,c,v]=value;
    rows.set(Math.round(ts*1000),{time_ms:Math.round(ts*1000),open:o,high:h,low:l,close:c,volume:Number.isFinite(v)?v:null});
   }else for(const x of value.slice(0,15000))if(x&&typeof x==='object')scanBars(x,rows,depth+1,budget);
 }else{
   if(valid(value.v))scanBars(value.v,rows,depth+1,budget);
   else if(value.time&&Number.isFinite(value.open)&&Number.isFinite(value.close)&&Number.isFinite(value.high)&&Number.isFinite(value.low)){
      const ts=value.time<2147483647?value.time*1000:value.time;
      if(ts>946684800000&&ts<2147483647000)rows.set(ts,{time_ms:ts,open:value.open,high:value.high,low:value.low,close:value.close,volume:Number.isFinite(value.volume)?value.volume:null});
   }
   for(const [k,x] of Object.entries(value))if(k!=='v'&&x&&typeof x==='object')scanBars(x,rows,depth+1,budget);
 }
}
(async()=>{
 fs.mkdirSync(OUT,{recursive:true});
 const browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
 const context=await browser.newContext({viewport:{width:1580,height:1120},locale:'en-US'});
 const page=await context.newPage();
 const data={status:'STARTED',url:URL_PUBLIC,http:null,chartCanvasCount:0,
   symbol:null,interval:null,websocket_method_counts:{},websocket_bars:0,
   idea_view:{seen:false,http:null,content_type:null,bytes:null,top_keys:[],bar_candidates:0},
   initial_html:{bytes:null,script_tags:0,series_data_found:false},
   xhr_bars:0,original_chart_bars_total:0,chart_market_bars_available:false,
   screenshot:'original-tv-live-canvas.png',collected_at:now(),errors:[]};
 const transportBars=new Map(),ajaxBars=new Map();
 const pending=[];
 page.on('response',res=>{
    try{
      const u=new URL(res.url());
      if(u.hostname!=='www.tradingview.com'||u.pathname!=='/idea-view/')return;
      const task=(async()=>{
        data.idea_view.seen=true;data.idea_view.http=res.status();
        const headers=await res.allHeaders();
        data.idea_view.content_type=headers['content-type']||null;
        const bytes=await res.body();
        data.idea_view.bytes=bytes.length;
        if(bytes.length>8e6)return;
        try{
          const obj=JSON.parse(bytes.toString('utf-8'));
          data.idea_view.top_keys=obj&&typeof obj==='object'?Object.keys(obj).slice(0,45):[];
          scanBars(obj,ajaxBars);
          data.idea_view.bar_candidates=ajaxBars.size;
        }catch(e){data.idea_view.json_parse_status='NON_JSON_RESPONSE'}
      })().catch(e=>data.errors.push('idea:'+e.name));
      pending.push(task);
    }catch(e){}
 });
 page.on('websocket',ws=>{
   try{if(new URL(ws.url()).hostname!=='data.tradingview.com')return;
     ws.on('framereceived',frame=>{
        for(const msg of frames(frame.payload)){
           data.websocket_method_counts[msg.m]=(data.websocket_method_counts[msg.m]||0)+1;
           if(['series_loading','timescale_update','du'].includes(msg.m))scanBars(msg.p,transportBars);
        }
     });
   }catch(e){}
 });
 page.on('pageerror',e=>data.errors.push(String(e.message).slice(0,170)));
 try{
   const response=await page.goto(URL_PUBLIC,{waitUntil:'domcontentloaded',timeout:60000});
   data.http=response?.status()||null;
   data.initial_html.bytes=(await response.body()).length;
   await page.waitForTimeout(16000);
   const dom=await page.evaluate(()=>{
     const root=document.querySelector('[data-name="publication-view-chart-container"]');
     return {canvas:root?.querySelectorAll('canvas').length||0,
       symbol:root?.querySelector('[data-qa-id="legend-source-exchange"]')?.textContent?.trim()||null,
       ticker:root?.querySelector('[data-qa-id="legend-source-title"]')?.textContent?.trim()||null,
       interval:root?.querySelector('[data-qa-id="legend-source-interval"]')?.textContent?.trim()||null,
       scripts:document.scripts.length};
   });
   data.chartCanvasCount=dom.canvas;
   data.symbol=dom.symbol+':'+dom.ticker;
   data.interval=dom.interval;
   data.initial_html.script_tags=dom.scripts;
   await page.locator('[data-name="publication-view-chart-container"]').screenshot({
     path:path.join(OUT,'original-tv-live-canvas.png'),timeout:20000
   });
   await Promise.allSettled(pending);
   data.websocket_bars=transportBars.size;
   data.xhr_bars=ajaxBars.size;
   const values=[...transportBars.values(),...ajaxBars.values()].sort((a,b)=>a.time_ms-b.time_ms);
   const uniq=new Map(values.map(x=>[x.time_ms,x]));
   data.original_chart_bars_total=uniq.size;
   if(uniq.size){
      data.original_chart_bars_first_time=Math.min(...uniq.keys());
      data.original_chart_bars_last_time=Math.max(...uniq.keys());
   }
   data.chart_market_bars_available=data.chartCanvasCount>0 &&
       dom.symbol==='NASDAQ'&&dom.interval==='2h'&&uniq.size>=40;
   data.status='ORIGINAL_PUBLICATION_TRANSPORT_INSPECTED';
   // No fabricated bars. Preserve only observed public chart transport
   // when there are real bars. Do not store other WebSocket messages.
   if(data.chart_market_bars_available){
     fs.writeFileSync(path.join(OUT,'observed-original-chart-bars.json'),
       JSON.stringify({source:'ORIGINAL_DDDS_PUBLICATION_IN_BROWSER',
       symbol:'NASDAQ:AMZN',timeframe:'120',
       bars:[...uniq.values()].sort((a,b)=>a.time_ms-b.time_ms)},null,2));
   }
 }catch(e){data.status='PROBE_FAILED';data.errors.push(String(e.stack||e).slice(0,500));}
 finally{
   fs.writeFileSync(path.join(OUT,'original-tv-transport.json'),JSON.stringify(data,null,2));
   console.log('ORIGINAL_DDDS_CHART_TRANSPORT '+JSON.stringify(data));
   await browser.close();
 }
 if(data.status!=='ORIGINAL_PUBLICATION_TRANSPORT_INSPECTED')process.exitCode=2;
})();
