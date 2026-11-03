/* Genuine Chromium user acceptance in the ORIGINAL WF02 management center.
 * The code and authorization are real; no mocked compiler or fake Pine output.
 */
const {chromium}=require('playwright');
const fs=require('fs');
const target=process.env.WF02_EDITOR_BASE||
 'https://investment-n8n-native-editor-production.up.railway.app';
const dir=process.env.WF02_EVIDENCE_DIR||'/tmp/ddds-node-evidence';
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
 try{
  const page=await browser.newPage({viewport:{width:1510,height:1050},locale:'ko-KR'});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const response=await page.goto(target+'/admin/index.html?section=convert',
    {waitUntil:'domcontentloaded',timeout:45000});
  if(response?.status()!==200)throw Error('WF02_PAGE_HTTP_'+response?.status());
  await page.locator('#ddds-wf02-run').waitFor({timeout:35000});
  await page.waitForFunction(()=>document.querySelector('#tv-publication-status')?.
    textContent?.includes('원본 확인'),null,{timeout:22000});
  const source=await (await page.request.get(target+'/api/investment/tv-publication/latest')).json();
  if(source.source_sha256!=='5a245e99447f13012dd026528235fc2c299cad5cb7b228653c684886dcba6507')
    throw Error('CHOSEN_DDDS_SHA_MISMATCH');
  await page.locator('#ddds-mpl-ack').check();
  await page.locator('#ddds-wf02-run').click();
  await page.waitForFunction(()=>{
    const t=document.querySelector('#ddds-register-state')?.textContent||'';
    return t.includes('DDDS 원본 고정')||t.includes('DDDS 실제 노드 연결 실패');
  },null,{timeout:110000});
  const label=await page.locator('#ddds-register-state').innerText();
  if(!label.includes('DDDS 원본 고정'))
    throw Error('DDDS_SOURCE_NODE_REGISTRATION_FAILED '+label);
  const sourceId=await page.locator('#wf02-source-id').inputValue();
  const version=await page.locator('#wf02-version').inputValue();
  if(sourceId!=='PUB;5442675d418140c58486eb4a7ae12768'||
     version!=='snapshot-sha256-'+source.source_sha256.slice(0,16))
    throw Error('WF02_RUN_DID_NOT_SELECT_EXACT_DDDS '+sourceId+' / '+version);
  const progress=await page.locator('#progress').innerText();
  const log=await page.locator('#run-log').innerText();
  const details=await page.locator('#node-details').innerText();
  if(!log.includes('wf02')&&!log.includes('Pine'))
    throw Error('NOT_ACTUAL_WF02_NODE_GRAPH '+log.slice(0,700));
  const blocked=(progress+' '+log+' '+details);
  if(!blocked.includes('PYNECOMP_API_KEY_MISSING')&&!blocked.includes('PYNESYS_API_KEY'))
    throw Error('MISSING_REAL_COMPILER_GATE_NOT_SHOWN '+blocked.slice(0,1200));
  if((blocked.includes('PYNECOMP_GENERATED_UNVALIDATED')||
      blocked.includes('conversion_validated": true')||
      blocked.includes('live_orders_enabled": true')))
    throw Error('WRONG_COMPLETION_OR_LIVE_TRADING_CLAIM');
  const steps=await page.locator('#node-list .step').count();
  if(steps!==6)throw Error('ORIGINAL_6_NODES_NOT_PRESERVED');
  if(errors.length)throw Error('BROWSER_PAGE_ERRORS '+errors.join(';'));
  const data={
    status:'ORIGINAL_WF02_ACTUAL_DDDS_SOURCE_NODES_PASSED',
    sourceId,version,pinnedSha:source.source_sha256,
    steps,realCompilerApiKeyConfigured:false,
    fullPineCompilationVerified:false,tradingviewParityVerified:false,
    strategyOrdersAvailable:false,liveTradingEnabled:false,
    progress,log,details,errors,observedAt:new Date().toISOString()
  };
  fs.mkdirSync(dir,{recursive:true});
  fs.writeFileSync(dir+'/wf02-ddds-real-node-result.json',JSON.stringify(data,null,2));
  await page.locator('#published-strategy-reference').screenshot({
    path:dir+'/wf02-ddds-registered-publication.png',timeout:25000});
  await page.locator('#flow-panel').screenshot({
    path:dir+'/wf02-ddds-node-execution.png',timeout:25000}).catch(async()=>{
    await page.screenshot({path:dir+'/wf02-ddds-node-execution.png',fullPage:true});
  });
  console.log('WF02_DDDS_REAL_NODE_BROWSER_PASS',JSON.stringify({
    sourceId,version,steps,compilerBlocked:true,progress,parityVerified:false
  }));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
