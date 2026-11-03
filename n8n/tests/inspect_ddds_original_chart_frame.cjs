/* Test whether the ORIGINAL TradingView DDDS script publication page itself
 * can run as an actual interactive chart when framed on an external site.
 * No emulated TradingView widget and no substitute symbol.
 */
const {chromium}=require('playwright');
const fs=require('fs');
const path=require('path');
const out=process.env.DDDS_ORIGINAL_CHART_PROBE_DIR||'/tmp/ddds-original-chart-probe';
const original='https://www.tradingview.com/script/LkgKT3TG-Displaced-Donchian-Decycler-Trend-Breakout-Strategy-with-MFI/';
(async()=>{
 fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
 const ctx=await browser.newContext({viewport:{width:1550,height:1100}});
 const page=await ctx.newPage();
 const data={status:'STARTED',original,framed_canvas_visible:false,
   actual_origin_chart_inside_external_frame:false,
   main_document_headers:{},frame_status:null,frame_url:null,errors:[]};
 page.on('console',m=>{if(m.type()==='error'&&data.errors.length<30)data.errors.push(m.text().slice(0,400))});
 page.on('pageerror',e=>data.errors.push(e.message.slice(0,150)));
 page.on('response',async r=>{
    if(r.url().split('?')[0]===original){
       data.frame_status=r.status();
       const h=await r.allHeaders().catch(()=>({}));
       data.main_document_headers={
        x_frame_options:h['x-frame-options']||null,
        content_security_policy_frame_ancestors:(h['content-security-policy']||'').match(/frame-ancestors[^;]*/)?.[0]||null
       };
    }
 });
 try{
   await page.setContent('<!DOCTYPE html><title>External WF02 chart iframe compatibility</title><iframe id="ddds-original" width="1450" height="800" src="'+original+'"></iframe>');
   await page.waitForTimeout(13000);
   const frame=page.frame({url:/tradingview\.com\/script\/LkgKT3TG/});
   data.frame_url=frame?.url()||null;
   data.framed_canvas_visible=Boolean(frame&&await frame.locator('[data-name="publication-view-chart-container"] canvas').count()>0);
   data.actual_origin_chart_inside_external_frame=data.framed_canvas_visible;
   data.status='FRAME_POLICY_TESTED';
 }catch(e){data.status='FRAME_TEST_ERROR';data.errors.push(String(e).slice(0,380))}
 finally{
   fs.writeFileSync(path.join(out,'original-publication-iframe-compatibility.json'),JSON.stringify(data,null,2));
   console.log('DDDS_PUBLICATION_ORIGINAL_IFRAME '+JSON.stringify(data));
   await browser.close();
 }
})();
