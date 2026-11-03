const {chromium}=require('playwright');
const fs=require('node:fs');
const URL=process.env.CHART_TEST_BASE||'http://127.0.0.1:5173';
const CASES=[
 {id:'PUB;fd5cad2ba18e450f8665ea1761f9b034',kind:'indicator'},
 {id:'PUB;9697fd0fa80f4251ac278e6ec9d172f5',kind:'strategy'}
];
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  for(const item of CASES){
   const page=await browser.newPage({viewport:{width:1350,height:1000},acceptDownloads:true});
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   const url=URL+'/scripts/'+encodeURIComponent(item.id);
   const navigation=await page.goto(url,{waitUntil:'domcontentloaded',timeout:40000});
   if(navigation?.status()!==200)throw Error('NOT_HTTP_200 '+url);
   const panel=page.getByTestId('chart-control-capture');
   await panel.waitFor({timeout:55000});
   await page.waitForFunction(()=>{
    const t=document.querySelector('[data-testid="chart-control-capture"]');
    return Boolean(t&&/봉 [1-9][0-9]*개 · 지표/.test(t.textContent||''));
   },{timeout:75000});
   const report=await panel.innerText();
   const downloadWait=page.waitForEvent('download',{timeout:25000});
   await panel.getByRole('button',{name:'전략 주문·체결 포함 JSON 내려받기'}).click();
   const download=await downloadWait;
   const file=await download.path();
   const payload=JSON.parse(fs.readFileSync(file,'utf8'));
   if(payload.provenance!=='VELA_PINETS_CHART_CONTROL'||payload.tv_original_export!==false||
      payload.script_id!==item.id||!payload.complete||payload.forming||
      payload.bars.length<40||!payload.bars[0].time_ms||
      !payload.bars[0].close||!Array.isArray(payload.trades))
    throw Error('CHART_OUTPUT_NOT_REAL '+JSON.stringify({kind:item.kind,report,payload}).slice(0,650));
   if(item.kind==='indicator'&&payload.plot_names.length===0)
    throw Error('INDICATOR_PLOT_SERIES_EMPTY');
   if(item.kind==='strategy'&&payload.kind!=='strategy')
    throw Error('STRATEGY_KIND_MISMATCH '+payload.kind);
   if(errors.length)throw Error('BROWSER_JS_ERROR '+errors.join(';').slice(0,700));
   const csvWait=page.waitForEvent('download',{timeout:20000});
   await panel.getByRole('button',{name:'지표·OHLCV CSV 내려받기'}).click();
   const csvDl=await csvWait;
   const csv=fs.readFileSync(await csvDl.path(),'utf8');
   if(csv.trim().split(/\r?\n/).length!==payload.bars.length+1)
    throw Error('CSV_BAR_COUNT_MISMATCH');
   if(process.env.CHART_CAPTURE_SCREENSHOT)
    await page.screenshot({path:process.env.CHART_CAPTURE_SCREENSHOT.replace('.png','-'+item.kind+'.png'),fullPage:true});
   console.log('CHART_CONTROL_CAPTURE_PASS',item.kind,JSON.stringify({
     bars:payload.bars.length,plots:payload.plot_names,trades:payload.trades.length,
     provider:payload.data_provider,source:payload.provenance,download:csvDl.suggestedFilename()
   }));
   await page.close();
  }
 }finally{await browser.close();}
})().catch(err=>{console.error(err);process.exit(1)});
