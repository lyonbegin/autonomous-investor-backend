const {chromium}=require('playwright');
const fs=require('fs');
const base=process.env.WF02_EDITOR_BASE||'https://investment-n8n-native-editor-production.up.railway.app';
const out=process.env.WF02_PUBLISHED_EVIDENCE_DIR;
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const response=await page.goto(base+'/admin/index.html?section=convert',
   {waitUntil:'domcontentloaded',timeout:45000});
  if(response?.status()!==200)throw Error('ORIGINAL_WF02_NOT_HTTP_200');
  const panel=page.locator('#published-strategy-reference');
  await panel.waitFor({timeout:30000});
  await page.waitForFunction(()=>document.getElementById('tv-publication-status')?.
   textContent?.includes('원본 확인'),null,{timeout:40000});
  const live=await page.request.get(base+'/api/investment/tv-publication/latest');
  if(live.status()!==200)throw Error('WF02_PUBLISHED_REFERENCE_API_FAILED');
  const ref=await live.json();
  if(ref.status!=='TRADINGVIEW_PUBLISHED_STRATEGY_REFERENCE_PARSED'||
     ref.source_line_count!==141||
     ref.source_sha256!=='5a245e99447f13012dd026528235fc2c299cad5cb7b228653c684886dcba6507'||
     !ref.pine_source.includes('strategy.entry("Long"')||
     ref.source_rights!=='MPL-2.0'||ref.chart_id!=='LkgKT3TG'||
     !ref.report_key_facts.some(x=>x.includes('88/299'))||
     ref.tradingview_pynecore_strategy_parity_verified!==false)
    throw Error('WRONG_TRADINGVIEW_PUBLICATION_OR_UNVERIFIED_SHOWN_AS_VALID '+JSON.stringify(ref).slice(0,650));
  if(await page.locator('#node-list .step').count()!==6)
    throw Error('WF02_ORIGINAL_NODES_NOT_PRESERVED');
  const imgSrc=await page.locator('#publication-official-image').getAttribute('src');
  const actualSource=await page.locator('#publication-pine-code').textContent();
  if(await page.locator('#publication-official-image').count()!==1||
     imgSrc!==ref.chart_preview_url||
     actualSource!==ref.pine_source)
    throw Error('REAL_CHART_SNAPSHOT_OR_FULL_PINE_NOT_RENDERED '+JSON.stringify({
      imgSrc,expectedImage:ref.chart_preview_url,
      actualSourceChars:actualSource?.length,expectedSourceChars:ref.pine_source.length,
      sourceHead:actualSource?.slice(0,80),expectedHead:ref.pine_source.slice(0,80)
    }));
  const state=await page.locator('#publication-python-state').innerText();
  if(!state.includes('미검증')||!state.includes('DDDS'))
    throw Error('UNRELATED_PYTHON_RESULT_WAS_PRESENTED_AS_DDDS '+state);
  const originalUrl=await page.locator('#publication-open-original').getAttribute('href');
  if(!originalUrl.includes('/script/LkgKT3TG-'))
    throw Error('OFFICIAL_PUBLISHED_STRATEGY_LINK_MISSING');
  if(errors.length)throw Error('BROWSER_JS_ERRORS '+errors.join(';'));
  if(out){
    fs.mkdirSync(out,{recursive:true});
    await panel.screenshot({path:out+'/original-wf02-ddds-published-reference.png',timeout:35000});
    fs.writeFileSync(out+'/ddds-reference-validation.json',JSON.stringify({
       strategy_title:ref.strategy_title,chart_id:ref.chart_id,source_id:ref.source_id,
       source_sha256:ref.source_sha256,source_line_count:ref.source_line_count,
       report_key_facts:ref.report_key_facts,
       rights:ref.source_rights,
       official_trades_available:ref.strategy_orders_extracted,
       parity_verified:ref.tradingview_pynecore_strategy_parity_verified,
       python_execution_complete:ref.python_execution_complete,originalUrl,
       errors
    },null,2));
  }
  console.log('WF02_REAL_PUBLISHED_DDDS_REFERENCE_CHROMIUM_PASS',JSON.stringify({
    title:ref.strategy_title,source_lines:ref.source_line_count,
    report:ref.report_key_facts,parity:ref.tradingview_pynecore_strategy_parity_verified
  }));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
