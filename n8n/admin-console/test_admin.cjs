const { chromium } = require('playwright');
const BASE=process.env.ADMIN_TEST_BASE||'https://investment-n8n-native-editor-production.up.railway.app';
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:900}});
  page.on('pageerror',e=>console.error('BROWSER_ERROR',e.message));
  const response=await page.goto(BASE+'/admin/index.html',{waitUntil:'domcontentloaded',timeout:30000});
  if(response.status()!==200)throw Error('Admin HTTP '+response.status());
  await page.getByText('AUTONOMOUS INVESTOR').first().waitFor();
  await page.getByRole('button',{name:/통합 테스트센터/}).first().click();
  await page.locator('#node-list .step').first().waitFor({timeout:30000});
  const nodes=await page.locator('#node-list .step').count();
  if(nodes<10)throw Error('Actual WF01 graph missing: '+nodes+' nodes');
  const href=await page.locator('#flow-panel a[href*="workflow="]').first().getAttribute('href');
  if(!href||!href.includes('WF01-latest-strategy-one.json'))throw Error('Workflow deep link missing');
  await page.locator('#node-list .step').first().click();
  await page.locator('#node-details').waitFor();
  const run=page.locator('#run');
  await run.click();
  await page.waitForFunction(()=>document.querySelector('#run-log')?.textContent?.includes('01 전략 1개 수집 시작'),{timeout:30000});
  await page.waitForFunction(()=>!document.querySelector('#run')?.disabled,{timeout:120000});
  const logs=await page.locator('#run-log').innerText();
  if(!logs.includes('HTTP 200')||!logs.includes('SUCCESS'))throw Error('No real successful N01 execution: '+logs.slice(0,3500));
  if(!logs.includes('02 전략 최신 목록 1페이지 설정'))throw Error('N01 output was not transferred to N02: '+logs.slice(0,3500));
  const detail=await page.locator('#node-details').innerText();
  if(!detail.includes('JSON'))throw Error('Node inspector not showing JSON');
  console.log('PASS Admin opened; actual nodes',nodes,'; live N01→N02 recorded; inspector rendered; href',href);
  console.log('RUN TRACE',logs.slice(0,2000).replace(/\n/g,' | '));
  const editor=await page.goto(BASE+href,{waitUntil:'domcontentloaded',timeout:30000});
  if(editor.status()!==200)throw Error('Editor HTTP '+editor.status());
  await page.locator('[data-stock-flow="operations/WF01-latest-strategy-one.json"].active').waitFor({timeout:30000});
  await page.locator('a[href="/admin/index.html"]').first().waitFor({timeout:10000});
  console.log('PASS editor deep-link selects matching workflow and has return navigation');
 }finally{await browser.close()}
})().catch(e=>{console.error(e.stack||e);process.exit(1)});
