/* Original Railway WF02: real UI clicks and generated DDDS Python graph.
 * Compiles exact 141-line Pine via FREE local hoox-PYNE, verifies Python
 * SHA-256 file export and real AMZN 120m 300-bar output, no false TV parity.
 */
const {chromium}=require('playwright');
const fs=require('fs');
const base=process.env.WF02_EDITOR_BASE||
  'https://investment-n8n-native-editor-production.up.railway.app';
const out=process.env.WF02_FREE_EVIDENCE_DIR||'/tmp/wf02-free-pyne-e2e';
const EXPECTED_PINE='5a245e99447f13012dd026528235fc2c299cad5cb7b228653c684886dcba6507';
const EXPECTED_PYTHON='ef27e69cbb71bc101431a2f9f71783c37f1f8094a7a77e080032ca3bbd7994a1';
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
 try{
  const page=await browser.newPage({
    viewport:{width:1560,height:1060},locale:'ko-KR',acceptDownloads:true
  });
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const response=await page.goto(base+'/admin/index.html?section=convert',
        {waitUntil:'domcontentloaded',timeout:50000});
  if(response?.status()!==200)throw Error('ORIGINAL_WF02_NOT_HTTP_200');
  await page.locator('#ddds-wf02-run').waitFor({state:'visible',timeout:50000});
  await page.waitForFunction(()=>document.getElementById('tv-publication-status')?.
       textContent?.includes('원본 확인'),null,{timeout:40000});
  const source=await (await page.request.get(base+'/api/investment/tv-publication/latest')).json();
  if(source.source_sha256!==EXPECTED_PINE||source.source_line_count!==141)
    throw Error('WRONG_ORIGINAL_USER_DDDS_SOURCE');
  if(await page.locator('#node-list .step').count()!==6)
    throw Error('MISSING_ORIGINAL_WF02_SIX_NODES');
  await page.locator('#ddds-mpl-ack').check();
  await page.locator('#ddds-wf02-run').click();
  await page.waitForFunction(()=>{
    const value=document.getElementById('ddds-register-state')?.textContent||'';
    return value.includes('DDDS 원본 고정')||
       value.includes('DDDS 실제 노드 연결 실패');
  },null,{timeout:190000});
  const reg=await page.locator('#ddds-register-state').innerText();
  if(!reg.includes('DDDS 원본 고정'))
    throw Error('REGISTER_OR_ORIGINAL_NODES_FAILED '+reg);
  const progress=await page.locator('#progress').innerText();
  if(!progress.includes('무료 PYNE Python 코드 생성·저장 완료'))
    throw Error('DDDS_FULL_FREE_CONVERSION_NOT_SUCCESS '+progress);
  const identity=await page.locator('#wf02-source-id').inputValue();
  if(identity!=='PUB;5442675d418140c58486eb4a7ae12768')
    throw Error('WF02_SOURCE_MISMATCH '+identity);

  await page.locator('#free-pyne-refresh').click();
  await page.waitForFunction(()=>document.getElementById('free-pyne-status')?.
    textContent?.includes('무료 PYNE 로컬 Python 생성됨'),null,{timeout:24000});
  const artifactResponse=await page.request.get(base+'/api/investment/free-pyne/ddds/latest');
  if(artifactResponse.status()!==200)throw Error('GENERATED_PYTHON_API_HTTP_ERROR');
  const artifact=await artifactResponse.json();
  if(!artifact.generated_python_available||
     artifact.pine_source_sha256!==EXPECTED_PINE||
     artifact.python_sha256!==EXPECTED_PYTHON||
     artifact.compiler?.api_key_required!==false||
     artifact.compiler?.installed!==true||
     artifact.tradingview_strategy_parity_verified!==false)
    throw Error('FAKE_OR_DIFFERENT_GENERATED_PYTHON '+JSON.stringify(artifact).slice(0,900));

  const [download]=await Promise.all([
    page.waitForEvent('download',{timeout:20000}),
    page.locator('#free-pyne-download').click()
  ]);
  const sourceText=fs.readFileSync(await download.path(),'utf8');
  const digest=require('crypto').createHash('sha256').update(sourceText,'utf8').digest('hex');
  if(digest!==EXPECTED_PYTHON||
      !sourceText.includes('def execute_script_compiled')||
      !sourceText.includes('CompileStrategyBroker'))
    throw Error('DOWNLOADED_DDDS_GENERATED_CODE_CORRUPT');

  await page.locator('#ddds-free-chart-run').click();
  await page.waitForFunction(()=>{
    const label=document.getElementById('ddds-free-chart-status')?.textContent||'';
    return label.includes('DDDS Python 실제 실행 성공') ||
           label.includes('DDDS 실제 Python 실행 실패');
  },null,{timeout:175000});
  const status=await page.locator('#ddds-free-chart-status').innerText();
  if(!status.includes('DDDS Python 실제 실행 성공'))
    throw Error('ACTUAL_DDDS_GENERATED_PYTHON_RUNTIME_FAILED '+status);
  const live=await page.request.get(base+'/api/investment/free-pyne/ddds/chart/latest');
  if(live.status()!==200)throw Error('ACTUAL_DDDS_RUNTIME_SESSION_NOT_STORED');
  const result=await live.json();
  if(result.status!=='EXACT_DDDS_FREE_PYNE_EXECUTED_ON_REAL_AMZN_120_BARS'||
     result.pine_source_sha256!==EXPECTED_PINE||
     result.python_sha256!==EXPECTED_PYTHON||
     result.symbol!=='NASDAQ:AMZN'||result.timeframe!=='120'||
     result.bar_count!==300||result.chart.length!==300||
     result.converter!=='hoox-pyne-0.6.31-offline'||
     result.tradingview_strategies_parity_verified!==false||
     result.complete_2016_2026_history!==false||
     result.live_orders_enabled!==false)
    throw Error('REAL_DDDS_PROVENANCE_OR_PARITY_FALSE '+JSON.stringify(result).slice(0,1200));
  const paths=await page.locator('#ddds-free-python-svg path').count();
  if(paths<2)throw Error('REAL_DDDS_PYTHON_GRAPH_NOT_DRAWN');
  const note=await page.locator('#ddds-free-chart-desc').innerText();
  if(!note.includes('DDDS Python')||!note.includes('동등성은 미검증'))
    throw Error('DDDS_SOURCE_OR_PARITY_NOTE_MISSING');
  if(errors.length)throw Error('ORIGINAL_WF02_BROWSER_JS_ERRORS '+errors.join(';'));
  fs.mkdirSync(out,{recursive:true});
  await page.locator('#published-strategy-reference').screenshot({
    path:out+'/real-ddds-free-pyne-original-wf02-chart.png',timeout:30000
  });
  fs.writeFileSync(out+'/ddds-141-to-python-and-real-amzn-300-summary.json',
    JSON.stringify({
      status:'REAL_DDDS_FREE_PYNE_WF02_CHROMIUM_PASSED',
      pine_sha:EXPECTED_PINE,
      python_sha:EXPECTED_PYTHON,
      source_lines:141,
      source_id:identity,
      actual_ohlcv_provider:result.provider,
      actual_market_symbol:result.symbol,
      actual_market_timeframe:result.timeframe,
      bars:result.bar_count,
      rendered_svg_paths:paths,
      strategy_events:result.strategy_event_count,
      generated_code_bytes:sourceText.length,
      real_six_nodes:true,
      official_tv_trade_parity_verified:false,
      full_published_history_verified:false,
      live_trading_enabled:false,
      errors
    },null,2));
  console.log('LIVE_FREE_DDDS_ORIGINAL_WF02_6_NODES_REAL_PYTHON_CHART_PASS',
       JSON.stringify({pine:EXPECTED_PINE,python:EXPECTED_PYTHON,
         bars:result.bar_count,plots:paths,tradeEvents:result.strategy_event_count,
         correctSource:true,parity:false}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
