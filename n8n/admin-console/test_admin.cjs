const { chromium } = require('playwright');
const BASE=process.env.ADMIN_TEST_BASE||'https://investment-n8n-native-editor-production.up.railway.app';
const FLOW='operations/WF02-pine-to-python.json';
async function nav(page,url){
 for(let attempt=0;attempt<8;attempt++){
   try{const r=await page.goto(url,{waitUntil:'domcontentloaded',timeout:30000});
     if(r?.status()===200)return;
   }catch(e){if(attempt===7)throw e}
   await page.waitForTimeout(1700);
 }
 throw Error('ADMIN_PAGE_HTTP_NOT_200');
}
async function submitFlow(page){
 await page.locator('#run').click();
 await page.waitForFunction(()=>document.querySelector('#run')&&!document.querySelector('#run').disabled,
    null,{timeout:150000});
 return page.locator('#run-log').innerText();
}
async function fetchJSON(page,url){
 const r=await page.request.get(BASE+url,{timeout:25000});
 if(!r.ok())throw Error('API '+url+' HTTP '+r.status());
 return r.json();
}
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
 const context=await browser.newContext({viewport:{width:1470,height:940}});
 const page=await context.newPage();const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await nav(page,BASE+'/admin/index.html?section=tests');
 await page.locator('#node-list .step').first().waitFor({timeout:45000});
 if(await page.locator('a[href="https://investment-pine-parity-review-production.up.railway.app/demo"]').count()!==1)
  throw Error('ADMIN_REAL_PYNECORE_TEST_LINK_MISSING');
 const steps=await page.locator('#node-list .step').count();
 if(steps<10)throw Error('WF01_STRATEGY_GRAPH_MISSING '+steps);
 let logs=await submitFlow(page);
 if(!logs.includes('01 전략 1개 수집 시작 · HTTP 200 · SUCCESS')||
    !logs.includes('02 전략 최신 목록 1페이지 설정 · HTTP 200 · SUCCESS'))
   throw Error('WF01_REAL_N01_N02_NOT_CHAINED '+logs.slice(0,800));
 console.log('PASS WF01 actual N01→N02');
 await page.locator('[data-flow="operations/WF01-latest-library-one.json"]').first().click();
 await page.locator('#library-pine').waitFor({timeout:30000});
 await page.locator('#run').click();
 const warning=await page.locator('#progress').innerText();
 if(!warning.includes('URL·버전·Pine 원본'))throw Error('No-library-source must be blocked');
 console.log('PASS Library no source returns actual blocker, not fabricated import');
 await page.locator('[data-flow="'+FLOW+'"]').first().click();
 await page.locator('#node-list .step').first().waitFor({timeout:30000});
 if(await page.locator('#node-list .step').count()!==6)
   throw Error('WF02_NOT_SIX_PYNECOMP_NODES');
 await page.locator('#wf02-source-id').fill('PUB;67a1548c0960450086a19d5b0ef1d467');
 await page.locator('#wf02-version').fill('1.0');
 logs=await submitFlow(page);
 for(const label of ['01 DB의 정확한 Pine 원본·버전 로드',
    '02 import Library 재귀 탐색·버전 고정',
    '03 미변환 Library PyneComp 변환·캐시',
    '04 메인 Pine 전체 PyneComp→PyneCore 변환',
    '05 PyneCore 확인·미검증 산출물 DB 저장',
    '06 변환 성공·차단 사유 확인']){
   if(!logs.includes(label.replace(/^\d\d /,'')+' · HTTP 200 · SUCCESS'))
     throw Error('SIX_NODE_REAL_EXECUTION_MISSING '+label+' '+logs.slice(0,2100));
 }
 const details=await page.locator('#node-details').innerText();
 if(!['PYNECOMP_API_KEY_MISSING','WF02_SOURCE_RIGHTS_NOT_APPROVED'].some(code=>details.includes(code)))
   throw Error('NO_KEY_WAS_NOT_REPORTED_IN_FINAL_NODE');
 if(details.includes('PINE_V6_RSI_REVERSAL_RUN_SIGNAL')||
    details.includes('"status": "PYTHON_GENERATED"'))
   throw Error('LEGACY_RSI_CONVERTER_MASQUERADING_AS_PYNECOMP');
 console.log('PASS WF02 SIX real Python nodes; external compiler safely blocked without PYNESYS_API_KEY');
 const sources=await fetchJSON(page,'/api/investment/sources');
 if(!sources.sources?.length||sources.pynecomp?.api_key_configured!==false)
   throw Error('SOURCE_DB_OR_API_KEY_CONFIGURATION_MISMATCH '+JSON.stringify(sources.pynecomp));
 const example=sources.sources.find(x=>x.source_id==='PUB;67a1548c0960450086a19d5b0ef1d467');
 if(!example||!example.legacy_python_code_stored||example.pynecomp_generated_stored)
   throw Error('OLD_GENERATED_PYTHON_WAS_NOT_DISTINGUISHED_FROM_PYNECOMP '+JSON.stringify(example));
 console.log('PASS old limited code is labelled LEGACY; zero forged PyneComp output');
 const before=await fetchJSON(page,'/api/investment/pipeline');
 await page.locator('#integrated-start').click();
 await page.waitForFunction((previous)=>{
   const label=document.querySelector('#integrated-label')?.textContent||'';
   const m=label.match(/실행 ID ([0-9a-f]{32})/);
   return m&&m[1]!==previous&&/PARTIAL_BLOCKED|FAILED|실행.*실패/.test(label);
 },before.run_id||'',{timeout:240000});
 const pipe=await fetchJSON(page,'/api/investment/pipeline');
 if(pipe.status!=='PARTIAL_BLOCKED'||
    !['BLOCKED_PYNECOMP_API_KEY_MISSING','BLOCKED_WF02_SOURCE_RIGHTS_NOT_APPROVED'].includes(pipe.result?.stages?.python)||
    pipe.result?.stages?.chart!=='BLOCKED_PYNECOMP_CONVERSION_NOT_READY')
   throw Error('AUTO_PIPELINE_FAKED_PYNECORE_COMPILATION '+JSON.stringify(pipe.result?.stages));
 if(!pipe.result?.selected_source?.source_id||
    pipe.canonical_postgres?.source_id!==pipe.result.selected_source.source_id||
    pipe.canonical_postgres?.status!==pipe.status)
   throw Error('CANONICAL_AUTO_PIPELINE_SOURCE_OR_STATUS_MISMATCH');
 if(await page.locator('#native-compare-target iframe').count())
   throw Error('Legacy Quant RSI chart used as if generated by PyneComp/PyneCore');
 const statusText=await page.locator('#pynecomp-runtime-status').innerText();
 if(!statusText.includes('PYNESYS_API_KEY 미설정'))
   throw Error('Admin UI hides missing PyneComp credentials '+statusText);
 await page.screenshot({path:'/tmp/investment-4stage-default.png',fullPage:true});
 console.log('PASS full AUTO four-stage pipeline blocks correctly instead of asserting fake PyneCore or TV parity',
  JSON.stringify({run_id:pipe.run_id,status:pipe.status,stages:pipe.result.stages,
                  source:pipe.result.selected_source}));
 const selector=page.locator('#integrated-source');
 const index=sources.sources.findIndex(x=>x.source_id===example.source_id);
 if(index<0)throw Error('PINNED_SOURCE_NOT_FOUND');
 await selector.selectOption(String(index));
 await page.locator('#integrated-start').click();
 await page.waitForFunction((previous)=>{
   const label=document.querySelector('#integrated-label')?.textContent||'';
   const m=label.match(/실행 ID ([0-9a-f]{32})/);
   return m&&m[1]!==previous&&/PARTIAL_BLOCKED|FAILED|실행.*실패/.test(label);
 },pipe.run_id,{timeout:240000});
 const exact=await fetchJSON(page,'/api/investment/pipeline');
 if(exact.result?.stages?.strategy!=='REUSED_EXACT_DB_SOURCE'||
    exact.result?.selected_source?.source_id!==example.source_id||
    exact.result?.selected_source?.version_key!==example.version_key||
    !['BLOCKED_PYNECOMP_API_KEY_MISSING','BLOCKED_WF02_SOURCE_RIGHTS_NOT_APPROVED'].includes(exact.result?.stages?.python))
   throw Error('PINNED_SOURCE_CHANGED_OR_FALLBACK_CONVERTED '+JSON.stringify(exact.result));
 if(await page.locator('#native-compare-target iframe').count())
   throw Error('Pinned strategy shows pre-PyneComp Quant result as PyneCore output');
 await page.screenshot({path:'/tmp/investment-4stage-pinned.png',fullPage:true});
 console.log('PASS pinned source preserved and no fake PyneCore graph',JSON.stringify({
   run_id:exact.run_id,source:exact.result.selected_source,stages:exact.result.stages}));
 if(errors.length)throw Error('Browser JS exception '+JSON.stringify(errors));
 console.log('LIVE_ADMIN_ROUTE_OK');
 }finally{await browser.close()}
})().catch(e=>{console.error('BROWSER_ERROR',e);process.exit(1)});
