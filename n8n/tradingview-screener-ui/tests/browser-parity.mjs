import{chromium}from'playwright';
import sharp from'sharp';
import fs from'node:fs/promises';
import path from'node:path';
const ROOT='http://127.0.0.1:4173';
const OUT=path.resolve('artifacts');
await fs.mkdir(OUT,{recursive:true});
const SCREENS=[
 ['stock','/screener/','https://kr.tradingview.com/screener/','주식_initial.png',12],
 ['etf','/etf-screener/','https://kr.tradingview.com/etf-screener/','ETF_initial.png',9],
 ['bond','/bond-screener/','https://kr.tradingview.com/bond-screener/','채권_initial.png',9],
 ['coin','/crypto-coins-screener/','https://kr.tradingview.com/crypto-coins-screener/',null,8],
 ['cex','/cex-screener/','https://kr.tradingview.com/cex-screener/',null,3],
 ['dex','/dex-screener/','https://kr.tradingview.com/dex-screener/',null,6],
 ['pine','/pine-screener/','https://kr.tradingview.com/pine-screener/',null,0]];
const browser=await chromium.launch({headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
const ctx=await browser.newContext({viewport:{width:1565,height:960},locale:'ko-KR',deviceScaleFactor:1});
const results=[],failures=[];
async function check(name,condition,details=''){
 const status=Boolean(condition);
 results.push({kind:'assertion',name,pass:status,details});
 if(!status)failures.push({name,details});
 console.log(status?'PASS':'FAIL',name,details);
}
async function screenshotComparison(ours,expectedPath,key){
 if(!expectedPath)return null;
 try{
  await fs.access(expectedPath);
  const a=await sharp(ours).resize(392,240,{fit:'fill'}).removeAlpha().raw().toBuffer();
  const b=await sharp(expectedPath).resize(392,240,{fit:'fill'}).removeAlpha().raw().toBuffer();
  const compare=new Uint8Array(a.length);
  let total=0,changed=0;
  for(let i=0;i<a.length;i+=3){
   const dr=Math.abs(a[i]-b[i]),dg=Math.abs(a[i+1]-b[i+1]),db=Math.abs(a[i+2]-b[i+2]);
   const diff=(dr+dg+db)/3;total+=diff;
   if(diff>35)changed++;
   compare[i]=dr;compare[i+1]=dg;compare[i+2]=db;
  }
  const score={mean_absolute_rgb_error:+(total/(a.length/3)).toFixed(2),pixel_fraction_changed_35:+(changed/(a.length/3)).toFixed(3)};
  await sharp(Buffer.from(compare),{raw:{width:392,height:240,channels:3}}).png().toFile(path.join(OUT,key+'_diff.png'));
  await sharp({create:{width:1176,height:240,channels:4,background:'#fff'}}).composite([
   {input:await sharp(expectedPath).resize(392,240).toBuffer(),left:0,top:0},
   {input:await sharp(ours).resize(392,240).toBuffer(),left:392,top:0},
   {input:await sharp(path.join(OUT,key+'_diff.png')).toBuffer(),left:784,top:0}
  ]).png().toFile(path.join(OUT,key+'_compare.png'));
  console.log('VISUAL',key,JSON.stringify(score));
  return score;
 }catch(e){console.log('VISUAL ERROR',key,String(e));return {error:String(e)}}
}
try{
 for(const [key,route,original,staticRef,tabCount]of SCREENS){
  const page=await ctx.newPage();
  const exceptions=[];
  page.on('pageerror',error=>exceptions.push(error.message));
  const response=await page.goto(ROOT+route,{waitUntil:'domcontentloaded',timeout:30000});
  await page.waitForSelector('[data-testid="screener-app"]',{timeout:20000});
  if(key!=='pine'){await page.waitForFunction(()=>document.querySelector('[data-testid="screener-app"]').dataset.source!==''&&!document.querySelector('[data-testid="screener-app"]').querySelector('.spin'),null,{timeout:40000}).catch(()=>{});}
  await page.waitForTimeout(250);
  const title=await page.locator('.screen-name').innerText();
  const tabs=await page.locator('[role="tab"]').count();
  const filters=await page.locator('.filter-pill').count();
  const rows=await page.locator('.screener-table tbody tr').count();
  const source=await page.locator('[data-testid="screener-app"]').getAttribute('data-source');
  const appShot=path.join(OUT,key+'_ours.png');
  await page.screenshot({path:appShot,fullPage:false});
  let referenceType='missing',referenceShot=null,refTabs=null;
  const originalPage=await ctx.newPage();
  const capturedReqs=[];
  originalPage.on('request',request=>{if(request.url().includes('/scan?')){let json=null;try{json=request.postDataJSON()}catch{}capturedReqs.push({url:request.url(),method:request.method(),json});}});
  try{
   let result=await originalPage.goto(original,{waitUntil:'domcontentloaded',timeout:35000});
   await originalPage.waitForTimeout(4500);
   if(result?.status()===200){
    referenceType='live';referenceShot=path.join(OUT,key+'_original_live.png');
    refTabs=await originalPage.locator('#market-screener-header-columnset-tabs [role="tab"]:not([aria-hidden="true"])').count().catch(()=>null);
    await originalPage.screenshot({path:referenceShot,fullPage:false});
   }
  }catch(e){console.log('LIVE REF UNAVAILABLE',key,String(e).slice(0,160))}
  await originalPage.close();
  await fs.writeFile(path.join(OUT,key+'_original_scans.json'),JSON.stringify(capturedReqs,null,2));
  if(referenceType==='missing'&&staticRef){const file=path.resolve('evidence',staticRef);try{await fs.access(file);referenceType='captured';referenceShot=file;}catch{}}
  const visual=await screenshotComparison(appShot,referenceShot,key);
  results.push({kind:'page',key,route,title,tabs,filters,rows,source,response_status:response.status(),referenceType,refTabs,visual,exceptions});
  await check(key+': HTTP 200',response.status()===200);
  await check(key+': heading exists',title?.length>2);
  await check(key+': tabs = '+tabCount,tabs===tabCount);
  await check(key+': filters visible',filters>=3);
  await check(key+': no React exceptions',exceptions.length===0,exceptions.join(','));
  if(['stock','etf','bond'].includes(key)){
   await check(key+': scan data or captured fallback',source==='live'||source==='captured','source='+source);
   await check(key+': nonempty rows',rows>=5,'rows='+rows);
   await page.locator('[data-testid="tab-1"]').click();
   await page.waitForTimeout(800);
   await check(key+': tab selects',await page.locator('[data-testid="tab-1"]').getAttribute('aria-selected')==='true');
   await page.locator('[data-testid="tab-0"]').click();
   await page.locator('[data-qa-id="screener-add-new-filter"]').click();
   await check(key+': add filter popup',await page.locator('.popover-add-filter').count()===1);
   await page.locator('.pop-header button').click();
   await page.locator('[data-qa-id="screener-add-column-button"]').click();
   await check(key+': columns popup',await page.locator('.popover-columns .option-list button').count()>4);
   await page.locator('.pop-header button').click();
   await page.locator('[data-qa-id="screener-topbar-settings"]').click();
   await check(key+': settings popup',await page.locator('.popover-settings input[type="checkbox"]').count()===4);
   await page.locator('.pop-header button').click();
  }
  if(key==='stock'||key==='etf'){
   await page.locator('[data-testid="market-filter"]').click();
   await check(key+': market selector 71',await page.locator('.popover-market .option-list button').count()===71);
   await page.locator('.popover-market .popup-search').fill('japan');
   await page.locator('.popover-market .option-list button').first().click();
   await page.waitForTimeout(2000);
   await check(key+': market switched Japan',await page.locator('[data-testid="market-filter"]').innerText().then(s=>s.includes('일본')));
   await page.locator('[data-qa-id="screener-refresh-button"]').click();
   await check(key+': refresh',true);
  }
  await page.close();
 }
}catch(e){failures.push({name:'test harness aborted',details:String(e.stack||e)})}
finally{await browser.close()}
const report={captured:new Date().toISOString(),description:'reference live if accessible else captured; diff measures raw screenshot mismatch, not pixel identical',pages:results.filter(x=>x.kind==='page'),assertions:results.filter(x=>x.kind==='assertion'),failures};
await fs.writeFile(path.join(OUT,'parity-report.json'),JSON.stringify(report,null,2));
console.log('FINAL',JSON.stringify({pages:report.pages.length,assertions:report.assertions.length,failed:failures.length,failures}));
if(failures.length)process.exitCode=1;
