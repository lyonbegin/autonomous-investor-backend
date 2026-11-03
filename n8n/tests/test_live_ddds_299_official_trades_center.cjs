/* ACTUAL production Railway WF02 DDDS public 299 trade source acceptance.
 * Real Playwright, real source page, real original browser worker.
 */
const {chromium}=require('playwright');
const fs=require('fs');
const base=process.env.WF02_EDITOR_BASE||
  'https://investment-n8n-native-editor-production.up.railway.app';
const dir=process.env.WF02_299_EVIDENCE||'/tmp/ddds-299-live';
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
 try{
  const page=await browser.newPage({viewport:{width:1530,height:1050},locale:'en-US'});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const response=await page.goto(base+'/admin/index.html?section=convert',
    {waitUntil:'domcontentloaded',timeout:45000});
  if(response?.status()!==200)throw Error('EXISTING_WF02_NOT_HTTP_200');
  // Wait for the original site's asynchronous session bootstrap and
  // workflow canvas rendering BEFORE checking dynamic DOM. The first paint
  // intentionally contains only the overview/sidebar and no WF02 elements.
  const btn=page.locator('#ddds-trades-capture');
  await btn.waitFor({state:'visible',timeout:60000});
  await page.waitForFunction(()=>document.getElementById('tv-publication-status')?.
    textContent?.includes('원본 확인'),null,{timeout:45000});
  const diagnostics=page.locator('#wf02-unrelated-aapl-diagnostics');
  const diagnosticState={
    count:await diagnostics.count(),
    open:await diagnostics.count()?await diagnostics.getAttribute('open'):null,
    sourceMarker:await page.locator('body').evaluate(el=>el.innerHTML.includes('wf02-unrelated-aapl-diagnostics')),
    currentUrl:page.url(),
    detailsCount:await page.locator('details').count(),
    publicationPanels:await page.locator('#published-strategy-reference').count(),
    diagnosticButtons:await page.locator('#tv-chart-start').count(),
    reportStatus:await page.locator('#tv-publication-status').allTextContents(),
    actionButton:await page.locator('#ddds-trades-capture').count()
  };
  fs.mkdirSync(dir,{recursive:true});
  await page.screenshot({path:dir+'/debug-before-ddds.png',fullPage:true});
  console.log('WF02_DOCUMENT_ACTUAL_TAGS',JSON.stringify(await page.locator('body').evaluate(el=>({
    details:Array.from(el.querySelectorAll('details')).slice(0,4).map(x=>x.outerHTML.slice(0,110)),
    panels:Array.from(el.querySelectorAll('[id]')).filter(x=>x.id.includes('published')||x.id.includes('unrelated')||x.id.includes('ddds-')).map(x=>({id:x.id,tag:x.tagName})).slice(0,15),
    execOuter:el.querySelector('#flow-panel')?.outerHTML.slice(0,220),
    sourceLen:el.innerHTML.length
  }))));
  console.log('WF02_DIAGNOSTIC_UI_PROOF',JSON.stringify(diagnosticState));
  if(diagnosticState.count!==1 || diagnosticState.open!==null)
    throw Error('UNRELATED_AAPL_SMA_DIAGNOSTICS_MUST_BE_COLLAPSED '+JSON.stringify(diagnosticState));
  const primary=page.locator('#published-strategy-reference');
  if(await primary.count()!==1)
    throw Error('ORIGINAL_DDDS_STRATEGY_PANEL_MISSING');
  await btn.click();
  await page.waitForFunction(()=>{
    const status=document.getElementById('ddds-trades-status')?.textContent||'';
    return status.includes('299/299')||status.includes('실제 거래 목록 확보 실패');
  },null,{timeout:165000});
  const state=await page.locator('#ddds-trades-status').innerText();
  if(!state.includes('299/299'))
    throw Error('OFFICIAL_299_DDDS_TRADES_NOT_SHOWING '+state);
  const responseResult=await page.request.get(base+'/api/investment/tv-publication/trades/latest');
  if(responseResult.status()!==200)
    throw Error('SESSION_DDDS_TRADES_NOT_PERSISTED');
  const result=await responseResult.json();
  if(result.status!=='PUBLISHED_DDDS_299_TRADES_CAPTURED'||
     result.observed_trade_count!==299||
     result.capture_verified_complete!==true||
     result.trades.length!==299||
     result.trades[0].trade_number!==299||
     result.trades[298].trade_number!==1||
     result.trades[0].entry_price_display!==250.04||
     result.trades[0].exit_price_display!==255.60||
     result.trades[0].net_pnl_display!==-656.85||
     result.pine_source_sha256!=='5a245e99447f13012dd026528235fc2c299cad5cb7b228653c684886dcba6507'||
     result.tradingview_pynecore_parity_verified!==false||
     result.live_orders_enabled!==false)
    throw Error('INVALID_ACTUAL_TRADE_BASELINE '+JSON.stringify(result).slice(0,800));
  const count=await page.locator('#ddds-trades-rows tr').count();
  if(count!==299)throw Error('DDDS_TRADES_TABLE_INCOMPLETE '+count);
  const right=await page.locator('#publication-python-state').innerText();
  if(!right.includes('미검증'))
    throw Error('FALSE_DDDS_PYTHON_PARITY_CLAIM '+right);

  const csvButton=page.locator('#ddds-trades-export');
  if(await csvButton.count()!==1 || await csvButton.isDisabled())
    throw Error('VERIFIED_TRADES_CSV_BUTTON_NOT_ENABLED');
  const [download]=await Promise.all([
    page.waitForEvent('download',{timeout:18000}),csvButton.click()
  ]);
  if(download.suggestedFilename()!=='DDDS_BATS-AMZN_2h_TradingView_published_299_trades.csv')
    throw Error('WRONG_VERIFIED_DDDS_CSV_FILE_NAME '+download.suggestedFilename());
  const csv=fs.readFileSync(await download.path(),'utf8');
  if(!csv.startsWith('\uFEFF'))throw Error('DDDS_CSV_UTF8_BOM_MISSING');
  const csvLines=csv.slice(1).trimEnd().split('\r\n');
  if(csvLines.length!==300 ||
     !csvLines[0].includes('entry_time_display_timezone_unspecified')||
     !csvLines[1].startsWith('"299","SHORT"')||
     !csvLines[299].startsWith('"1",')||
     !csvLines[1].includes(result.pine_source_sha256))
    throw Error('DDDS_299_CSV_MISSING_OR_TAMPERED '+JSON.stringify({
      rows:csvLines.length,header:csvLines[0]?.slice(0,100),
      first:csvLines[1]?.slice(0,70),last:csvLines[299]?.slice(0,60)
    }));
  if(errors.length)throw Error('PAGE_JS_ERRORS '+errors.join(';'));
  fs.mkdirSync(dir,{recursive:true});
  await page.locator('#published-strategy-reference').screenshot({path:dir+'/ddds-299-real-trades-wf02.png'});
  const withoutAllRows={...result,trades:undefined};
  fs.writeFileSync(dir+'/ddds-299-live-verified-manifest.json',JSON.stringify({
     ...withoutAllRows,trades_sample:[result.trades[0],result.trades[98],result.trades[298]],
     ui_rows:count,parityVerified:false,
     capturedAt:new Date().toISOString()
  },null,2));
  console.log('LIVE_ORIGINAL_WF02_REAL_TV_DDDS_299_TRADES_PASS',JSON.stringify({
   trades:count,first:result.trades[0].trade_number,last:result.trades[298].trade_number,
   source:result.source,hash:result.rows_sha256,parity:false
  }));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
