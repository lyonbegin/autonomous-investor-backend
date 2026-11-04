/* Real deployed original public frontend + existing n8n editor comparison API.
 * Must click UI and verify actual 300 OHLCV matched and real plots compared.
 */
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path');
const BASE='https://autonomous-investor-public-production.up.railway.app';
const ID='PUB;5442675d418140c58486eb4a7ae12768';
const out=process.env.DDDS_WEB_UI_EVIDENCE||'/tmp/ddds-same-bars-ui-e2e';
(async()=>{
 fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
 const page=await browser.newPage({viewport:{width:1520,height:1150},locale:'ko-KR'});
 const errors=[];page.on('pageerror',e=>errors.push(e.message.slice(0,350)));
 try{
   // Verify the exact HTTP path in the user's 502 screenshot, then the UI.
   const sourceUrl='https://autonomous-investor-public-api-production.up.railway.app/api/public/scripts/'+encodeURIComponent(ID)+'/source';
   const sourceReply=await fetch(sourceUrl,{signal:AbortSignal.timeout(35000)});
   const sourceBody=await sourceReply.json();
   if(sourceReply.status!==200||sourceBody.source_hash!=='5a245e99447f13012dd026528235fc2c299cad5cb7b228653c684886dcba6507'||
      sourceBody.source_line_count!==141||sourceBody.source_provenance!=='PINNED_USER_SUPPLIED_PUBLICATION_DOM_SHA256_VERIFIED')
     throw Error('ORIGINAL_USER_502_ENDPOINT_NOT_RECOVERED '+sourceReply.status+' '+JSON.stringify(sourceBody).slice(0,290));
   console.log('DDDS_SOURCE_502_RECOVERY_LIVE_HTTP_PASS',JSON.stringify({status:sourceReply.status,sha:sourceBody.source_hash,lines:sourceBody.source_line_count,provenance:sourceBody.source_provenance}));
   const response=await page.goto(BASE+'/compare/'+encodeURIComponent(ID),{waitUntil:'domcontentloaded',timeout:60000});
   if(response?.status()!==200)throw Error('SITE_COMPARE_HTTP_FAILURE');
   const root=page.getByTestId('ddds-shared-chart-comparison');
   await root.waitFor({timeout:85000});
   // Exactly the problem in the user screenshot: opening this page must
   // trigger the actual Python execution without a manual approval/click.
   if(await root.getByRole('checkbox').count())throw Error('BLOCKING_APPROVAL_STILL_VISIBLE');
   await page.waitForFunction(()=>{
     const t=document.querySelector('[data-testid="ddds-same-bar-status"]')?.textContent||'';
     return t.includes('300/300')||document.body.innerText.includes('Python 자동 실행 실패:');
   },{timeout:160000});
   const status=await root.getByTestId('ddds-same-bar-status').innerText();
   if(!status.includes('300/300'))throw Error('NOT_SAME_300_BARS '+status+' '+(await root.innerText()).slice(0,700));
   await root.getByTestId('ddds-python-chart').waitFor({timeout:25000});
   const plots=await root.getByTestId('ddds-plot-comparison').innerText();
   const capture=await root.getByTestId('ddds-vela-status').innerText();
   if(/공통 지표값 0개/.test(plots)||!/공통 지표값 [1-9][0-9]*개/.test(plots))
     throw Error('DDDS_COMMON_NUMERIC_INDICATOR_OUTPUT_MISSING '+plots);
   if(/불일치 [1-9][0-9]*개/.test(plots))throw Error('DDDS_SAME_BARS_PLOT_MISMATCH '+plots);
   if(errors.length)throw Error('PAGE_JS_ERRORS '+errors.join('|'));
   // Reproduce the 944px screenshot: a strategy plot must not be crammed
   // into a 420px half-column. At this width, charts must stack.
   await page.setViewportSize({width:944,height:850});
   await page.waitForTimeout(1200);
   const responsive=await page.evaluate(()=>{
     const root=document.querySelector('[data-testid="ddds-shared-chart-comparison"]');
     const plot=root?.querySelector('.native-pine-chart');
     const py=root?.querySelector('[data-testid="ddds-python-chart"]');
     const grid=root?.querySelector('.pine-compare-grid');
     const cols=grid?getComputedStyle(grid).gridTemplateColumns.split(' ').length:0;
     return {columns:cols,pine_width:plot?.getBoundingClientRect().width,
             python_width:py?.getBoundingClientRect().width,
             visible_python:!!py};
   });
   if(responsive.columns!==1||!responsive.visible_python||
       (responsive.pine_width||0)<600||(responsive.python_width||0)<600)
     throw Error('USER_SCREENSHOT_944PX_LAYOUT_UNUSABLE '+JSON.stringify(responsive));
   await page.screenshot({path:path.join(out,'real-site-DDDS-944px-both-charts-auto.png'),fullPage:true});
   await page.setViewportSize({width:1710,height:1000});
   await page.waitForTimeout(900);
   await page.screenshot({path:path.join(out,'real-site-DDDS-wide-both-charts-auto.png'),fullPage:true});
   const result={status:'DDDS_REAL_SITE_TWO_CHARTS_SAME_300_BARS_VERIFIED',
     website:BASE,source_id:ID,bar_count:300,plots,vela_status:capture,responsive_944px:responsive,automatic_run:true,errors};
   fs.writeFileSync(path.join(out,'actual-browser-ui-result.json'),JSON.stringify(result,null,2));
   console.log('REAL_SITE_DDDS_TWO_CHART_PASS '+JSON.stringify(result));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
