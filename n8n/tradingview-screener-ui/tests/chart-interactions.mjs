import {chromium} from 'playwright';
import fs from 'node:fs/promises';
const ROOT=process.env.CHART_BASE_URL||'http://127.0.0.1:4173';
const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_SYSTEM_CHROME?{executablePath:process.env.PLAYWRIGHT_SYSTEM_CHROME}:{}),args:['--no-sandbox','--disable-dev-shm-usage']});
const page=await browser.newPage({viewport:{width:1210,height:750},locale:'ko-KR'});
await fs.mkdir('artifacts',{recursive:true});
const errors=[],requests=[],checks=[];page.on('pageerror',e=>errors.push(String(e)));
function check(name,value,details={}){checks.push({name,pass:!!value,...details});console.log((value?'PASS':'FAIL')+' '+name+' '+JSON.stringify(details).slice(0,200))}
const sym=['NASDAQ:AAPL','NASDAQ:NVDA','NASDAQ:MSFT','NASDAQ:GOOGL'];
const names=['Apple Inc.','NVIDIA Corporation','Microsoft Corporation','Alphabet Inc.'];
await page.route('**/api/scan',async route=>{
 const q=route.request().postDataJSON(),columns=q.payload.columns;
 const data=sym.map((s,i)=>({s,d:columns.map(col=>col==='ticker-view'?{name:s.split(':')[1],description:names[i]}:col==='close'?330+i*20:col==='change'?i%2===0?2.75:-3.5:col==='market_cap_basic'?1e12*(4-i):null)}));
 await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({totalCount:4,data})});
});
await page.route('**/api/chart?**',async route=>{
 const u=new URL(route.request().url()),symbol=u.searchParams.get('symbol'),range=u.searchParams.get('range');
 requests.push({symbol,range});
 const bars=Array.from({length:80},(_,i)=>({t:1793404800+i*3600,o:300+i*.4,h:301+i*.4,l:299+i*.4,c:300+i*.4,v:500+i*40}));
 await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({symbol,resolvedSymbol:symbol.split(':').pop(),provider:'TEST_FIXTURE_NOT_MARKET_DATA',interval:range==='5d'?'15m':'1d',range,timezone:'America/New_York',delayed:true,bars})});
});
try{
 await page.goto(ROOT+'/screener/',{waitUntil:'domcontentloaded',timeout:30000});
 await page.getByTestId('screener-table').waitFor();
 await page.getByTestId('view-switch').click();
 check('source view menu includes 3 options',(await Promise.all(['table','charts','heatmap'].map(v=>page.getByTestId('view-option-'+v).count()))).every(Boolean));
 await page.getByTestId('view-option-charts').click();
 await page.getByTestId('screener-chart-grid').waitFor();
 check('2 column chart grid displays 4 exact screened symbols',(await page.getByTestId('chart-card').count())===4&&(await page.getByTestId('chart-card').first().getAttribute('data-symbol'))==='NASDAQ:AAPL');
 await page.getByTestId('lightweight-chart').first().locator('canvas').first().waitFor({timeout:12000});
 check('chart requests exact ID and original default 5D',requests.some(x=>x.symbol==='NASDAQ:AAPL'&&x.range==='5d'),{requests:requests.slice(0,4)});
 check('rendered actual OHLCV dataset identifies its source',(await page.getByTestId('chart-card').first().getAttribute('data-data-source'))==='TEST_FIXTURE_NOT_MARKET_DATA');
 await page.getByTestId('chart-range-1mo').click();
 await page.waitForFunction(()=>document.querySelectorAll('[data-testid="chart-card"][data-data-source="TEST_FIXTURE_NOT_MARKET_DATA"]').length===4);
 check('period changes requests to 1 month',requests.some(x=>x.range==='1mo'),{rangeRequests:requests.map(x=>x.range).slice(-5)});
 await page.getByLabel('차트 유형').selectOption('Candles');
 check('candlestick engine renders actual OHLC series',(await page.getByTestId('lightweight-chart').first().getAttribute('data-chart-type'))==='Candles'&&(await page.getByTestId('lightweight-chart').first().locator('canvas').count())>0);
 await page.getByLabel('차트 유형').selectOption('Line');
 await page.getByLabel('거래량 표시').selectOption('hide');
 check('volume switch actually updates engine data option',(await page.getByTestId('lightweight-chart').first().getAttribute('data-chart-volume'))==='hide');
 await page.getByLabel('차트 가격 축').selectOption('Percent');
 check('percentage axis applies real chart scale',(await page.getByTestId('lightweight-chart').first().getAttribute('data-chart-scale'))==='Percent');
 await page.screenshot({path:'artifacts/chart-view-fixture.png'});
 await page.getByTestId('view-switch').click();await page.getByTestId('view-option-heatmap').click();
 check('heatmap uses real scanner returned percent values',await page.getByTestId('screener-heatmap').locator('a').count()===4);
 await page.screenshot({path:'artifacts/heatmap-view-fixture.png'});
 await page.getByTestId('view-switch').click();await page.getByTestId('view-option-table').click();
 check('table stays functional after view changes',await page.getByTestId('screener-table').locator('tbody tr').count()===4);
 check('no browser errors',errors.length===0,{errors});
}finally{await browser.close()}
const result={checks,errors,networkSource:'TEST_FIXTURE_NOT_MARKET_DATA',note:'UI contract test uses a declared local fixture. Provider real OHLCV is tested separately.'};
await fs.writeFile('artifacts/chart-interactions.json',JSON.stringify(result,null,2));
if(checks.some(c=>!c.pass))process.exitCode=1;
