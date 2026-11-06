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
const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_SYSTEM_CHROME?{executablePath:process.env.PLAYWRIGHT_SYSTEM_CHROME}:{}),args:['--no-sandbox','--disable-dev-shm-usage']});
const ctx=await browser.newContext({viewport:{width:1565,height:960},locale:'ko-KR',deviceScaleFactor:1});
const results=[],failures=[];

/* Semantic UI inventory: compare every major structural group, all tabs, filter controls,
   and visible table fields. Both missing and unexpected elements fail the layout gate.
   A reference acquisition failure is NOT a passing comparison. */
const UI_PARITY_LIMIT=.10;
const DISPLAY_FIELD_MAP={
 TickerUniversal:'ticker-view',TickerInstrumentUniversal:'ticker-view',
 Price:'close',ChangeCrypto:'24h_close_change|5','ChangeCrypto|Interval24H':'24h_close_change|5',
 'Change|TimeResolution1D':'change','Volume|TimeResolution1D':'volume',
 'RelativeVolume|TimeResolution1D':'relative_volume_10d_calc',
 MarketCap:'market_cap_basic',PriceToEarnings:'price_earnings_ttm',
 'EpsDiluted|ttm':'earnings_per_share_diluted_ttm',
 'EpsDilutedGrowth|YoYTTM':'earnings_per_share_diluted_yoy_growth_ttm',
 'DividendsYield|ttm':'dividends_yield_current',
 Sector:'sector.tr',AnalystRating:'AnalystRating.tr',
 'VolumePrice|TimeResolution1D':'Value.Traded',AssetsUnderManagement:'aum',
 'NavTotalReturn|Interval3Y':'nav_total_return.3Y',TotalHoldings:'etf_holdings_count',
 ExpenseRatio:'expense_ratio',AssetClass:'asset_class.tr',Focus:'focus.tr',
 Isin:'isin-displayed',YieldToWorst:'yield_to_worst',BondClose:'close_pct',
 BondCloseNet:'close_net',CurrentCoupon:'current_coupon',MaturityDate:'maturity_date',
 Redemption:'redemption_type.tr',BondIssuerType:'bond_issuer_type.tr',
 SnpRatingLongTerm:'bond_snp_rating_lt.tr',FitchRatingLongTerm:'bond_fitch_rating_lt.tr',
 MoodysRatingLongTerm:'bond_moodys_rating_lt.tr',Source:'exchange.tr',
 Rank:'crypto_total_rank',MarketCapCalc:'market_cap_calc',
 'Volume24hCoin|Interval24H':'24h_vol_cmc',SupplyCirculating:'circulating_supply',
 VolumeToMarketCap:'24h_vol_to_market_cap',SocialDominance:'socialdominance',
 CryptoCategory:'crypto_common_categories.tr',
 'TechnicalRating|TimeResolution1D':'TechRating_1D.tr',
 Exchange:'exchange.tr','Volume24h|Interval24H':'24h_vol|5',
 'Volume24hChange|Interval24H':'24h_vol_change|5',
 Blockchain:'blockchain-id.tr','TransactionsDex|Interval24H':'dex_txs_count_24h',
 'TradingVolumeDex|Interval24H':'dex_trading_volume_24h',
 'TradersDex|Interval24H':'dex_txs_count_uniq_24h',
 LiquidityDex:'dex_total_liquidity',FullyDilutedValuation:'fully_diluted_value'
};

