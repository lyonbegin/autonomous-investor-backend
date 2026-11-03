const {chromium}=require('playwright');
const base=process.env.PYNECORE_DEMO_BASE||'http://127.0.0.1:3000';
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1450,height:940}});
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  const resp=await page.goto(base+'/demo',{waitUntil:'domcontentloaded',timeout:30000});
  if(resp?.status()!==200)throw Error('DEMO_ROUTE_NOT_HTTP_200');
  await page.locator('#run').click();
  await page.getByText('실제 PyneCore 실행 성공',{exact:false}).waitFor({timeout:90000});
  const text=await page.locator('#counts').innerText();
  if(!text.includes('종료 거래')||await page.locator('#trades tr').count()<1)
    throw Error('REAL_PYNECORE_TRADE_RESULT_MISSING '+text);
  const data=await page.request.get(base+'/api/pynecore-demo',{timeout:90000});
  if(data.status()!==200)throw Error('REAL_PYNECORE_API_ERROR '+data.status());
  const result=await data.json();
  if(result.bar_count<900||result.strategy_closed_trades<1||
     result.market_data_is_synthetic!==false||result.tradingview_chart_validated!==false||
     result.live_orders_enabled!==false||result.new_pynecomp_compilation!==false)
    throw Error('WRONG_PROVENANCE_OR_EMPTY_OUTPUT '+JSON.stringify(result).slice(0,600));
  const csvResp=await page.request.get(base+'/api/pynecore-demo/export.csv',{timeout:90000});
  if(csvResp.status()!==200)throw Error('PYNECORE_FULL_CSV_DOWNLOAD_FAILED');
  const csvText=await csvResp.text();
  const lines=csvText.trim().split(/\r?\n/);
  if(lines.length!==1001||!lines[0].includes('Basis,Upper,Lower'))
    throw Error('PYNECORE_1000_BAR_CSV_EXPORT_INVALID '+lines.length);
  if(errors.length)throw Error('JS_ERRORS '+errors.join(';'));
  if(process.env.PYNECORE_DEMO_SCREENSHOT)
    await page.screenshot({path:process.env.PYNECORE_DEMO_SCREENSHOT,fullPage:true});
  const back=await page.goto(base+'/',{waitUntil:'domcontentloaded',timeout:30000});
  if(back?.status()!==200||await page.locator('#keypointRun').count()!==1)
    throw Error('ORIGINAL_PARITY_UI_BROKEN');
  console.log('REAL_PYNECORE_CHROMIUM_SUCCESS',result.bar_count,result.strategy_closed_trades);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
