/* Public TradingView DDDS Strategy Report Properties read-only inspection.
 * Browser-native clicks, no login or undocumented API replay.
 * Does not assume visible values are publisher source defaults.
 */
const {chromium}=require('playwright');
const fs=require('fs');
const dir=process.env.DDDS_PROPERTIES_DIR||'/tmp/ddds-tv-properties';
const pageUrl='https://www.tradingview.com/script/LkgKT3TG-Displaced-Donchian-Decycler-Trend-Breakout-Strategy-with-MFI/';
(async()=>{
 fs.mkdirSync(dir,{recursive:true});
 const browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
 const result={
  status:'NOT_CHECKED',source:'PUBLIC_TRADINGVIEW_DDDS_STRATEGY_REPORT_PROPERTIES_BROWSER',
  url:pageUrl,http_status:null,opened_report:false,opened_properties:false,
  properties_text:'',properties_rows:[],visible_inputs:[],errors:[],
  retrieved_at:new Date().toISOString(),
  is_current_authenticated_strategy_tester:false,
  pynecomp_python_generated:false,parity_verified:false
 };
 try{
  const page=await browser.newPage({viewport:{width:1520,height:1050},locale:'en-US'});
  page.on('pageerror',e=>result.errors.push(e.message.slice(0,160)));
  const response=await page.goto(pageUrl,{waitUntil:'domcontentloaded',timeout:50000});
  result.http_status=response?.status()||null;
  await page.waitForTimeout(7000);
  const top=page.getByText('Strategy report',{exact:true}).filter({visible:true}).first();
  if(await top.count()){
    await top.click({timeout:13000});
    result.opened_report=true;
  }
  const report=page.locator('[data-qa-id="backtesting-static"]').first();
  if(result.opened_report)await report.waitFor({timeout:18000});
  const properties=report.locator('[role="tab"][id="Properties"]').first();
  if(await properties.count()){
    await properties.click({timeout:12000});
    await page.waitForTimeout(3200);
    result.opened_properties=true;
  }
  if(result.opened_properties){
    const text=await report.innerText();
    result.properties_text=text.slice(0,12000);
    result.properties_rows=await report.locator('tr,[role="row"]').evaluateAll(
      es=>es.slice(0,120).map(e=>(e.innerText||'').replace(/\s+/g,' ').trim().slice(0,250))
        .filter(Boolean));
    result.visible_inputs=await report.locator('input,select').evaluateAll(
      es=>es.slice(0,50).map(e=>({
        type:e.type,placeholder:e.getAttribute('placeholder')||'',
        aria:e.getAttribute('aria-label')||'',value:e.value||''
      })));
  }
  await page.screenshot({path:dir+'/ddds-official-published-properties.png',fullPage:false});
  result.status=result.opened_properties&&result.properties_text.length>60?
    'OFFICIAL_PUBLIC_DDDS_PROPERTIES_TAB_VISIBLE':'DDDS_PUBLIC_PROPERTIES_NOT_ACCESSIBLE';
  fs.writeFileSync(dir+'/ddds-properties-evidence.json',JSON.stringify(result,null,2));
  console.log('TV_DDDS_PUBLISHED_PROPERTIES_UI_INSPECTION',JSON.stringify(result).slice(0,17000));
  if(result.http_status!==200||!result.opened_properties||result.properties_text.length<60)
    process.exitCode=2;
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=2});
