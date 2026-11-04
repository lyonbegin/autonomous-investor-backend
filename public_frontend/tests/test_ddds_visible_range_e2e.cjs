/* E2E specifically addressing the user's screenshot:
 * both ACTUAL chart rendering engines must display matching UTC time extents,
 * not merely have 300 same input bars in their memory.
 */
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path');
const BASE='https://autonomous-investor-public-production.up.railway.app';
const ID='PUB;5442675d418140c58486eb4a7ae12768';
const OUT=process.env.DDDS_RANGE_EVIDENCE||'/tmp/ddds-aligned-range-e2e';
const TIME_TOLERANCE=2*3600*1000;
(async()=>{
 fs.mkdirSync(OUT,{recursive:true});
 const browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
 const page=await browser.newPage({viewport:{width:1710,height:1010},locale:'ko-KR'});
 const errors=[];page.on('pageerror',e=>errors.push(e.message.slice(0,450)));
 try {
  let res=await page.goto(BASE+'/compare/'+encodeURIComponent(ID),{waitUntil:'domcontentloaded',timeout:60000});
  if(res?.status()!==200)throw Error('COMPARE_HTTP_NOT_200');
  const root=page.getByTestId('ddds-shared-chart-comparison');
  await root.waitFor({timeout:60000});
  await page.waitForFunction(()=>{
    const e=document.querySelector('[data-testid="ddds-same-bar-status"]');
    return e?.textContent?.includes('300/300')||document.body.innerText.includes('Python 자동 실행 실패:');
  },{timeout:160000});
  const stat=await page.getByTestId('ddds-same-bar-status').innerText();
  if(!stat.includes('300/300'))throw Error('PYTHON_NOT_RUNNING_ON_SAME_BARS '+stat);
  await page.getByTestId('ddds-python-chart').waitFor();
  const identity=(await page.getByTestId('ddds-shared-symbol-timeframe').innerText()).trim();
  if(!identity.includes('NASDAQ:AMZN')||!identity.includes('2시간봉'))throw Error('SYMBOL_OR_TIMEFRAME_NOT_PINNED '+identity);
  async function realRenderedRanges(expectedCount){
    try{
    await page.waitForFunction(tolerance=>{
      const vela=document.querySelector('.ddds-shared-compare .native-pine-chart');
      const py=document.querySelector('[data-testid="ddds-python-chart"]');
      const sync=document.querySelector('[data-testid="ddds-viewport-sync"]');
      const a=Number(vela?.dataset.visibleFrom), b=Number(vela?.dataset.visibleTo);
      const c=Number(py?.dataset.visibleFrom), d=Number(py?.dataset.visibleTo);
      return !!a&&!!b&&!!c&&!!d&&a<b&&c<d&&
        Math.abs(a-c)<=tolerance&&Math.abs(b-d)<=tolerance&&
        sync?.textContent?.includes('양쪽 차트 날짜 동기화 확인');
    },TIME_TOLERANCE,{timeout:12000});
    }catch(e){
      const diag=await page.evaluate(()=>{
        const v=document.querySelector('.ddds-shared-compare .native-pine-chart');
        const p=document.querySelector('[data-testid="ddds-python-chart"]');
        return {selector:document.querySelector('[data-testid="ddds-visible-bars-select"]')?.value,
          vela:{from:v?.dataset.visibleFrom,to:v?.dataset.visibleTo},
          python:{from:p?.dataset.visibleFrom,to:p?.dataset.visibleTo},
          shown:document.querySelector('[data-testid="ddds-visible-interval"]')?.textContent,
          sync:document.querySelector('[data-testid="ddds-viewport-sync"]')?.textContent,
          computed:document.querySelector('[data-testid="ddds-visible-plot-stats"]')?.textContent,
          pageErrors:document.querySelectorAll('.native-pine-error').length};
      });
      console.log('DDDS_VISIBLE_RANGE_DIAGNOSTIC '+expectedCount+' '+JSON.stringify(diag));
      await page.screenshot({path:path.join(OUT,'failed-date-sync-'+expectedCount+'.png'),fullPage:true});
      fs.writeFileSync(path.join(OUT,'failed-date-sync-'+expectedCount+'.json'),JSON.stringify(diag,null,2));
      throw e;
    }
    const actual=await page.evaluate(()=>{
      const l=document.querySelector('.ddds-shared-compare .native-pine-chart');
      const r=document.querySelector('[data-testid="ddds-python-chart"]');
      const labels=[...document.querySelectorAll('.ddds-shared-compare .pine-compare-grid .panel p')].map(x=>x.textContent?.trim());
      const range=document.querySelector('[data-testid="ddds-visible-interval"]')?.textContent?.trim();
      const s=document.querySelector('[data-testid="ddds-visible-plot-stats"]')?.textContent?.trim();
      return {vela:{from:Number(l?.dataset.visibleFrom),to:Number(l?.dataset.visibleTo)},
        python:{from:Number(r?.dataset.visibleFrom),to:Number(r?.dataset.visibleTo)},
        labels,range,visiblePlotStats:s};
    });
    if(actual.labels.filter(x=>x?.includes('NASDAQ:AMZN')&&x.includes('120분')).length<2)
      throw Error('VISIBLE_LABELS_ARE_NOT_IDENTICAL '+JSON.stringify(actual.labels));
    if(!actual.range?.includes('UTC')||!actual.range.includes('실제 표시 날짜'))
      throw Error('VISIBLE_DATE_LABEL_MISSING '+actual.range);
    if(!actual.visiblePlotStats?.includes('불일치 0개'))
      throw Error('VISIBLE_PLOT_VALUES_DIFFER '+actual.visiblePlotStats);
    if(actual.vela.to<=actual.vela.from||Math.abs(actual.vela.from-actual.python.from)>TIME_TOLERANCE||
      Math.abs(actual.vela.to-actual.python.to)>TIME_TOLERANCE)
      throw Error('ACTUAL_RENDERER_VIEWPORT_DIFFERENT '+JSON.stringify(actual));
    console.log('LIVE_VELA_PYTHON_VIEWPORT_MATCH '+expectedCount+' '+JSON.stringify(actual));
    return actual;
  }
  const first=await realRenderedRanges(80);
  const selector=page.getByTestId('ddds-visible-bars-select');
  const windows=[];
  for(const count of [40,120,300,80]){
    await selector.selectOption(String(count));
    const selection=await realRenderedRanges(count);
    windows.push({count,...selection});
    if(count===40&&selection.vela.from<=first.vela.from)
      throw Error('SELECT_40_DID_NOT_MOVE_START_FORWARD');
    if(count===300&&selection.vela.from>=first.vela.from)
      throw Error('SELECT_300_DID_NOT_MOVE_START_BACKWARD');
  }
  const chartArea=page.locator('.ddds-shared-compare .native-pine-chart');
  const bbox=await chartArea.boundingBox();
  if(!bbox)throw Error('NO_NATIVE_CHART_TO_PAN');
  const dragStart={x:bbox.x+bbox.width*.52,y:bbox.y+bbox.height*.55};
  await page.mouse.move(dragStart.x,dragStart.y);
  await page.mouse.down();
  await page.mouse.move(dragStart.x-bbox.width*.12,dragStart.y,{steps:12});
  await page.mouse.up();
  const dragged=await realRenderedRanges('native-pan');
  // A drag must keep Python aligned with the actual Vela renderer, not just
  // compare labels. The chart library may ignore drag in some modes; that
  // does not allow a mismatched viewport.
  await page.setViewportSize({width:944,height:900});
  await realRenderedRanges('responsive-944');
  const layout=await page.evaluate(()=>{
    const x=document.querySelector('.ddds-shared-compare .pine-compare-grid');
    const left=document.querySelector('.ddds-shared-compare .native-pine-chart');
    const right=document.querySelector('[data-testid="ddds-python-chart"]');
    return {columns:getComputedStyle(x).gridTemplateColumns.split(' ').length,
      leftWidth:left.getBoundingClientRect().width,rightWidth:right.getBoundingClientRect().width};
  });
  if(layout.columns!==1||layout.leftWidth<600||layout.rightWidth<600)
    throw Error('944_LAYOUT_DIFFERENT_OR_TOO_NARROW '+JSON.stringify(layout));
  if(errors.length)throw Error('BROWSER_JAVASCRIPT_ERRORS '+errors.join('|'));
  await page.screenshot({path:path.join(OUT,'ddds-944px-same-symbol-same-utc-view.png'),fullPage:true});
  await page.setViewportSize({width:1710,height:1010});
  await realRenderedRanges('wide');
  await page.screenshot({path:path.join(OUT,'ddds-wide-same-symbol-same-utc-view.png'),fullPage:true});
  const report={status:'REAL_DDDS_VISUAL_TIME_RANGE_ALIGNED',source_id:ID,
    symbol:'NASDAQ:AMZN',timeframe:'2h',input_bars:300,first,windows,dragged,layout,
    playwright_page_errors:errors};
  fs.writeFileSync(path.join(OUT,'verified-visible-range.json'),JSON.stringify(report,null,2));
  console.log('DDDS_ACTUAL_VISIBLE_RANGE_E2E_PASS '+JSON.stringify(report));
 }finally{await browser.close()}
})().catch(e=>{console.error('DDDS_VISIBLE_RANGE_E2E_FAIL',e);process.exitCode=1});