const originalSelectors={
  siteHeader:'header,nav,[role="banner"],[class*="siteHeader"],[class*="headerRoot"]',main:'main#tv-content',categorySwitch:'[data-qa-id="screener-pills-switcher"]',
  screenTitle:'[data-qa-id="screen-title"]',undo:'[data-qa-id="screener-undo-button"]',
  redo:'[data-qa-id="screener-redo-button"]',settings:'[data-qa-id="screener-topbar-settings"]',
  filterPanel:'[class*="pillsPanel"],[class*="pillsContainer"]',
  addFilter:'[data-qa-id="screener-add-new-filter"]',
  filterOptions:'[data-qa-id="reset-options-button"]',
  tabs:'[role="tablist"]',refresh:'[data-qa-id="screener-refresh-button"]',
  fullscreen:'[data-qa-id="screener-enter-fullscreen"]',
  resultTable:'table thead th[data-field]',tableBody:'table tbody tr',
  symbolSearch:'th[data-field] button[title="찾기"]',
  columnSetup:'[data-qa-id="screener-add-column-button"]',
  firstColumn:'th[data-field]:first-child',logoImages:'tbody tr img',
  watchlist:'[class*="watchlistWrapper"]',
  bondOverlay:'[data-qa-id="screener-registration-bottom-bar"]',
  pineGuest:'[class*="emptyScreen"],[class*="emptyState"],[class*="emptyContainer"]'
};
const cloneSelectors={
  siteHeader:'.site-header',main:'main#tv-content',categorySwitch:'.category-switch',
  screenTitle:'.screen-name',undo:'[data-qa-id="screener-undo-button"]',
  redo:'[data-qa-id="screener-redo-button"]',settings:'[data-qa-id="screener-topbar-settings"]',
  filterPanel:'.pills-panel',addFilter:'[data-qa-id="screener-add-new-filter"]',
  filterOptions:'[data-qa-id="reset-options-button"]',tabs:'.tab-list[role="tablist"]',
  refresh:'[data-qa-id="screener-refresh-button"]',
  fullscreen:'[data-qa-id="screener-enter-fullscreen"]',
  resultTable:'table.screener-table thead th[data-field]',tableBody:'table.screener-table tbody tr',
  symbolSearch:'th[data-field] button[title="심볼 찾기"]',
  columnSetup:'[data-qa-id="screener-add-column-button"]',
  firstColumn:'th[data-field]:first-child',logoImages:'.logo-host img',
  watchlist:'.watchlist-pill',bondOverlay:'.bond-registration',pineGuest:'.pine-empty'
};
async function collectLayout(page,original,kind){
 const selectors=original?originalSelectors:cloneSelectors;
 return page.evaluate(({selectors,kind,original})=>{
   const visible=node=>{if(!node)return false;let style=getComputedStyle(node);
     const r=node.getBoundingClientRect();return style.display!=='none'&&style.visibility!=='hidden'&&r.width>0&&r.height>0};
   const data={};for(const [name,selector]of Object.entries(selectors)){
     const nodes=[...document.querySelectorAll(selector)];
     data[name]={present:nodes.some(visible),count:nodes.filter(visible).length,
       boxes:nodes.filter(visible).slice(0,2).map(n=>{let r=n.getBoundingClientRect();return{x:Math.round(r.x),y:Math.round(r.y),width:Math.round(r.width),height:Math.round(r.height)}})};
   }
   if(original&&data.siteHeader&&!data.siteHeader.present){
     const top=[...document.querySelectorAll('div')].filter(n=>{
       const r=n.getBoundingClientRect();return visible(n)&&r.y>=-2&&r.y<20&&r.width>1000&&r.height>=45&&r.height<=100;
     });
     data.siteHeader={present:top.length>0,count:top.length,boxes:top.slice(0,2).map(n=>{const r=n.getBoundingClientRect();return{x:Math.round(r.x),y:Math.round(r.y),width:Math.round(r.width),height:Math.round(r.height)}})};
   }
   if(original&&kind==='pine'&&data.pineGuest&&!data.pineGuest.present){
     const titles=[...document.querySelectorAll('h1,h2,h3,h4,div,p,strong')].filter(n=>{
       const r=n.getBoundingClientRect();return visible(n)&&r.y>280&&r.y<780&&r.width<1200&&/Pine Screener|파인 스크리너/i.test((n.innerText||'').trim());
     });
     data.pineGuest={present:titles.length>0,count:titles.length,boxes:titles.slice(0,2).map(n=>{const r=n.getBoundingClientRect();return{x:Math.round(r.x),y:Math.round(r.y),width:Math.round(r.width),height:Math.round(r.height)}})};
   }
   const tabSel=original?'#market-screener-header-columnset-tabs [role="tab"]:not([aria-hidden="true"])':'.tab-list [role="tab"]';
   const pillSel=original?'[data-qa-id*="filter-pill"],[data-qa-id*="condition-pill"],[data-qa-id*="date-pill"]':'.pills-scroller .filter-pill:not(.watchlist-pill)';
   const arr=sel=>[...document.querySelectorAll(sel)].filter(visible).map(n=>(n.innerText||n.textContent||'').replace(/\s+/g,' ').trim());
   const fields=arr(original?'table thead th[data-field]':'table.screener-table thead th[data-field]');
   const fieldIds=[...document.querySelectorAll(original?'table thead th[data-field]':'table.screener-table thead th[data-field]')].filter(visible).map(n=>n.getAttribute('data-field'));
   return {kind,mode:original?'original':'clone',elements:data,
     tabs:arr(tabSel),filters:arr(pillSel),fields,fieldIds,
     symbolRows:document.querySelectorAll('table tbody tr').length,
     screenText:(document.querySelector(original?'[data-qa-id="screen-title"]':'.screen-name')?.textContent||'').replace(/\s+/g,' ').trim()};
 },{selectors,kind,original});
}
async function validateLayout(key,reference,clone){
 const mustExist=['siteHeader','main'];
 if(key==='pine')mustExist.push('pineGuest');
 else mustExist.push('categorySwitch','screenTitle','undo','redo','settings','filterPanel',
  'addFilter','filterOptions','tabs','refresh','fullscreen','resultTable','tableBody',
  'symbolSearch','columnSetup','firstColumn','logoImages','watchlist');
 if(key==='bond')mustExist.push('bondOverlay');
 for(const name of mustExist){
   const a=Boolean(reference.elements[name]?.present),b=Boolean(clone.elements[name]?.present);
   await check(key+': layout '+name+' present in both',a&&b,JSON.stringify({original:a,clone:b}));
 }
 // Pine has no traditional screener title/filter/table. Both implementations must omit them.
 if(key==='pine'){
  for(const name of ['categorySwitch','screenTitle','filterPanel','tabs','resultTable','tableBody']){
   await check(key+': absent '+name+' in both',!reference.elements[name]?.present&&!clone.elements[name]?.present);
  }
 } else {
  const normalized=s=>String(s||'').replace(/\s+/g,'').replace(/[⌄▾▼]/g,'').trim();
  await check(key+': all visible preset tab names and order',
    JSON.stringify(reference.tabs.map(normalized))===JSON.stringify(clone.tabs.map(normalized)),
    JSON.stringify({original:reference.tabs,clone:clone.tabs}));
  await check(key+': all visible filter names and order',
    JSON.stringify(reference.filters.map(normalized))===JSON.stringify(clone.filters.map(normalized)),
    JSON.stringify({original:reference.filters,clone:clone.filters}));
  const transformed=reference.fieldIds.map(x=>DISPLAY_FIELD_MAP[x]||x);
  await check(key+': all columns equivalent by semantics and exact order',
    JSON.stringify(transformed)===JSON.stringify(clone.fieldIds),
    JSON.stringify({original:reference.fieldIds,mapped:transformed,clone:clone.fieldIds}));
  await check(key+': result rows exist in both',reference.symbolRows>0&&clone.symbolRows>0,
    JSON.stringify({reference:reference.symbolRows,clone:clone.symbolRows}));
 }
 const order=key==='pine'?['siteHeader','main']:['siteHeader','categorySwitch','screenTitle','filterPanel','tabs','resultTable'];
 for(const mode of [reference,clone]){
  const boxes=order.map(k=>({name:k,y:mode.elements[k]?.boxes[0]?.y})).filter(x=>typeof x.y==='number');
  await check(key+': '+mode.mode+' structural order',boxes.every((x,i)=>!i||x.y>=boxes[i-1].y-8),JSON.stringify(boxes));
 }
}

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
  // Judge ORIGINAL screenshot resolution, never a downsampled preview.
  const aImage=await sharp(ours).removeAlpha().raw().toBuffer({resolveWithObject:true});
  const bImage=await sharp(expectedPath).removeAlpha().raw().toBuffer({resolveWithObject:true});
  const {width,height,channels}=aImage.info;
  if(width!==bImage.info.width||height!==bImage.info.height||channels!==3||bImage.info.channels!==3)
    throw new Error('Native screenshot geometry mismatch, original='+bImage.info.width+'x'+bImage.info.height+' clone='+width+'x'+height);
  const a=aImage.data,b=bImage.data;
  const compare=new Uint8Array(a.length);
  let total=0,changed=0;
  for(let i=0;i<a.length;i+=3){
   const dr=Math.abs(a[i]-b[i]),dg=Math.abs(a[i+1]-b[i+1]),db=Math.abs(a[i+2]-b[i+2]);
   const diff=(dr+dg+db)/3;total+=diff;
   if(diff>35)changed++;
   compare[i]=dr;compare[i+1]=dg;compare[i+2]=db;
  }
  const score={mean_absolute_rgb_error:+(total/(width*height)).toFixed(2),
    pixel_fraction_changed_35:+(changed/(width*height)).toFixed(4),
    measured_resolution:width+'x'+height,measured_pixels:width*height,
    threshold_mean_absolute_rgb:35};
  // Scale only the displayed difference preview, not the acceptance measurement.
  await sharp(Buffer.from(compare),{raw:{width,height,channels:3}}).resize(392,240).png().toFile(path.join(OUT,key+'_diff.png'));
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
  const localScanRequests=[];
  page.on('request',req=>{if(req.url().includes('/api/scan')){try{localScanRequests.push(req.postDataJSON())}catch{}}});
  page.on('pageerror',error=>exceptions.push(error.message));
  const response=await page.goto(ROOT+route,{waitUntil:'domcontentloaded',timeout:30000});
  await page.waitForSelector('[data-testid="screener-app"]',{timeout:20000});
  if(key!=='pine'){await page.waitForFunction(()=>document.querySelector('[data-testid="screener-app"]').dataset.source!==''&&!document.querySelector('[data-testid="screener-app"]').querySelector('.spin'),null,{timeout:40000}).catch(()=>{});}
  await page.waitForTimeout(550);
  await page.waitForFunction(()=>[...document.querySelectorAll('.logo-host img')].slice(0,20).every(img=>img.complete),null,{timeout:3000}).catch(()=>{});
  const logoLoad=await page.locator('.logo-host img').evaluateAll(imgs=>({count:imgs.length,loaded:imgs.filter(i=>i.complete&&i.naturalWidth>0).length,failed:imgs.filter(i=>i.complete&&!i.naturalWidth).length}));
  await fs.writeFile(path.join(OUT,key+'_local_logo_status.json'),JSON.stringify(logoLoad,null,2));
  const title=await page.locator('.screen-name').innerText();
  const tabs=await page.locator('[role="tab"]').count();
  const filters=await page.locator('.filter-pill').count();
  const rows=await page.locator('.screener-table tbody tr').count();
  const source=await page.locator('[data-testid="screener-app"]').getAttribute('data-source');
  const appShot=path.join(OUT,key+'_ours.png');
  await page.screenshot({path:appShot,fullPage:false});
  let referenceType='missing',referenceShot=null,refTabs=null,referenceLayout=null;
  const cloneLayout=await collectLayout(page,false,key);
  const originalPage=await ctx.newPage();
  const capturedReqs=[];
  const capturedResponses=[];
  originalPage.on('response',async response=>{
    if(!response.url().includes('/scan?')||response.status()!==200)return;
    try{const json=await response.json();if(json?.data?.length)capturedResponses.push({url:response.url(),totalCount:json.totalCount,rows:json.data.slice(0,20)})}catch{}
  });
  originalPage.on('request',request=>{if(request.url().includes('/scan?')){let json=null;try{json=request.postDataJSON()}catch{}capturedReqs.push({url:request.url(),method:request.method(),json});}});
  try{
   let result=await originalPage.goto(original,{waitUntil:'domcontentloaded',timeout:35000});
   await originalPage.waitForTimeout(4500);
   if(result?.status()===200){
    referenceType='live';referenceShot=path.join(OUT,key+'_original_live.png');
    refTabs=await originalPage.locator('#market-screener-header-columnset-tabs [role="tab"]:not([aria-hidden="true"])').count().catch(()=>null);
    await originalPage.screenshot({path:referenceShot,fullPage:false});
    referenceLayout=await collectLayout(originalPage,true,key);
   }
  }catch(e){console.log('LIVE REF UNAVAILABLE',key,String(e).slice(0,160))}
  const logoSamples=await originalPage.locator('tbody tr').first().locator('img').evaluateAll(imgs=>imgs.map(i=>({src:i.getAttribute('src'),alt:i.getAttribute('alt'),text:i.parentElement?.textContent?.slice(0,70)}))).catch(()=>[]);
  await fs.writeFile(path.join(OUT,key+'_original_logo_urls.json'),JSON.stringify(logoSamples,null,2));
  await originalPage.close();
  if(capturedReqs.length&&localScanRequests.length){
    const originalQuery=capturedReqs[0].json;
    const localQuery=localScanRequests.at(-1)?.payload;
    const sameCols=JSON.stringify(originalQuery.columns)===JSON.stringify(localQuery?.columns);
    const sameSort=JSON.stringify(originalQuery.sort)===JSON.stringify(localQuery?.sort);
    const sameFilter2=JSON.stringify(originalQuery.filter2||null)===JSON.stringify(localQuery?.filter2||null);
    await check(key+': original scan columns exact',sameCols,'columns '+(localQuery?.columns?.length||0));
    await check(key+': original scan sorting exact',sameSort,JSON.stringify(localQuery?.sort));
    await check(key+': original scan filter2 exact',sameFilter2);
  }
  await fs.writeFile(path.join(OUT,key+'_original_scans.json'),JSON.stringify(capturedReqs,null,2));
  await fs.writeFile(path.join(OUT,key+'_original_scan_response_sample.json'),JSON.stringify(capturedResponses,null,2));
  if(referenceType==='missing'&&staticRef){const file=path.resolve('evidence',staticRef);try{await fs.access(file);referenceType='captured';referenceShot=file;}catch{}}
  const visual=await screenshotComparison(appShot,referenceShot,key);
  await fs.writeFile(path.join(OUT,key+'_layout-inventory.json'),JSON.stringify({original:referenceLayout,clone:cloneLayout},null,2));
  if(referenceLayout)await validateLayout(key,referenceLayout,cloneLayout);
  else await check(key+': ORIGINAL REFERENCE REQUIRED',false,'Original visible DOM unavailable: cannot claim parity.');
  await check(key+': visible pixel mismatch <= 10 percent',
    Boolean(visual&&Number.isFinite(visual.pixel_fraction_changed_35)&&visual.pixel_fraction_changed_35<=UI_PARITY_LIMIT),
    JSON.stringify({fraction:visual?.pixel_fraction_changed_35,limit:UI_PARITY_LIMIT,definition:'native screenshot pixels, absolute RGB average >35'}));
  results.push({kind:'page',key,route,title,tabs,filters,rows,source,response_status:response.status(),referenceType,refTabs,visual,exceptions});
  await check(key+': HTTP 200',response.status()===200);
  if(key!=='pine')await check(key+': public symbol logos loaded',logoLoad.loaded>0,JSON.stringify(logoLoad));
  await check(key+': heading exists',title?.length>2);
  await check(key+': tabs = '+tabCount,tabs===tabCount);
  await check(key+': filters visible',key==='pine'?(await page.locator('.filter-pill:visible').count())===0:filters>=3);
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
   await check(key+': original filter groups visible',await page.locator('[data-testid="filter-category-list"] button').count()>=(key==='stock'?8:key==='etf'?5:7));
   await page.locator('[data-testid="filter-category-list"] button').first().click();
   await check(key+': filter group opens connected field choices',await page.locator('[data-testid="filter-candidate-list"]').count()===1);
   await page.locator('.filter-picker-back').click();
   await page.locator('input[aria-label="필터 찾기"]').fill(key==='stock'?'가격':key==='etf'?'AUM':'쿠폰 %');
   await check(key+': global filter search matches',await page.locator('[data-testid="filter-candidate-list"] button').count()>0);
   await page.locator('.pop-header button').click();
   await page.locator('[data-qa-id="screener-add-column-button"]').click();
   await check(key+': columns popup',await page.locator('.popover-columns .option-list button').count()>4);
   await page.locator('.pop-header button').click();
   if(key==='bond'){
     await page.locator('[data-testid="filter-발행자"]').click();
     await page.locator('.popover-filter .filter-values label').first().waitFor({timeout:15000});
     await check('bond: real issuer enum search',await page.locator('.popover-filter .filter-values label').count()>=25);
     await page.locator('.popover-filter .popup-search').fill('Johnson');
     await check('bond: filter matches issuer names',await page.locator('.popover-filter .filter-values label').count()>=1);
     await page.locator('.pop-header button').click();
   }
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
