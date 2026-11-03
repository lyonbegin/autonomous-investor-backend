/* Read-only LIVE Chromium probe of EXISTING NativePineChartControl for exact DDDS.
 * Not an assertion of parity; records actual Vela compiler support/error.
 */
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path');
const BASE='https://autonomous-investor-public-production.up.railway.app';
const ID='PUB;5442675d418140c58486eb4a7ae12768';
const OUT=process.env.DDDS_VELA_PROBE_OUT||'/tmp/ddds-vela-native-probe';
(async()=>{
 fs.mkdirSync(OUT,{recursive:true});
 const browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const report={source_id:ID,base:BASE,status:'PROBING',page_http:null,
   native_capture_panel_visible:false,chart_runtime_text:null,
   pine_input_chart_succeeded:false,ddds_numeric_plots_observed:false,
   no_other_strategy_used:true,errors:[]};
 page.on('pageerror',e=>report.errors.push(String(e.message).slice(0,230)));
 try{
   const r=await page.goto(BASE+'/scripts/'+encodeURIComponent(ID),{
       waitUntil:'domcontentloaded',timeout:50000});
   report.page_http=r?.status()||null;
   const panel=page.getByTestId('chart-control-capture');
   await panel.waitFor({timeout:50000});
   report.native_capture_panel_visible=true;
   await page.waitForFunction(()=>{
     const root=document.querySelector('[data-testid="chart-control-capture"]');
     const t=document.body.innerText||'';
     return (root&&/봉 [1-9][0-9]*개/.test(root.textContent||''))||
       /Native Pine 실행 오류|원문 실행 진단:/.test(t);
   },{timeout:100000}).catch(()=>{});
   report.chart_runtime_text=(await page.locator('main').innerText())
      .slice(-4500);
   report.pine_input_chart_succeeded=
     /봉 [1-9][0-9]*개 · 지표/.test(await panel.innerText());
   report.ddds_numeric_plots_observed=/지표 [1-9][0-9]*개/.test(await panel.innerText());
   if(report.pine_input_chart_succeeded){
     const btn=panel.getByRole('button',{name:'전략 주문·체결 포함 JSON 내려받기'});
     if(await btn.isEnabled()){
       const [download]=await Promise.all([page.waitForEvent('download',{timeout:18000}),btn.click()]);
       const data=JSON.parse(fs.readFileSync(await download.path(),'utf8'));
       report.capture={kind:data.kind,source_hash:data.source_hash,
          script_id:data.script_id,bar_count:data.bars?.length||0,
          plot_names:data.plot_names||[],trades:data.trades?.length||0,
          source:data.provenance};
       report.ddds_numeric_plots_observed=report.capture.plot_names.length>0;
     }
   }
   await page.screenshot({path:path.join(OUT,'exact-ddds-on-original-site-native-pine.png'),fullPage:true});
   report.status='EXISTING_NATIVE_DDDS_INSPECTED';
 }catch(e){report.status='EXISTING_NATIVE_DDDS_INSPECTION_FAILED';report.errors.push(String(e.stack||e).slice(0,420))}
 finally{
   fs.writeFileSync(path.join(OUT,'runtime-report.json'),JSON.stringify(report,null,2));
   console.log('EXISTING_SITE_REAL_DDDS_VELA_RUNTIME '+JSON.stringify({...report,chart_runtime_text:report.chart_runtime_text?.slice(0,1800)}));
   await browser.close();
 }
 if(report.status!=='EXISTING_NATIVE_DDDS_INSPECTED')process.exitCode=3;
})();
