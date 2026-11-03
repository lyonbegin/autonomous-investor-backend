/* Existing Railway 4-stage screen: SELECT exact DDDS (not automatic),
 * run strategy->library->Python->real AMZN 300bar chart, verify truthful
 * PARTIAL_BLOCKED for TradingView order parity and link to original WF02.
 */
const {chromium}=require('playwright');
const fs=require('fs');
const base=process.env.WF02_EDITOR_BASE||
 'https://investment-n8n-native-editor-production.up.railway.app';
const out=process.env.FREE_INTEGRATED_EVIDENCE_DIR||'/tmp/ddds-integrated-e2e';
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
 try{
  const page=await browser.newPage({viewport:{width:1490,height:1000},locale:'ko-KR'});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const response=await page.goto(base+'/admin/index.html?section=tests',
     {waitUntil:'domcontentloaded',timeout:45000});
  if(response?.status()!==200)throw Error('INTEGRATED_ORIGINAL_PAGE_NOT_200');
  await page.locator('#integrated-start').waitFor({state:'visible',timeout:55000});
  const uiReady=await page.locator('#integrated-source option').count();
  if(uiReady<2)await page.waitForFunction(
    ()=>document.querySelectorAll('#integrated-source option').length>1,
    null,{timeout:45000});
  const opts=await page.locator('#integrated-source option').evaluateAll(
    els=>els.map(x=>({value:x.value,text:x.textContent})));
  const chosen=opts.find(x=>x.text?.includes('PUB;5442675d418140c58486eb4a7ae12768')&&
                         x.text?.includes('snapshot-sha256-5a245e99447f1301'));
  if(!chosen)throw Error('EXACT_DDDS_NOT_IN_INTEGRATED_SELECTOR '+JSON.stringify(opts.slice(0,10)));
  await page.locator('#integrated-source').selectOption(chosen.value);
  await page.locator('#integrated-start').click();
  await page.waitForFunction(()=>{
    const state=document.getElementById('integrated-label')?.textContent||'';
    return state.includes('PARTIAL_BLOCKED')||state.includes('FAILED')||state.includes('오류');
  },null,{timeout:145000});
  const statuses=await page.locator('#integrated-label').innerText();
  const log=await page.locator('#integrated-events').innerText();
  if(!statuses.includes('PARTIAL_BLOCKED'))
    throw Error('ORIGINAL_DDDS_INTEGRATED_NOT_EXECUTED '+statuses+' '+log.slice(0,850));
  const summary=await page.locator('#integrated-comparison-note').innerText();
  if(!summary.includes('300')||!summary.includes('동등성은 미검증'))
    throw Error('REAL_PYNE_DDDS_300BAR_OR_PARITY_NOTE_MISSING '+summary);
  const link=page.locator('#integrated-charts a[href="/admin/index.html?section=convert"]');
  if(await link.count()!==1)
    throw Error('INTEGRATED_DDDS_REAL_WF02_CHART_LINK_MISSING');
  const nodeNames=['wf02-01','wf02-02','wf02-03','wf02-04','wf02-05','wf02-06'];
  for(const id of nodeNames){
    if(!log.includes(id.toUpperCase()))throw Error('INTEGRATED_SIX_NODE_LOG_MISSING '+id);
  }
  if(errors.length)throw Error('JS_PAGE_ERRORS '+errors.join(';'));
  fs.mkdirSync(out,{recursive:true});
  await page.locator('#integrated-section').screenshot({path:out+'/ddds-free-pyne-integrated-4-stage.png',timeout:35000});
  fs.writeFileSync(out+'/integrated-e2e.json',JSON.stringify({
    status:'REAL_DDDS_FREE_PYNE_INTEGRATED_PIPELINE_CONFIRMED',
    exact_selected_ddds:chosen.text,
    result:statuses,
    actual_300_bars_summary:summary,
    linked_to_real_wf02:true,
    six_nodes:nodeNames,
    tv_order_parity_verified:false,
    live_orders_enabled:false,
    checked_at:new Date().toISOString(),
    errors
  },null,2));
  console.log('LIVE_DDDS_INTEGRATED_FREE_PYNE_4_STAGE_PASS',JSON.stringify({
    status:statuses,summary,source:chosen.text,allSixNodes:true,parity:false
  }).slice(0,4000));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
