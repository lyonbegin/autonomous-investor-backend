/* Observe official, public TradingView DDDS strategy publication
 * STRATEGY REPORT -> List of Trades with ordinary Chromium UI controls.
 * No credentials, no internal APIs, no WS frame replay and no scraping service.
 */
const {chromium}=require('playwright');
const fs=require('fs');
const path=require('path');
const output=process.env.TV_DDDS_INSPECT_DIR||'/tmp/tv-ddds-inspect';
const URL='https://www.tradingview.com/script/LkgKT3TG-Displaced-Donchian-Decycler-Trend-Breakout-Strategy-with-MFI/';
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function main(){
 fs.mkdirSync(output,{recursive:true});
 const browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
 const result={
  source:'OFFICIAL_TRADINGVIEW_PUBLICATION_CHROMIUM_UI',
  url:URL,logged_in:false,original_trades_api:false,
  navigation:0,title:'',reportContainer:false,strategyLegend:false,tabs:[],
  clickedListOfTrades:false,visibleRows:0,rowSamples:[],
  errors:[],wsMethodCounts:{},strategyReportMetricsText:''
 };
 try{
  const page=await browser.newPage({viewport:{width:1480,height:1100},locale:'en-US'});
  page.on('pageerror',e=>result.errors.push(e.message.slice(0,150)));
  page.on('websocket',ws=>{
   if(!ws.url().includes('tradingview.com'))return;
   ws.on('framereceived',frame=>{
    if(typeof frame.payload!=='string')return;
    for(const match of frame.payload.matchAll(/"m":"([a-z][a-z0-9_]+)"/g)){
      const m=match[1];result.wsMethodCounts[m]=(result.wsMethodCounts[m]||0)+1;
    }
   });
  });
  const r=await page.goto(URL,{waitUntil:'domcontentloaded',timeout:45000});
  result.navigation=r?.status()||0;
  await sleep(9000);
  result.title=await page.title();
  // Publication defaults to Chart. Its real Strategy report tab must be clicked
  // before the backtesting-static panel and nested Trades tabs are mounted.
  const topReport=page.getByText('Strategy report',{exact:true}).filter({visible:true}).first();
  if(await topReport.count()){
    await topReport.click({timeout:12000});await sleep(6500);
    result.clickedStrategyReportTab=true;
  }else result.clickedStrategyReportTab=false;
  result.reportContainer=await page.locator('[data-qa-id="backtesting-static"]').count()>0;
  result.strategyLegend=await page.locator('[data-qa-id="legend-source-item"]').count()>0;
  result.tabs=await page.locator('[data-qa-id="backtesting-static"] [role="tab"]').evaluateAll(
   els=>els.map(x=>({id:x.id,text:x.textContent?.trim().slice(0,70)})));
  result.strategyReportMetricsText=(await page.locator('[data-qa-id="strategy-key-facts"]').allInnerTexts())
   .join(' | ').slice(0,500);
  await page.screenshot({path:path.join(output,'publication-before-trades.png'),fullPage:false});
  const tab=page.locator('[data-qa-id="backtesting-static"] [role="tab"][id="List of Trades"]').first();
  if(await tab.count()){
   await tab.click({timeout:8000});await sleep(5000);
   result.clickedListOfTrades=true;
   await page.screenshot({path:path.join(output,'publication-trades-tab.png'),fullPage:false});
  }
  const region=page.locator('[data-qa-id="backtesting-static"]').first();
  const t=await region.innerText().catch(()=>''),lines=t.split('\n').filter(x=>x.trim());
  result.visibleRows=await region.locator('tr,[role="row"]').count();
  result.rowSamples=(await region.locator('tr,[role="row"]').allInnerTexts()).slice(0,8).map(x=>x.slice(0,280));
  result.afterTabText=lines.slice(0,65).join(' | ').slice(0,2500);
  result.serverTradeListAvailable=result.clickedListOfTrades&&result.visibleRows>2;
  result.uiOnlyNoOrderCapture=!result.serverTradeListAvailable;
  console.log('TV_DDDS_PUBLICATION_LIST_OF_TRADES_PROBE',JSON.stringify(result).slice(0,15000));
  fs.writeFileSync(path.join(output,'ddds-publication-trades-probe.json'),JSON.stringify(result,null,2));
  if(result.navigation!==200||!result.reportContainer||!result.strategyLegend)process.exitCode=2;
 }finally{await browser.close();}
}
main().catch(e=>{console.error(e);process.exitCode=2;});
