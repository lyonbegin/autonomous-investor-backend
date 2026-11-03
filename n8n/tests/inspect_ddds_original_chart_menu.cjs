/* Public DDDS original chart menu/data-window inspection.
 * Only normal clicks on the actual TradingView publication widget.
 * Never substitutes a fresh chart, never pretends to capture OHLCV from pixels.
 */
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path');
const OUT=process.env.DDDS_ORIGINAL_CHART_PROBE_DIR||'/tmp/ddds-original-chart-probe';
const url='https://www.tradingview.com/script/LkgKT3TG-Displaced-Donchian-Decycler-Trend-Breakout-Strategy-with-MFI/';
(async()=>{
 fs.mkdirSync(OUT,{recursive:true});
 const browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
 const context=await browser.newContext({viewport:{width:1550,height:1120},locale:'en-US',acceptDownloads:true});
 const page=await context.newPage();
 const report={status:'STARTED',original:url,chart_canvas_count:0,
   exact_original_chart:true,
   right_click_menu_visible:false,menu_strings:[],
   export_chart_data_control_visible:false,exported_file:false,
   visible_series_values:[],hovered_series_values:[],hovered_times:[],
   script_tags_with_chart_data_markers:[],errors:[]};
 try{
  const resp=await page.goto(url,{waitUntil:'domcontentloaded',timeout:55000});
  await page.waitForTimeout(7500);
  const chart=page.locator('[data-name="publication-view-chart-container"]');
  await chart.waitFor({timeout:15000});
  report.chart_canvas_count=await chart.locator('canvas').count();
  const pane=chart.locator('[data-qa-id="pane"]').first();
  const bb=await pane.boundingBox();
  report.visible_series_values=await chart.locator('[data-qa-id="legend"] [data-test-id-value-title]')
      .evaluateAll(els=>els.slice(0,22).map(x=>({name:x.getAttribute('data-test-id-value-title'),
        value:(x.textContent||'').replace(/\s+/g,' ').slice(0,100)})));
  if(bb){
    for(const x of [0.18,0.32,0.46,0.61,0.76]){
      await page.mouse.move(bb.x+bb.width*x,bb.y+bb.height*0.48);
      await page.waitForTimeout(250);
      report.hovered_series_values.push({
        x:Number(x.toFixed(2)),
        indicators:await chart.locator('[data-qa-id="legend"] [data-test-id-value-title]')
        .evaluateAll(es=>es.slice(0,22).map(e=>({name:e.getAttribute('data-test-id-value-title'),
             value:(e.textContent||'').replace(/\s+/g,' ').slice(0,80)})))
      });
    }
    await page.mouse.click(bb.x+bb.width*.50,bb.y+bb.height*.50,{button:'right'});
    await page.waitForTimeout(1400);
  }
  report.menu_strings=await page.locator('[role="menu"],[role="menuitem"],[data-name="context-menu"]')
    .evaluateAll(els=>els.slice(0,60).map(el=>(el.innerText||el.textContent||'').replace(/\s+/g,' ').slice(0,200)).filter(Boolean));
  report.right_click_menu_visible=report.menu_strings.length>0;
  report.export_chart_data_control_visible=report.menu_strings.some(x=>/export chart data|export.*csv|download.*data/i.test(x));
  await page.screenshot({path:path.join(OUT,'ddds-original-context-menu.png')});
  const stat=await page.evaluate(()=>document.scripts?Array.from(document.scripts).slice(0,100).map((s,i)=>({
    i,type:s.type||'js',size:(s.textContent||'').length,
    hasCandles:/ohlcv|candles|bars|timescale_update|series_loading/i.test(s.textContent||''),
    hasChart:/chartData|chart_data|chartState|chart_state/i.test(s.textContent||'')
  })).filter(x=>x.size>100&&x.hasCandles||x.hasChart).slice(0,15):[]);
  report.script_tags_with_chart_data_markers=stat;
  report.status='ORIGINAL_CHART_MENU_INSPECTED';
 }catch(e){report.status='FAILED';report.errors.push(String(e.stack||e).slice(0,600))}
 finally{
   fs.writeFileSync(path.join(OUT,'original-chart-menu-evidence.json'),JSON.stringify(report,null,2));
   console.log('ORIGINAL_DDDS_CHART_CONTEXT_MENU '+JSON.stringify(report).slice(0,18000));
   await browser.close();
 }
 if(report.status!=='ORIGINAL_CHART_MENU_INSPECTED')process.exitCode=2;
})();
