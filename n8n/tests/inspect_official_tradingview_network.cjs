/* Evidence-only audit of requests originating from TradingView official charts.
 * No login, cookies, tokens, raw request bodies, raw WebSocket payloads, or
 * undocumented API calls are saved or replayed. No broker or account data.
 */
const {chromium}=require('playwright');
const fs=require('fs');
const http=require('http');
const path=require('path');
const OUT=process.env.TV_NETWORK_AUDIT_OUT||'/tmp/tradingview-network-audit';
fs.mkdirSync(OUT,{recursive:true});
const onlyTV=url=>{
  try {const h=new URL(url).hostname;return h==='tradingview.com'||h.endsWith('.tradingview.com')||h.endsWith('.tradingview-widget.com');}
  catch{return false;}
};
const safeUrl=u=>{try{const x=new URL(u);return x.origin+x.pathname;}catch{return 'malformed';}};
const count=(map,key)=>{map[key]=(map[key]||0)+1;};
const methods=new Set(['timescale_update','du','series_completed','symbol_resolved','study_completed',
 'create_series','create_study','quote_completed','qsd','data_update','resolve_symbol',
 'set_auth_token','critical_error','protocol_error','request_more_data','symbol_error']);
function inspectFrame(payload, map, shapes){
  if(typeof payload!=='string')return;
  const matches=[...payload.matchAll(/"m"\s*:\s*"([A-Za-z0-9_]+)"/g)].map(m=>m[1]);
  for(const m of matches)count(map,m);
  const hit=matches.find(m=>/timescale|du|series|study|strategy|order|trade|broker|resolve|qsd/i.test(m));
  if(hit&&!shapes.find(x=>x.method===hit)){
    // Never save frame content. Only method and structural size.
    shapes.push({method:hit,byte_count:Buffer.byteLength(payload),has_series:/\"s\"\s*:/.test(payload),
       has_data:/\"d\"\s*:/.test(payload),has_studies:/study/i.test(payload),
       contains_strategy_keyword:/strategy/i.test(payload),
       contains_order_keyword:/order/i.test(payload)});
  }
}
async function test(page,label,url){
  const report={scenario:label,entry_url:safeUrl(url),started:new Date().toISOString(),
    navigation_status:null,navigation_error:null,request_types:{},requests:{},responses:{},
    response_status:{},ws_connects:[],ws_messages_sent:{},ws_messages_received:{},ws_shapes:[],
    ws_frames_in:0,ws_frames_out:0,page_errors:[],page_title:null,dom:{},screen:null};
  page.on('request',req=>{
    if(!onlyTV(req.url()))return;
    count(report.request_types,req.resourceType());
    count(report.requests,req.method()+' '+safeUrl(req.url()));
  });
  page.on('response',res=>{
    if(!onlyTV(res.url()))return;
    count(report.responses,safeUrl(res.url()));
    count(report.response_status,String(res.status()));
  });
  page.on('websocket',ws=>{
    if(!onlyTV(ws.url()))return;
    report.ws_connects.push({endpoint:safeUrl(ws.url()),time:new Date().toISOString()});
    ws.on('framesent',data=>{report.ws_frames_out++;inspectFrame(data.payload,report.ws_messages_sent,[]);});
    ws.on('framereceived',data=>{report.ws_frames_in++;inspectFrame(data.payload,report.ws_messages_received,report.ws_shapes);});
    ws.on('socketerror',err=>report.page_errors.push('WebSocketError:'+String(err).slice(0,160)));
  });
  page.on('pageerror',error=>report.page_errors.push('PageError:'+String(error).slice(0,240)));
  try{
    const res=await page.goto(url,{waitUntil:'domcontentloaded',timeout:50000});
    report.navigation_status=res?.status()||null;
  }catch(e){report.navigation_error=String(e).slice(0,230);}
  await page.waitForTimeout(15000);
  try{
    report.page_title=await page.title();
    report.dom=await page.evaluate(()=>({
      iframes:document.querySelectorAll('iframe').length,
      customCharts:document.querySelectorAll('tv-advanced-chart').length,
      canvases:document.querySelectorAll('canvas').length,
      svgCharts:document.querySelectorAll('svg').length,
      visibleText:(document.body?.innerText||'').replace(/\s+/g,' ').slice(0,350),
    }));
    const fn=path.join(OUT,label+'.png');
    await page.screenshot({path:fn,fullPage:false,timeout:10000});
    report.screen=path.basename(fn);
  }catch(e){report.page_errors.push('DOM:'+String(e).slice(0,200));}
  report.completed=new Date().toISOString();
  fs.writeFileSync(path.join(OUT,label+'.json'),JSON.stringify(report,null,2));
  console.log('TV_NETWORK_SCENARIO',label,JSON.stringify({
     nav:report.navigation_status,req:report.request_types,websockets:report.ws_connects,
     ws_received:report.ws_frames_in,ws_types:report.ws_messages_received,
     interesting_http: Object.keys(report.responses).filter(x=>/chart|history|symbol|series|quote|study|strategy|script|screener/i.test(x)).slice(0,20),
     dom:report.dom,page_errors:report.page_errors.slice(0,5)
  }));
  return report;
}
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
 const server=http.createServer((req,res)=>{
   res.writeHead(200,{'content-type':'text/html; charset=utf-8'});
   res.end('<!doctype html><html lang="ko"><head><title>Official TradingView Widget Network Check</title><script type="module" src="https://widgets.tradingview-widget.com/w/en/tv-advanced-chart.js"></script></head><body><tv-advanced-chart symbol="NASDAQ:AAPL" interval="1D" timezone="Asia/Seoul" theme="light" locale="kr" style="display:block;width:1100px;height:700px"></tv-advanced-chart></body></html>');
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const port=server.address().port;
 const urls=[
   ['official_chart','https://www.tradingview.com/chart/?symbol=NASDAQ%3AAAPL'],
   ['official_widgetembed','https://www.tradingview.com/widgetembed/?symbol=NASDAQ%3AAAPL&interval=D&theme=light'],
   ['our_original_component','http://127.0.0.1:'+port+'/'],
 ];
 const reports=[];
 try{
  for(const [label,url] of urls){
    const context=await browser.newContext({viewport:{width:1320,height:850},
     locale:'ko-KR',timezoneId:'Asia/Seoul'});
    const page=await context.newPage();
    reports.push(await test(page,label,url));
    await context.close();
  }
 }finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
 const summary={
  recorded_at:new Date().toISOString(),
  disclaimers:[
   'Public browser traffic only; no authenticated TradingView account session',
   'Observed traffic may include third-party analytics and may differ by login or market entitlement',
   'Captured WebSocket method metadata only; no raw payload or session credentials',
   'A network request carrying OHLCV does not itself prove Strategy Tester trade records are exposed'
  ],
  scenarios:reports.map(r=>({
   name:r.scenario,http_status:r.navigation_status,navigation_error:r.navigation_error,
   request_count:Object.values(r.requests).reduce((a,b)=>a+b,0),
   websocket_count:r.ws_connects.length,ws_in:r.ws_frames_in,ws_out:r.ws_frames_out,
   incoming_types:r.ws_messages_received,dom:r.dom
  }))
 };
 fs.writeFileSync(path.join(OUT,'summary.json'),JSON.stringify(summary,null,2));
 console.log('TV_NETWORK_AUDIT_SUMMARY',JSON.stringify(summary));
})().catch(err=>{console.error(err);process.exit(1);});
