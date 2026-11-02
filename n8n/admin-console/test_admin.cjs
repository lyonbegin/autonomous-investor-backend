const { chromium } = require('playwright');
const BASE=process.env.ADMIN_TEST_BASE||'https://investment-n8n-native-editor-production.up.railway.app';
const PARITY='https://investment-pine-parity-review-production.up.railway.app';
async function nav(page,url){
 let last;
 for(let attempt=0;attempt<7;attempt++){
  try{
   const response=await page.goto(url,{waitUntil:'domcontentloaded',timeout:30000});
   if(response?.status()===200)return;
   last=new Error('HTTP '+response?.status()+' at '+url);
  }catch(e){last=e}
  await page.waitForTimeout(1300);
 }
 throw last;
}
async function choose(page,workflow){
 await page.locator('[data-flow="'+workflow+'"]').first().click();
 await page.locator('#flow-panel .node-list .step').first().waitFor({timeout:30000});
}
async function run(page){
 await page.locator('#run').click();
 await page.waitForFunction(()=>document.querySelector('#run')&&!document.querySelector('#run').disabled,null,{timeout:90000});
 return page.locator('#run-log').innerText();
}
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:920}});
  const page=await context.newPage();
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await nav(page,BASE+'/admin/index.html?section=tests');
  await page.locator('#node-list .step').first().waitFor({timeout:30000});
  const n=await page.locator('#node-list .step').count();
  if(n<10)throw Error('WF01 graph missing nodes '+n);
  let logs=await run(page);
  if(!logs.includes('01 전략 1개 수집 시작 · HTTP 200 · SUCCESS')||
     !logs.includes('02 전략 최신 목록 1페이지 설정 · HTTP 200 · SUCCESS'))throw Error('WF01 N01 N02 real chain missing: '+logs.slice(0,1500));
  console.log('PASS WF01 strategy actual N01→N02 nodes, count',n);

  await choose(page,'operations/WF01-latest-library-one.json');
  if(await page.locator('#library-pine').count()!==1)throw Error('Library manual source UI missing');
  await page.locator('#run').click();
  const pending=await page.locator('#progress').innerText();
  if(!pending.includes('URL·버전·Pine 원본을 입력'))throw Error('Library missing-source must be explicit and not fake success: '+pending);
  console.log('PASS WF01 library no-source blocked with honest manual-entry instructions');

  // Large deliberately invalid Pine is not saved. It must reach the Python
  // declaration validator instead of being rejected by the old 2KB HTTP cap.
  await page.locator('#library-url').fill('https://www.tradingview.com/script/j7vCseM2-VisibleChart/');
  await page.locator('#library-version').fill('ui-validation-only');
  await page.locator('#library-pine').fill('INVALID_PINE\n'+'test comment line\n'.repeat(180));
  logs=await run(page);
  if(!logs.includes('HTTP 422')||!logs.includes('LIBRARY_PINE_DECLARATION_REQUIRED')||logs.includes('INPUT_SIZE_INVALID'))
   throw Error('WF01 library 2KB API problem persists or wrong validator: '+logs.slice(0,900));
  console.log('PASS WF01 library >2KB input is received and correctly rejected as invalid Pine; no fake library stored');


  await choose(page,'operations/WF02-pine-to-python.json');
  if(await page.locator('#node-list .step').count()!==3)throw Error('WF02 actual 3 nodes missing');
  logs=await run(page);
  if(!logs.includes('01 저장된 Pine 코드 읽기 · HTTP 200 · SUCCESS')||
     !logs.includes('02 Pine 계산·신호 Python 생성 · HTTP 200 · SUCCESS')||
     !logs.includes('03 변환 결과 또는 미지원 내용 보기 · HTTP 200 · SUCCESS'))throw Error('WF02 actual execution missing: '+logs.slice(0,3500));
  const raw=await page.locator('#node-details').innerText();
  if(!raw.includes('JSON'))throw Error('WF02 inspector lacks JSON');
  console.log('PASS WF02 3 actual Python conversion nodes and JSON inspection');

  await choose(page,'operations/WF02-chart-parity-first-stage.json');
  if(await page.locator('#node-list .step').count()!==8)throw Error('WF02 parity eight-node graph missing');
  if(await page.locator('[href="'+PARITY+'/"]').count()===0)throw Error('Parity compare UI link missing');
  const popupEvent=page.waitForEvent('popup',{timeout:20000});
  await page.locator('[data-action=compare]').first().click();
  const popup=await popupEvent;
  await popup.waitForLoadState('domcontentloaded');
  await popup.locator('#pine').waitFor({timeout:30000});
  await popup.waitForFunction(()=>document.querySelector('#pine')?.value.includes('//@version='),null,{timeout:15000});
  const imported=await popup.locator('#pine').inputValue();
  if(!imported.includes('strategy('))throw Error('Real stored Pine not imported to parity page');
  const left=await popup.locator('#leftChart').innerText();
  if(!left.includes('이미지가 아직 없습니다'))throw Error('Absent TV screenshot must remain absent: '+left);
  const status=await popup.locator('#status').innerText();
  if(!status.includes('TradingView'))throw Error('Parity import not acknowledged');
  console.log('PASS WF02 parity separate page opens and receives actual DB Pine; no fake TradingView image');
  await popup.close();

  // One click performs four actual stages with a stable selected strategy ID.
  const integrated=page.locator('#integrated-start');
  if(await integrated.count()!==1)throw Error('One-click entire pipeline control missing');
  await integrated.click();
  await page.waitForFunction(()=>{
    const text=document.querySelector('#integrated-label')?.textContent||'';
    return /TV_PARITY_PENDING|PARTIAL_BLOCKED|REVIEW_REQUIRED|FAILED|실행 시작 실패|실행 조회 실패/.test(text);
  },null,{timeout:180000});
  const firstStatus=await page.locator('#integrated-label').innerText();
  if(firstStatus.includes('실패'))throw Error('First one-click pipeline did not complete: '+firstStatus);
  const pipeline=await page.evaluate(async()=>{
    const r=await fetch('/api/investment/pipeline',{credentials:'same-origin',cache:'no-store'});
    return r.json();
  });
  const events=pipeline.events||[],stages=pipeline.result?.stages||{};
  if(stages.strategy==='NO_NEW_SOURCE'||
     stages.strategy==='BLOCKED_NO_CONVERTIBLE_SAVED_SOURCE'||
     stages.python!=='PYTHON_GENERATED'||
     stages.chart!=='CHART_PREVIEW_READY_TV_PARITY_PENDING'||
     pipeline.status!=='TV_PARITY_PENDING')
    throw Error('AUTO MODE DID NOT EXECUTE COMPLETE REAL CONVERTIBLE STRATEGY TO CHART: '+
      JSON.stringify({status:pipeline.status,source:pipeline.result?.selected_source,stages}));
  if(!pipeline.result?.selected_source||!pipeline.result?.converted_source||
     pipeline.result.selected_source.source_id!==pipeline.result.converted_source.source_id)
    throw Error('AUTO MODE CHANGED SOURCE BEFORE PYTHON/CHART');
  if(!pipeline.result.chart?.bar_count||
     pipeline.result.chart?.python_adapter!=='sequence-reversal-python'||
     pipeline.result.chart?.tv_website_parity_verified!==false)
    throw Error('AUTO MODE NO REAL CHART PREVIEW OR FALSE TRADINGVIEW PARITY: '+
      JSON.stringify(pipeline.result.chart));

  for(const name of ['strategy','library','python','chart']){
    if(!events.some(e=>e.stage===name))throw Error('No real stage persisted: '+name);
  }
  if(pipeline.result?.converted_source){
    const selected=pipeline.result.selected_source,converted=pipeline.result.converted_source;
    if(selected.source_id!==converted.source_id||selected.version_key!==converted.version_key)
      throw Error('Pipeline wrongly replaced selected source with unrelated strategy');
  }
  if(stages.chart==='BLOCKED_REAL_TV_CHART_CSV_MISSING'&&pipeline.status==='REVIEW_REQUIRED')
     throw Error('False chart verification despite missing actual TV input');
  if(!pipeline.canonical_postgres||pipeline.canonical_postgres.status!==pipeline.status)
    throw Error('Canonical Postgres pipeline status diverged: '+JSON.stringify(pipeline.canonical_postgres));
  if(pipeline.canonical_postgres.node_runs<events.length)
    throw Error('Not all pipeline stage/node records were mirrored into Postgres');
  if(pipeline.result.selected_source?.source_id&&pipeline.canonical_postgres.source_id!==
      pipeline.result.selected_source.source_id)
    throw Error('Canonical Postgres source ID changed across stage boundaries');
  if(!pipeline.result?.postgres_sync||pipeline.result.postgres_sync.postgres_sync!=='SYNCED')
    throw Error('Integrated run not finalized in canonical Postgres: '+JSON.stringify(pipeline.result?.postgres_sync));
  if(pipeline.result.postgres_trace_failures)
    throw Error('Individual stages did not persist in PostgreSQL: '+pipeline.result.postgres_trace_failures);
  const dbstatus=await page.evaluate(async()=>{
    const response=await fetch('/api/investment/database/status',{credentials:'same-origin',cache:'no-store'});
    return response.json();
  });
  if(dbstatus.status!=='ok'||dbstatus.node_runs<events.length||dbstatus.pipeline_runs<1)
    throw Error('Canonical DB stage/node execution counts missing: '+JSON.stringify(dbstatus));
  if(stages.python==='UNSUPPORTED_SELECTED_PINE'&&!events.some(e=>
       e.stage==='python'&&e.status==='UNSUPPORTED_PINE'))
    throw Error('Converter unsupported outcome hidden behind generic SUCCESS');
  await page.screenshot({path:'/tmp/investment-4stage-default.png',fullPage:true});
  console.log('PASS one-click persisted four-stage pipeline',JSON.stringify({
    status:pipeline.status,stages,events:events.length,
    postgres_node_runs:dbstatus.node_runs,postgres_pipeline_runs:dbstatus.pipeline_runs
  }));


  // Explicit saved version must remain the same across all four stages.
  await page.waitForFunction(()=>document.querySelector('#integrated-source')?.options.length>1,null,{timeout:30000});
  const selected=await page.locator('#integrated-source').evaluate(el=>{
    el.value='0';
    const option=el.options[1];
    return {label:option.textContent};
  });
  const sourceMeta=await page.evaluate(async()=>{
    const r=await fetch('/api/investment/sources',{credentials:'same-origin'});
    return (await r.json()).sources[0];
  });
  await page.locator('#integrated-start').click();
  await page.waitForFunction((previousRunId)=>{
    const text=document.querySelector('#integrated-label')?.textContent||'';
    return !text.includes(previousRunId) && /TV_PARITY_PENDING|PARTIAL_BLOCKED|REVIEW_REQUIRED|FAILED|실행 시작 실패|실행 조회 실패/.test(text);
  },pipeline.run_id,{timeout:180000});
  const secondStatus=await page.locator('#integrated-label').innerText();
  if(secondStatus.includes('실패'))throw Error('Exact pinned one-click pipeline did not complete: '+secondStatus);
  const exact=await page.evaluate(async()=>
      (await fetch('/api/investment/pipeline',{credentials:'same-origin'})).json());
  if(exact.result?.stages?.strategy!=='REUSED_EXACT_DB_SOURCE')
    throw Error('Selected DB source was not reused: '+JSON.stringify(exact.result?.stages));
  if(exact.result?.selected_source?.source_id!==sourceMeta.source_id||
     exact.result?.selected_source?.version_key!==sourceMeta.version_key)
    throw Error('Explicit source selection silently replaced '+selected.label);
  if(exact.canonical_postgres?.source_id!==sourceMeta.source_id||
     exact.canonical_postgres?.version_key!==sourceMeta.version_key)
    throw Error('Postgres canonical exact version did not match user selection');
  if(await page.locator('#integrated-final-review').count()!==1)
    throw Error('Missing persistent final side-by-side comparison panel');
  const displayedIdentity=await page.locator('#integrated-source-identity').innerText();
  if(!displayedIdentity.includes('source_id: '+sourceMeta.source_id)||
     !displayedIdentity.includes('version_key: '+sourceMeta.version_key)||
     !displayedIdentity.includes('script_version_id (PostgreSQL UUID): '+exact.canonical_postgres.script_version_id))
    throw Error('Selected source identifier mutated between selector and final review: '+displayedIdentity);
  const summaryText=await page.locator('#integrated-summary').innerText();
  if(exact.status==='PARTIAL_BLOCKED'&&
     (!summaryText.includes('차단/미지원')||!summaryText.includes('전체 검증 미완료')))
    throw Error('Summary conceals blocked stages: '+summaryText);
  if(!/^[0-9a-f]{64}$/.test(sourceMeta.source_sha256||''))
    throw Error('Exact Pine version lacks immutable SHA-256 in DB source picker');
  const url='https://autonomous-investor-public-api-production.up.railway.app/api/public/scripts/'+
      encodeURIComponent(sourceMeta.source_id)+'/compare-exact?version='+
      encodeURIComponent(sourceMeta.version_key)+'&sha256='+sourceMeta.source_sha256+
      '&symbol=NASDAQ%3ANVDA&horizon=2h';
  const response=await page.request.get(url,{timeout:110000});
  if(!response.ok())throw Error('Restored exact pinned Pine+Python API unavailable: HTTP '+
     response.status()+' '+(await response.text()).slice(0,400));
  const restored=await response.json();
  if(restored.source?.source_sha256!==sourceMeta.source_sha256||
     restored.chart?.source_hash!==sourceMeta.source_sha256||
     restored.chart?.script_id!==sourceMeta.source_id)
    throw Error('Exact source mismatch between studio, PostgreSQL and Quant comparison');
  if(restored.chart?.visual?.adapter!=='sequence-reversal-python'||!restored.chart?.bars?.length)
    throw Error('Saved Pine did not reach existing Python Quant chart adapter');
  const embedded=page.locator('#native-compare-target iframe');
  if(await embedded.count()!==1)throw Error('Existing side-by-side Pine/Python chart not linked to four-stage run');
  const iframeSrc=await embedded.getAttribute('src');
  if(!iframeSrc.includes(encodeURIComponent(sourceMeta.source_id))||
      !iframeSrc.includes(sourceMeta.source_sha256))
    throw Error('Embedded native/Python comparison not pinned to exact Pine source');
  const comparison=page.frameLocator('#native-compare-target iframe');
  await comparison.locator('.pine-compare-page').waitFor({state:'visible',timeout:120000});
  await comparison.locator('.native-pine-chart').waitFor({state:'visible',timeout:120000});
  await comparison.locator('.pine-chart-wrap').waitFor({state:'visible',timeout:120000});
  const frameText=await comparison.locator('.pine-compare-page').innerText();
  if(!frameText.includes('같은 OHLCV 사용')||!frameText.includes('거래 수 '))
    throw Error('Native Pine and Python charts are not both populated in final workflow');
  if(!frameText.includes(sourceMeta.source_id)||!frameText.includes(sourceMeta.source_sha256))
    throw Error('Embedded charts switched strategy ID or SHA');
  console.log('PASS final workflow iframe rendered native PineTS + Python price charts on same real OHLCV');
  console.log('PASS exact canonical source SHA and original Pine/Python chart linked',JSON.stringify({
     sha:sourceMeta.source_sha256,bars:restored.chart.bars.length,
     markers:restored.chart.visual.markers.length,
     python_adapter:restored.chart.visual.adapter
  }));
  if(exact.result.chart==null&&await page.locator('#integrated-left-chart img').count())
    throw Error('Fake TradingView screenshot displayed without reference');
  if(exact.result?.stages?.python!=='PYTHON_GENERATED'||
     exact.result?.stages?.chart!=='CHART_PREVIEW_READY_TV_PARITY_PENDING'||
     exact.status!=='TV_PARITY_PENDING')
    throw Error('Pinned strategy did not execute all four real stages up to chart preview: '+
       JSON.stringify(exact.result?.stages));
  await page.screenshot({path:'/tmp/investment-4stage-pinned.png',fullPage:true});
  console.log('PASS exact pinned source used through four DB stages and side-by-side real-data-only panel',
    JSON.stringify({source:sourceMeta.source_id,version:sourceMeta.version_key,
      status:exact.status,stages:exact.result?.stages}));

  const href=await page.locator('#flow-panel a[href*="workflow="]').first().getAttribute('href');
  if(!href?.includes('WF02-chart-parity-first-stage.json'))throw Error('Parity deep link wrong '+href);
  await nav(page,BASE+href);
  await page.locator('[data-stock-flow="operations/WF02-chart-parity-first-stage.json"].active').waitFor({timeout:30000});
  await page.locator('a[href="/admin/index.html"]').first().waitFor({timeout:10000});
  if(errors.length)throw Error('Browser JS errors: '+errors.join(' | '));
  console.log('PASS parity graph deep link and admin return navigation');
 }finally{await browser.close()}
})().catch(e=>{console.error(e.stack||e);process.exit(1)});
