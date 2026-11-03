/* Real SAME market data: intercept OUR existing chart API response only to
 * truncate to 300 real bars; do not fabricate bars or substitute Pine code.
 * Then execute original deployed NativePineChartControl and export its plots.
 */
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path');
const BASE='https://autonomous-investor-public-production.up.railway.app';
const ID='PUB;5442675d418140c58486eb4a7ae12768';
const SHA='5a245e99447f13012dd026528235fc2c299cad5cb7b228653c684886dcba6507';
const OUT=process.env.DDDS_SITE_COMPARE_DIR||'/tmp/ddds-site-vela-pyne-300';
(async()=>{
 fs.mkdirSync(OUT,{recursive:true});
 const browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
 const context=await browser.newContext({viewport:{width:1470,height:1020},acceptDownloads:true});
 const page=await context.newPage();let truncated=null;
 const report={status:'STARTED',source_id:ID,public_site:BASE,
   chart_api_truncated_from:null,chart_api_sent_bars:null,
   capture_bars:null,capture_plot_names:[],errors:[]};
 page.on('pageerror',e=>report.errors.push(String(e.message).slice(0,240)));
 await page.route('**/api/public/scripts/**/chart?*',async route=>{
   const request=new URL(route.request().url());
   if(request.pathname.indexOf(encodeURIComponent(ID))<0&&decodeURIComponent(request.pathname).indexOf(ID)<0)
     return route.continue();
   const original=await route.fetch({timeout:50000});
   const body=await original.json();
   if(original.status()!==200||body.script_id!==ID||body.source_hash!==SHA||
      body.symbol!=='NASDAQ:AMZN'||body.horizon!=='2h'||body.market_data?.fallback_used===true||
      !Array.isArray(body.bars)||body.bars.length<300){
     const diagnostic={response_status:original.status(),request_url:request.pathname+request.search,
       script_id:body.script_id,source_hash:body.source_hash,symbol:body.symbol,
       horizon:body.horizon,bar_count:body.bars?.length||0,
       fallback_used:body.market_data?.fallback_used===true};
     report.errors.push('LIVE_CHART_RESPONSE_PROVENANCE_MISMATCH '+JSON.stringify(diagnostic));
     await route.fulfill({response:original});
     return;
   }
   report.chart_api_truncated_from=body.bars.length;
   truncated=body.bars.slice(-300);
   report.chart_api_sent_bars=300;
   const sliced={...body,bars:truncated,market_data:{...body.market_data,count:300}};
   await route.fulfill({response:original,contentType:'application/json',body:JSON.stringify(sliced)});
 });
 try{
   const r=await page.goto(BASE+'/scripts/'+encodeURIComponent(ID),{waitUntil:'domcontentloaded',timeout:60000});
   if(r?.status()!==200)throw Error('SITE_PAGE_HTTP_NOT_200');
   const panel=page.getByTestId('chart-control-capture');
   await panel.waitFor({timeout:55000});
   await page.waitForFunction(()=>{
     const s=document.querySelector('[data-testid="chart-control-capture"]')?.textContent||'';
     return /봉 300개 · 지표/.test(s) || /Native Pine 실행 오류/.test(document.body.innerText||'');
   },{timeout:110000});
   if(!truncated||!((await panel.innerText()).includes('봉 300개 · 지표')))
     throw Error('Vela_DDDS_300_BAR_NOT_EXECUTED '+(await panel.innerText()).slice(0,400));
   const button=panel.getByRole('button',{name:'전략 주문·체결 포함 JSON 내려받기'});
   const [file]=await Promise.all([page.waitForEvent('download',{timeout:30000}),button.click()]);
   const output=JSON.parse(fs.readFileSync(await file.path(),'utf8'));
   if(output.script_id!==ID||output.source_hash!==SHA||
      output.provenance!=='VELA_PINETS_CHART_CONTROL'||output.bars?.length!==300)
     throw Error('VELA_DDDS_CAPTURE_SOURCE_OR_SIZE_MISMATCH');
   for(let i=0;i<300;i++){
     const o=output.bars[i],p=truncated[i];
     if(o.time_ms!==p.timestamp||o.open!==p.open||o.high!==p.high||
        o.low!==p.low||o.close!==p.close||o.volume!==p.volume)
        throw Error('VELA_DDDS_INPUT_NOT_IDENTICAL_AT_'+i);
   }
   report.capture_bars=output.bars.length;
   report.capture_plot_names=output.plot_names;
   report.status='ACTUAL_VELA_DDDS_300_BAR_CAPTURED_SAME_MARKET_INPUT';
   fs.writeFileSync(path.join(OUT,'same-300-real-site-bars.json'),JSON.stringify(truncated));
   fs.writeFileSync(path.join(OUT,'same-300-vela-plots.json'),JSON.stringify(output));
   await page.screenshot({path:path.join(OUT,'ddds-site-vela-300.png'),fullPage:true});
 }catch(e){
   report.status='ACTUAL_VELA_DDDS_CAPTURE_FAILED';
   report.errors.push(String(e.stack||e).slice(0,680));
 }finally{
   fs.writeFileSync(path.join(OUT,'real-vela-capture-status.json'),JSON.stringify(report,null,2));
   console.log('SAME_300_SITE_VELA_DDDS '+JSON.stringify(report));
   await browser.close();
 }
 if(report.status!=='ACTUAL_VELA_DDDS_300_BAR_CAPTURED_SAME_MARKET_INPUT')process.exitCode=4;
})();
