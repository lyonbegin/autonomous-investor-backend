/* Read-only inspection of the ACTUAL published DDDS chart, not another AMZN chart.
 * Never log tokens or replay private endpoints. Observe UI network with Playwright.
 */
const {chromium}=require('playwright');
const fs=require('fs');
const path=require('path');
const PUBLICATION_URL='https://www.tradingview.com/script/LkgKT3TG-Displaced-Donchian-Decycler-Trend-Breakout-Strategy-with-MFI/';
const OUT=process.env.DDDS_ORIGINAL_CHART_PROBE_DIR||'/tmp/ddds-original-chart-probe';
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const text=x=>String(x||'').replace(/\s+/g,' ').slice(0,220);
(async()=>{
 fs.mkdirSync(OUT,{recursive:true});
 const browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
 const report={
   status:'INSPECTION_STARTED',publication_url:PUBLICATION_URL,access:'PUBLIC_CHROMIUM',
   http_status:null,title:null,chart_container_found:false,chart_content_kind:null,
   chart_container_markup_preview:null,chart_links:[],chart_buttons:[],
   canvas_count:0,iframe_count:0,iframe_sources:[],charts_visible_from_dom:[],
   observed_websockets:[],observed_series_methods:{},
   xhr_responses:[],new_pages:[],clicked_chart:false,
   chart_same_published_page_verified:false,actual_published_ohlcv_observed:false,
   source_symbol_from_published_chart:null,errors:[],
   timestamp:new Date().toISOString()
 };
 const context=await browser.newContext({viewport:{width:1520,height:1120},locale:'en-US'});
 context.on('page',p=>{
    if(!p.url().startsWith('about:'))report.new_pages.push(p.url().slice(0,220));
    p.on('framenavigated',fr=>{if(fr===p.mainFrame())report.new_pages.push(fr.url().slice(0,220));});
 });
 const page=await context.newPage();
 page.on('pageerror',e=>report.errors.push(String(e.message).slice(0,180)));
 page.on('websocket',ws=>{
    try{
      const u=new URL(ws.url());
      report.observed_websockets.push({host:u.host,path:u.pathname.slice(0,100)});
      ws.on('framereceived',frame=>{
        if(typeof frame.payload!=='string')return;
        for(const m of frame.payload.matchAll(/"m":"([a-z][a-z0-9_]*)"/g))
          report.observed_series_methods[m[1]]=(report.observed_series_methods[m[1]]||0)+1;
      });
    }catch(e){}
 });
 page.on('response',res=>{
    try{
      if(report.xhr_responses.length>60)return;
      const request=res.request();
      if(!['xhr','fetch'].includes(request.resourceType()))return;
      const u=new URL(res.url());
      if(!u.hostname.endsWith('tradingview.com'))return;
      report.xhr_responses.push({host:u.hostname,path:u.pathname.slice(0,140),
        status:res.status(),type:request.resourceType()});
    }catch(e){}
 });
 try{
   const loaded=await page.goto(PUBLICATION_URL,{waitUntil:'domcontentloaded',timeout:60000});
   report.http_status=loaded?.status()||null;
   await sleep(8500);
   report.title=await page.title();
   const data=await page.evaluate(()=>{
      const el=document.querySelector('[data-name="publication-view-chart-container"]');
      const root=el||document;
      const nodes=[...root.querySelectorAll('a,button,[role="button"]')];
      return {
       found:!!el,
       snippet:el?.outerHTML?.slice(0,6000)||'',
       image_count:root.querySelectorAll('img').length,
       canvas_count:root.querySelectorAll('canvas').length,
       iframe_count:root.querySelectorAll('iframe').length,
       iframes:[...root.querySelectorAll('iframe')].map(x=>x.getAttribute('src')||'').slice(0,10),
       imgs:[...root.querySelectorAll('img')].slice(0,8).map(x=>({alt:x.getAttribute('alt'),src:(x.getAttribute('src')||'').split('?')[0].slice(0,170)})),
       clickable:nodes.slice(0,35).map(x=>({tag:x.tagName,role:x.getAttribute('role'),
          aria:x.getAttribute('aria-label'),title:x.getAttribute('title'),text:(x.textContent||'').trim().slice(0,100),
          href:x.getAttribute('href')})),
       chart_links:[...document.querySelectorAll('a[href*="/chart/"]')].slice(0,25).map(x=>({
          text:(x.textContent||'').trim().slice(0,100),href:x.getAttribute('href')})),
       main_iframes:[...document.querySelectorAll('iframe')].slice(0,10).map(x=>x.getAttribute('src')||''),
       global_canvas_count:document.querySelectorAll('canvas').length,
       global_iframe_count:document.querySelectorAll('iframe').length,
       chartSymbol:(el?.innerText||'').slice(0,550)
      };
   });
   report.chart_container_found=data.found;
   report.chart_container_markup_preview=data.snippet;
   report.chart_buttons=data.clickable;
   report.chart_links=data.chart_links;
   report.canvas_count=data.global_canvas_count;
   report.iframe_count=data.global_iframe_count;
   report.iframe_sources=data.main_iframes;
   report.charts_visible_from_dom=data.imgs;
   report.source_symbol_from_published_chart=data.chartSymbol;
   report.chart_content_kind=data.canvas_count>0?'CANVAS':
     data.iframe_count>0?'EMBEDDED_IFRAME':data.image_count>0?'IMAGE_IN_CHART_CONTAINER':'DOM_WITHOUT_IMAGE';
   await page.screenshot({path:path.join(OUT,'original-published-chart.png'),fullPage:false});
   // UI-only click of the ORIGINAL publication chart container: no replay.
   const original=page.locator('[data-name="publication-view-chart-container"]').first();
   if(await original.count()){
     // Click only if there is an obvious UI link; never assume it opens a live original chart.
     const links=original.locator('a[href]');
     if(await links.count()){
       const choices=await links.evaluateAll(es=>es.map(e=>({
         href:e.getAttribute('href')||'',text:(e.textContent||'').trim().slice(0,80)
       })));
       report.original_chart_inner_links=choices.slice(0,25);
       let launch=choices.find(x=>/\/chart\/|open chart|launch chart/i.test(x.href+' '+x.text));
       if(launch){
         await links.filter({hasText:launch.text}).first().click({timeout:6000}).catch(e=>report.errors.push('click:'+e.name));
         report.clicked_chart=true;
         await sleep(5000);
       }
     }
   }
   report.actual_published_ohlcv_observed=
     Object.keys(report.observed_series_methods).some(x=>/timescale_update|series_loading|du/.test(x));
   report.chart_same_published_page_verified=report.actual_published_ohlcv_observed &&
     report.chart_content_kind!=='IMAGE_IN_CHART_CONTAINER';
   report.status='ORIGINAL_PUBLICATION_UI_INSPECTED';
 }catch(e){
   report.status='ORIGINAL_PUBLICATION_INSPECTION_FAILED';
   report.errors.push(String(e.stack||e).slice(0,800));
 }finally{
   fs.writeFileSync(path.join(OUT,'published-chart-probe.json'),JSON.stringify(report,null,2));
   console.log('DDDS_ORIGINAL_PUBLICATION_PROBE '+JSON.stringify(report).slice(0,27000));
   await browser.close();
 }
 if(report.status!=='ORIGINAL_PUBLICATION_UI_INSPECTED')process.exitCode=2;
})();
