import {test,expect} from '@playwright/test';
import fs from 'node:fs';
const kinds=['stock','etf','bond'] as const;
const expected:Record<string,string>={stock:'주식 스크리너',etf:'ETF 스크리너',bond:'본드 스크리너'};
test.beforeEach(async({page})=>{await page.setViewportSize({width:1440,height:900})});
for(const kind of kinds){
 test(kind+' first screen real API & UI interactions',async({page})=>{
  const requests:Array<{url:string,status:number}>=[];
  page.on('response',r=>{if(r.url().includes('/screener-data/'))requests.push({url:r.url(),status:r.status()})});
  await page.goto('/?screener='+kind,{waitUntil:'networkidle'});
  await expect(page.getByTestId('screener-app')).toBeVisible();
  await expect(page.getByRole('heading',{name:expected[kind]})).toBeVisible();
  await expect(page.locator('.sc-table thead th').first()).toBeVisible();
  await expect(page.locator('.sc-count')).toContainText('매칭',{timeout:30000});
  await expect(page.locator('.sc-table tbody tr').first()).toBeVisible();
  expect(requests.some(r=>r.status===200&&r.url.includes('/scan?')),'live scan HTTP 200').toBe(true);
  await page.screenshot({path:'comparison/screens/'+kind+'-clone-1440.png',fullPage:true});
  await page.getByTestId('columns-setup').click();
  await expect(page.getByText('컬럼 셋업')).toBeVisible();
  await page.getByTestId('columns-setup').click();
  await page.getByTestId('refresh-screener').click();
  await expect(page.locator('.sc-count')).toContainText('매칭',{timeout:30000});
  const clickSort=page.locator('.sc-table thead th').nth(2).locator('button');
  await clickSort.click();await expect(page.locator('.sc-count')).toContainText('매칭',{timeout:30000});
  await page.getByTestId('watchlist-filter').click();
  await expect(page.getByText('내 왓치리스트만')).toBeVisible();
  await page.getByTestId('watchlist-filter').click();
  await page.getByTestId('reset-filters').click();
  await expect(page.locator('.sc-table thead th').first()).toBeVisible();
 });
}
test('market switch Korea, Japan and US ETF live scan',async({page})=>{
 await page.goto('/?screener=stock',{waitUntil:'networkidle'});
 await page.getByTestId('market-filter').click();
 await page.getByTestId('market-japan').click();
 await expect(page.getByTestId('market-filter')).toContainText('일본');
 await expect(page.locator('.sc-count')).toContainText('매칭',{timeout:30000});
 await page.getByRole('button',{name:'ETF',exact:true}).first().click();
 await expect(page.getByRole('heading',{name:'ETF 스크리너'})).toBeVisible();
 await page.getByTestId('market-filter').click();
 await page.getByTestId('market-america').click();
 await expect(page.getByTestId('market-filter')).toContainText('미국');
 await expect(page.locator('.sc-count')).toContainText('매칭',{timeout:30000});
});
test('filter changes query body, back/forward and pagination',async({page})=>{
 const calls:any[]=[];
 page.on('request',r=>{if(r.url().includes('/screener-data/')&&r.method()==='POST'){try{calls.push(JSON.parse(r.postData()||'{}'))}catch{}}});
 await page.goto('/?screener=stock',{waitUntil:'networkidle'});
 await page.getByTestId('filter-close').click();
 await page.getByRole('spinbutton',{name:'가격 최소'}).fill('100');
 await page.getByRole('button',{name:'적용'}).click();
 await expect.poll(()=>calls.some(c=>(c.filter||[]).some((f:any)=>f.left==='close')),{timeout:30000}).toBe(true);
 await page.getByTitle('실행 취소').click();
 await expect.poll(()=>calls.at(-1).filter.length,{timeout:30000}).toBe(0);
 await page.getByTestId('next-page').click();
 await expect.poll(()=>calls.at(-1).range[0],{timeout:30000}).toBe(50);
});
test('capture official original screener layouts and DOM controls',async({browser})=>{
 const original=await browser.newContext({viewport:{width:1440,height:900},locale:'ko-KR'});
 const page=await original.newPage();
 const captures=[] as any[];
 for(const [kind,url] of [['stock','https://kr.tradingview.com/stock-screener/'],['etf','https://kr.tradingview.com/etf-screener/'],['bond','https://kr.tradingview.com/bond-screener/']] as const){
  try{
   const response=await page.goto(url,{waitUntil:'domcontentloaded',timeout:45000});
   await page.waitForTimeout(6000);
   const title=await page.title();
   const headings=await page.locator('h1').allTextContents();
   const tabLabels=await page.locator('[role=tab]').allTextContents();
   const filterLabels=await page.locator('[data-qa-id*="filter-pill"],[data-qa-id*="condition-pill"],[data-qa-id*="date-pill"]').allTextContents();
   const headerLabels=await page.locator('thead th').allTextContents();
   await page.screenshot({path:'comparison/screens/'+kind+'-original-1440.png',fullPage:true});
   captures.push({kind,url,status:response?.status(),title,headings,tabLabels,filterLabels,headerLabels});
  }catch(e){captures.push({kind,url,error:String(e)})}
 }
 fs.writeFileSync('comparison/original-controls.json',JSON.stringify(captures,null,2));
 console.log('original captured',JSON.stringify(captures.map(x=>({kind:x.kind,status:x.status,headings:x.headings?.slice(0,2),tabs:x.tabLabels?.length,filters:x.filterLabels?.length,columns:x.headerLabels?.length,error:x.error}))));
 await original.close();
});
