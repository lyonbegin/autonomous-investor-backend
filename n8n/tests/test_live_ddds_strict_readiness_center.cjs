/* Existing Railway WF02 SAME DDDS source/compiled/trade parity-readiness.
 * Real network, real Chromium. No synthetic market data or pretending a
 * missing PyneComp API key is a successful Python conversion.
 */
const {chromium}=require('playwright');
const fs=require('fs');
const url=process.env.WF02_EDITOR_BASE||
  'https://investment-n8n-native-editor-production.up.railway.app';
const evidence=process.env.WF02_EVIDENCE_DIR||'/tmp/ddds-parity-evidence';
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
 try{
  const page=await browser.newPage({viewport:{width:1540,height:1050},locale:'ko-KR'});
  const pageErrors=[];
  page.on('pageerror',e=>pageErrors.push(e.message));
  const response=await page.goto(url+'/admin/index.html?section=convert',
   {waitUntil:'domcontentloaded',timeout:45000});
  if(response?.status()!==200)throw Error('ORIGINAL_WF02_PAGE_NOT_AVAILABLE');
  await page.locator('#ddds-parity-check').waitFor({state:'visible',timeout:60000});
  await page.waitForFunction(()=>{
    const label=document.querySelector('#ddds-parity-summary')?.textContent||'';
    return label.includes('DDDS_VERIFICATION_BLOCKED')||
      label.includes('DDDS_READY_TO_REVIEW')||
      label.includes('실제 DDDS 동등성 점검 실패');
  },null,{timeout:20000});
  const before=await page.request.get(url+'/api/investment/tv-publication/parity/readiness');
  if(before.status()!==200)throw Error('READINESS_API_HTTP_'+before.status());
  const state=await before.json();
  if(state.pine_sha256!=='5a245e99447f13012dd026528235fc2c299cad5cb7b228653c684886dcba6507'||
     state.symbol!=='NASDAQ:AMZN'||state.timeframe_minutes!==120||
     state.source_input_defaults.startLen!==31||
     state.source_input_defaults.endLen!==36||
     state.source_input_defaults.commission_value!==0.05||
     state.strategy_report_symbol_conflict!==true||
     state.published_properties_current_report_inputs_match_defaults!==true||
     state.published_chart_snapshot_symbol!=='BATS:AMZN'||
     state.current_strategy_report_properties_symbol!=='NASDAQ:AMZN'||
     state.tradingview_pynecore_parity_verified!==false||
     state.actual_ddds_pynecore_run_available!==false||
     state.live_orders_enabled!==false||
     !state.missing_requirements.includes('VERIFIED_NASDAQ_AMZN_120MIN_FULL_HISTORY_2016_2026'))
    throw Error('UNTRUSTED_DDDS_READINESS_OR_FAKE_PARITY '+JSON.stringify(state).slice(0,850));
  const cards=page.locator('#ddds-parity-conditions .card');
  if(await cards.count()!==10)throw Error('ORIGINAL_DDDS_FIDELITY_10_CHECKS_NOT_SHOWN');
  if(!(await page.locator('#ddds-parity-details').textContent()).includes('commission_value'))
    throw Error('PINNED_COMMISSION_VALUE_NOT_SHOWN');
  await page.locator('#ddds-parity-check').click();
  await page.waitForFunction(()=>{
    const v=document.querySelector('#ddds-parity-summary')?.textContent||'';
    return v.startsWith('DDDS_VERIFICATION_BLOCKED')||v.startsWith('DDDS_READY_TO_REVIEW');
  },null,{timeout:25000});
  // This session may not have previously captured its published 299 trade rows.
  const count=state.saved_published_trade_count;
  const keySet=state.pynecomp_api_key_configured;
  if(keySet===false){
    if(!state.missing_requirements.includes('PYNESYS_API_KEY'))
      throw Error('ACTUAL_REMOTE_PYNECOMP_KEY_GATE_MISSING');
    if(state.exact_pynecomp_code_available!==false)
      throw Error('NEW_DDDS_PYTHON_ALLEGEDLY_EXISTS_WITH_NO_KEY');
  }
  await page.waitForFunction(()=>{
    const img=document.getElementById('publication-official-image');
    const backup=document.getElementById('publication-image-fallback');
    return Boolean((img?.complete && img.naturalWidth>0) ||
      (backup && getComputedStyle(backup).display!=='none'));
  },null,{timeout:27000});
  const officialChartImage=await page.locator('#publication-official-image').evaluate(img=>({
    loaded:img.complete&&img.naturalWidth>0,naturalWidth:img.naturalWidth
  }));
  const fallbackShown=await page.locator('#publication-image-fallback').isVisible();
  if(!officialChartImage.loaded&&!fallbackShown)
    throw Error('OFFICIAL_TV_DDDS_CHART_PREVIEW_BLANK_WITH_NO_SOURCE_LINK');
  console.log('WF02_OFFICIAL_DDDS_CHART_PREVIEW',JSON.stringify({officialChartImage,fallbackShown}));
  if(pageErrors.length)throw Error('JS_PAGE_ERRORS '+pageErrors.join(';'));
  fs.mkdirSync(evidence,{recursive:true});
  const panel=page.locator('#published-strategy-reference');
  await panel.screenshot({path:evidence+'/ddds-real-pynecomp-gate-in-original-wf02.png',
    timeout:25000});
  fs.writeFileSync(evidence+'/ddds-real-readiness.json',JSON.stringify(state,null,2));
  console.log('LIVE_DDDS_ORIGINAL_WF02_REAL_PARITY_READINESS_PASS',JSON.stringify({
    pineSha:state.pine_sha256,pynecompKeyConfigured:keySet,
    exactCompiled:state.exact_pynecomp_code_available,
    tvPublishedTrades:count,history:state.historical_data_coverage_verified,
    parity:state.tradingview_pynecore_parity_verified,
    unmet:state.missing_requirements
  }));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
