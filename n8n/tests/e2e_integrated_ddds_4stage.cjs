/* REAL production site workflow: user chooses DDDS in operations console
 * ① DB pinned source ② Library NOT_REQUIRED ③ exact generated PYNE and real
 * current market Python execution ④ previous site parity proof + embedded
 * live Vela/Python on identical 300 bars. No fake screenshots or sleep-only tests.
 */
const {chromium}=require('playwright'),fs=require('fs'),path=require('path');
const SITE='https://investment-n8n-native-editor-production.up.railway.app';
const ID='PUB;5442675d418140c58486eb4a7ae12768';
const SHA='5a245e99447f13012dd026528235fc2c299cad5cb7b228653c684886dcba6507';
const PY_SHA='ef27e69cbb71bc101431a2f9f71783c37f1f8094a7a77e080032ca3bbd7994a1';
const OUT=process.env.INTEGRATED_DDDS_EVIDENCE||'/tmp/wf02-ddds-4-stage-actual';
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 fs.mkdirSync(OUT,{recursive:true});
 const browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
 const context=await browser.newContext({viewport:{width:1760,height:1010},locale:'ko-KR'});
 const page=await context.newPage();
 const report={site:SITE,source_id:ID,checks:[],js_errors:[],network_errors:[]};
 page.on('pageerror',e=>report.js_errors.push(e.message.slice(0,400)));
 page.on('requestfailed',r=>report.network_errors.push(r.url()+': '+r.failure()?.errorText));
 const snap=async name=>{try{await page.screenshot({path:path.join(OUT,name+'.png'),fullPage:true,timeout:18000})}catch(e){report.screenshot_error=String(e)}};
 try {
   const response=await page.goto(SITE+'/admin/index.html?section=tests',{waitUntil:'domcontentloaded',timeout:60000});
   if(response?.status()!==200)throw Error('ADMIN_PAGE_NOT_200 '+response?.status());
   await page.locator('#integrated-source').waitFor({timeout:30000});
   await page.waitForFunction(id=>[...document.querySelectorAll('#integrated-source option')].some(x=>x.textContent?.includes(id)),ID,{timeout:65000});
   const option=await page.locator('#integrated-source').evaluate((el,id)=>{
       const node=[...el.options].find(x=>x.textContent?.includes(id));
       return node?.value;
   },ID);
   if(!option)throw Error('APPROVED_DDDS_NOT_IN_SOURCE_SELECT');
   await page.locator('#integrated-source').selectOption(option);
   report.checks.push('EXPLICIT_PINNED_DDDS_SELECTED_IN_REAL_CONSOLE');
   const [startResp]=await Promise.all([
      page.waitForResponse(r=>r.url().endsWith('/api/investment/pipeline')&&r.request().method()==='POST',{timeout:30000}),
      page.locator('#integrated-start').click()
   ]);
   const started=await startResp.json();
   if(!startResp.ok()||!started.run_id)
     throw Error('WF02_PIPELINE_START_FAILED '+startResp.status()+' '+JSON.stringify(started));
   const runid=started.run_id;
   report.pipeline_run_id=runid;
   let result=null;
   for(let i=0;i<140;i++){
      const r=await context.request.get(SITE+'/api/investment/pipeline/'+runid,{timeout:18000});
      if(r.status()!==200)throw Error('WF02_READ_HTTP_'+r.status());
      result=await r.json();
      if(result.status!=='RUNNING')break;
      await sleep(2100);
   }
   if(!result||result.status==='RUNNING')throw Error('WF02_PIPELINE_STILL_RUNNING '+JSON.stringify(result?.result?.stages));
   report.pipeline_status=result.status;
   report.stages=result.result?.stages;
   report.chart=result.result?.chart;
   report.canonical=result.canonical_postgres;
   const stages=result.result?.stages||{},chart=result.result?.chart||{};
   if(result.status!=='SITE_CHART_VERIFIED_EVIDENCE_REUSED'||
       stages.strategy!=='REUSED_EXACT_DB_SOURCE'||
       stages.library!=='NOT_REQUIRED'||
       stages.python!=='PYNE_FREE_CURRENT_SITE_300_BARS_EXECUTED'||
       stages.chart!=='REUSED_VERIFIED_SITE_PINE_PYTHON_300_BARS')
     throw Error('WF02_4_STAGE_STATUS_INVALID '+JSON.stringify(report).slice(0,3000));
   if(chart.status!=='DDDS_CURRENT_PYTHON_EXECUTED_PRIOR_SITE_PARITY_REUSED'||
       chart.source_id!==ID||chart.source_sha256!==SHA||chart.python_sha256!==PY_SHA||
       chart.symbol!=='NASDAQ:AMZN'||chart.timeframe!=='120'||chart.bar_count!==300||
       chart.current_python_runtime_executed!==true||chart.current_input_matches_python!==true||
       chart.current_input_vela_parity_evaluated_in_this_backend_run!==false||
       chart.previous_site_parity_points!==864||chart.previous_site_parity_mismatches!==0||
       chart.official_tradingview_publication_parity_verified!==false)
      throw Error('WF02_4_STAGE_UNVERIFIED_OR_FAKE_PARITY '+JSON.stringify(chart).slice(0,2500));
   report.checks.push('REAL_300_CURRENT_SITE_BARS_EXECUTED_WITH_SHA_PINNED_PYTHON');
   report.checks.push('PREVIOUS_864_VELA_PYTHON_PARITY_EVIDENCE_REUSED_NOT_MISREPRESENTED_AS_CURRENT_RUN');
   // Screen must show latest result, not an old state or a static TV image.
   await page.waitForFunction(expected=>document.querySelector('#integrated-label')?.textContent?.includes(expected),runid,{timeout:45000});
   const iframe=page.locator('#native-compare-target iframe');
   await iframe.waitFor({timeout:40000});
   const frame=page.frameLocator('#native-compare-target iframe');
   await frame.locator('[data-testid="ddds-shared-chart-comparison"]').waitFor({timeout:60000});
   // Browser evaluates BOTH engines again, on matching currently displayed
   // OHLCV, proving a fresh visual comparison separate from the API's
   // historical evidence flag.
   await page.waitForFunction(()=>{
      const f=document.querySelector('#native-compare-target iframe');
      const doc=f?.contentDocument;
      const bar=doc?.querySelector('[data-testid="ddds-same-bar-status"]')?.textContent||'';
      const total=doc?.querySelector('[data-testid="ddds-total-plot-stats"]')?.textContent||'';
      const sync=doc?.querySelector('[data-testid="ddds-viewport-sync"]')?.textContent||'';
      return bar.includes('300/300')&&total.includes('일치 864개')&&
             total.includes('불일치 0개')&&sync.includes('양쪽 차트 날짜 동기화 확인');
   },null,{timeout:150000});
   report.live_browser=await page.locator('#native-compare-target iframe').evaluate(frame=>{
      const d=frame.contentDocument,ela=q=>d.querySelector(q);
      const left=ela('.ddds-shared-compare .native-pine-chart');
      const right=ela('[data-testid="ddds-python-chart"]');
      return {bar:ela('[data-testid="ddds-same-bar-status"]')?.textContent,
         all:ela('[data-testid="ddds-total-plot-stats"]')?.textContent,
         visible:ela('[data-testid="ddds-visible-interval"]')?.textContent,
         compare:ela('[data-testid="ddds-viewport-sync"]')?.textContent,
         native:{from:left?.dataset.visibleFrom,to:left?.dataset.visibleTo},
         python:{from:right?.dataset.visibleFrom,to:right?.dataset.visibleTo}};
   });
   if(Math.abs(Number(report.live_browser.native.from)-Number(report.live_browser.python.from))>7200000||
      Math.abs(Number(report.live_browser.native.to)-Number(report.live_browser.python.to))>7200000)
      throw Error('WF02_VELA_PYTHON_RENDERED_UTC_WINDOW_DIFFER');
   report.checks.push('LIVE_ADMIN_VELA_AND_PYTHON_CHARTS_SAME_300_BARS_864_MATCH');
   if(report.js_errors.length)throw Error('WF02_PAGE_JS_ERRORS '+report.js_errors.join(';'));
   report.success=true;
   await snap('four-stage-DDDS-Pine-Python-verified');
   console.log('WF02_DDDS_ALL_FOUR_ACTUAL_STAGES_VALIDATED '+JSON.stringify(report));
 }catch(e){
   report.success=false;report.error=String(e);
   try{report.body=(await page.locator('body').innerText({timeout:6000})).slice(0,3200)}catch{}
   await snap('failed-four-stage');
   console.error('WF02_DDDS_FOUR_STAGES_FAILED '+JSON.stringify(report).slice(0,11000));
   process.exitCode=1;
 }finally{
   fs.writeFileSync(path.join(OUT,'wf02-ddds-actual-4-stage.json'),JSON.stringify(report,null,2));
   await browser.close();
 }
})();
