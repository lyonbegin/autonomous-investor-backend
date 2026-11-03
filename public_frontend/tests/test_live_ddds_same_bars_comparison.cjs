/* Real deployed original public frontend + existing n8n editor comparison API.
 * Must click UI and verify actual 300 OHLCV matched and real plots compared.
 */
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path');
const BASE='https://autonomous-investor-public-production.up.railway.app';
const ID='PUB;5442675d418140c58486eb4a7ae12768';
const out=process.env.DDDS_WEB_UI_EVIDENCE||'/tmp/ddds-same-bars-ui-e2e';
(async()=>{
 fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
 const page=await browser.newPage({viewport:{width:1520,height:1150},locale:'ko-KR'});
 const errors=[];page.on('pageerror',e=>errors.push(e.message.slice(0,350)));
 try{
   const response=await page.goto(BASE+'/compare/'+encodeURIComponent(ID),{waitUntil:'domcontentloaded',timeout:60000});
   if(response?.status()!==200)throw Error('SITE_COMPARE_HTTP_FAILURE');
   const root=page.getByTestId('ddds-shared-chart-comparison');
   await root.waitFor({timeout:85000});
   const buttons=root.getByRole('button',{name:/같은 봉을 Python에 전달해 비교/});
   await buttons.waitFor({timeout:30000});
   if(await buttons.isEnabled())throw Error('MPL_RIGHTS_CONFIRMATION_NOT_REQUIRED');
   await root.getByRole('checkbox').check();
   if(!await buttons.isEnabled())throw Error('EXACT_DDDS_300_BAR_SITE_CHART_NOT_READY');
   await buttons.click();
   await page.waitForFunction(()=>{
     const t=document.querySelector('[data-testid="ddds-same-bar-status"]')?.textContent||'';
     return t.includes('300/300')||document.body.innerText.includes('Python 실행 실패:');
   },{timeout:160000});
   const status=await root.getByTestId('ddds-same-bar-status').innerText();
   if(!status.includes('300/300'))throw Error('NOT_SAME_300_BARS '+status+' '+(await root.innerText()).slice(0,700));
   await root.getByTestId('ddds-python-chart').waitFor({timeout:25000});
   const plots=await root.getByTestId('ddds-plot-comparison').innerText();
   const capture=await root.getByTestId('ddds-vela-status').innerText();
   if(/공통 지표값 0개/.test(plots)||!/공통 지표값 [1-9][0-9]*개/.test(plots))
     throw Error('DDDS_COMMON_NUMERIC_INDICATOR_OUTPUT_MISSING '+plots);
   if(/불일치 [1-9][0-9]*개/.test(plots))throw Error('DDDS_SAME_BARS_PLOT_MISMATCH '+plots);
   if(errors.length)throw Error('PAGE_JS_ERRORS '+errors.join('|'));
   await page.screenshot({path:path.join(out,'real-site-DDDS-vela-python-300-bars.png'),fullPage:true});
   const result={status:'DDDS_REAL_SITE_TWO_CHARTS_SAME_300_BARS_VERIFIED',
     website:BASE,source_id:ID,bar_count:300,plots,vela_status:capture,errors};
   fs.writeFileSync(path.join(out,'actual-browser-ui-result.json'),JSON.stringify(result,null,2));
   console.log('REAL_SITE_DDDS_TWO_CHART_PASS '+JSON.stringify(result));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
