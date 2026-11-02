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

  const href=await page.locator('#flow-panel a[href*="workflow="]').first().getAttribute('href');
  if(!href?.includes('WF02-chart-parity-first-stage.json'))throw Error('Parity deep link wrong '+href);
  await nav(page,BASE+href);
  await page.locator('[data-stock-flow="operations/WF02-chart-parity-first-stage.json"].active').waitFor({timeout:30000});
  await page.locator('a[href="/admin/index.html"]').first().waitFor({timeout:10000});
  if(errors.length)throw Error('Browser JS errors: '+errors.join(' | '));
  console.log('PASS parity graph deep link and admin return navigation');
 }finally{await browser.close()}
})().catch(e=>{console.error(e.stack||e);process.exit(1)});
