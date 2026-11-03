/* Real user-browser acceptance test against deployed ORIGINAL WF-02 center.
 * NO mocks, no uploaded fake TV CSV and no official Strategy Tester claims.
 */
const {chromium}=require('playwright');
const fs=require('fs');
const target=process.env.WF02_EDITOR_BASE||
 'https://investment-n8n-native-editor-production.up.railway.app';
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1510,height:1030}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const response=await page.goto(target+'/admin/index.html?section=convert',
    {waitUntil:'domcontentloaded',timeout:45000});
  if(response?.status()!==200)throw Error('EXISTING_ADMIN_NOT_HTTP_200');
  await page.locator('#tv-chart-start').waitFor({timeout:35000});
  const nodes=await page.locator('#node-list .step').count();
  if(nodes!==6)throw Error('WF02_ORIGINAL_6_NODE_GRAPH_MISSING '+nodes);
  const previous=await page.request.get(target+'/api/investment/tv-chart/latest');
  if(previous.status()!==200)throw Error('WF02_LATEST_API_FAILED');
  await page.locator('#tv-chart-start').click();
  await page.waitForFunction(()=>{
    const t=document.querySelector('#tv-chart-status')?.textContent||'';
    return t.includes('실제 실행 성공')||t.includes('검증 실패');
  },null,{timeout:115000});
  const label=await page.locator('#tv-chart-status').innerText();
  if(!label.includes('실제 실행 성공'))
    throw Error('LIVE_OFFICIAL_CHART_TO_PYNECORE_FAILED '+label);
  const resultApi=await page.request.get(target+'/api/investment/tv-chart/latest');
  const result=await resultApi.json();
  if(resultApi.status()!==200||
    result.status!=='OFFICIAL_CHART_OHLCV_PYNECORE_EXECUTED'||
    result.bars_from_official_chart<20||
    result.bars_executed_by_pynecore!==result.bars_from_official_chart||
    !result.chart||result.chart.length!==result.bars_from_official_chart||
    !result.chart.some(b=>b.Basis!==null&&Number.isFinite(b.Basis))||
    result.provenance!=='TRADINGVIEW_PUBLIC_CHART_PASSIVE_WEBSOCKET'||
    result.tv_strategy_parity_verified!==false||
    result.new_pynecomp_compilation!==false||
    result.live_orders_enabled!==false)
   throw Error('INVALID_REAL_TV_PYNECORE_CONTRACT '+JSON.stringify(result).slice(0,900));
  if(await page.locator('#tv-official-svg path').count()<1||
     await page.locator('#tv-pynecore-svg path').count()<3)
   throw Error('ACTUAL_DUAL_CHARTS_NOT_DRAWN');
  if(await page.locator('#tv-proof-trades tr').count()<1)
   throw Error('PYNECORE_TRADES_NOT_SHOWN');
  if(errors.length)throw Error('BROWSER_ERRORS '+errors.join(';'));
  const dir=process.env.WF02_EVIDENCE_DIR;
  if(dir){
    fs.mkdirSync(dir,{recursive:true});
    await page.locator('#official-tv-chart-wf02').screenshot({path:dir+'/wf02-official-chart-pynecore.png',timeout:20000});
    fs.writeFileSync(dir+'/wf02-official-chart-pynecore.json',JSON.stringify(result,null,2));
  }
  console.log('WF02_EXISTING_CENTER_ACTUAL_TV_PYNECORE_PASS',JSON.stringify({
    nodes,bars:result.bars_from_official_chart,pynecore:result.bars_executed_by_pynecore,
    trades:result.closed_trades_from_pynecore,source:result.provenance,
    strategyParity:result.tv_strategy_parity_verified,session:result.executed_at
  }));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
