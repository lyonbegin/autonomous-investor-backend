/* Browser-only inspection of official TradingView indicator/strategy UI.
 * Collect public, unauthenticated UI shape and transport method COUNTS.
 * Do not save cookies/tokens, websocket frame bodies, or private account data.
 */
const {chromium}=require('playwright');
const fs=require('fs');
const path=require('path');
const out=process.env.TV_STRATEGY_AUDIT_DIR||'/tmp/tv-strategy-audit';
fs.mkdirSync(out,{recursive:true});
const cleanUrl=s=>{try {const u=new URL(s);return u.origin+u.pathname;}catch{return 'invalid-url'}};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const pageSummary=async(page)=>{
 return await page.evaluate(()=>({
  title:document.title,
  buttons:[...document.querySelectorAll('button,[role=button]')].map(x=>({
   text:(x.innerText||x.getAttribute('aria-label')||x.title||'').replace(/\s+/g,' ').trim().slice(0,80),
   title:x.title||'',testid:x.getAttribute('data-name')||''
  })).filter(x=>x.text).slice(0,180),
  inputs:[...document.querySelectorAll('input')].map(x=>({
    placeholder:x.placeholder,role:x.getAttribute('role'),
    ariaLabel:x.getAttribute('aria-label'),type:x.type
  })).slice(0,30),
  dialogTexts:[...document.querySelectorAll('[role=dialog], [data-name*=dialog], [class*=dialog]')].map(x=>(x.innerText||'').replace(/\s+/g,' ').slice(0,1500)).filter(Boolean).slice(0,12),
  bodyText:(document.body.innerText||'').replace(/\s+/g,' ').slice(0,2500)
 }));
};
async function stage(page,name,report) {
 report.stages.push({name,at:new Date().toISOString(),ui:await pageSummary(page),
  messageCounts:{...report.ws_methods},xhrPaths:Object.keys(report.httpPaths)});
 await page.screenshot({path:path.join(out,name+'.png'),timeout:10000});
 console.log('UI_STAGE',name,JSON.stringify({
  buttons:report.stages.at(-1).ui.buttons.map(x=>x.text).filter(x=>/indicator|strateg|test|cross|search|technical|script|tester/i.test(x)).slice(0,30),
  dialogs:report.stages.at(-1).ui.dialogTexts.slice(0,2),
  body:report.stages.at(-1).ui.bodyText.slice(0,600)
 }));
}
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
 const context=await browser.newContext({viewport:{width:1510,height:980},timezoneId:'Asia/Seoul',locale:'en-US'});
 const page=await context.newPage();page.setDefaultTimeout(7000);
 const report={started:new Date().toISOString(),url:'https://www.tradingview.com/chart/?symbol=NASDAQ%3AAAPL',
  stages:[],wsMethodsSent:{},ws_methods:{},httpPaths:{},wsConnections:[],errors:[],
  indicatorSelected:false,strategyPanelVisible:false,authWall:false,baseStudyCommands:0,status:'NOT_CHECKED'};
 function key(m,n){m[n]=(m[n]||0)+1}
 function parseMethods(payload,dest){
  if(typeof payload!=='string')return;
  for(const m of payload.matchAll(/"m"\s*:\s*"([^"]{1,80})"/g))key(dest,m[1]);
 }
 page.on('websocket',ws=>{
  if(!/\.tradingview\.com/.test(new URL(ws.url()).hostname))return;
  report.wsConnections.push(cleanUrl(ws.url()));
  ws.on('framereceived',e=>parseMethods(e.payload,report.ws_methods));
  ws.on('framesent',e=>parseMethods(e.payload,report.wsMethodsSent));
 });
 page.on('request',r=>{
  if(!/\.tradingview\.com/.test(new URL(r.url()).hostname))return;
  if(['xhr','fetch'].includes(r.resourceType()))key(report.httpPaths,r.method()+' '+cleanUrl(r.url()));
 });
 page.on('pageerror',e=>report.errors.push(String(e).slice(0,180)));
 try{
  const nav=await page.goto(report.url,{waitUntil:'domcontentloaded',timeout:45000});
  report.navigationStatus=nav?.status()||0;
  await sleep(8500);await stage(page,'01-chart-loaded',report);
  report.baseStudyCommands=report.wsMethodsSent.create_study||0;
  const indicatorButton=page.getByRole('button',{name:/Indicators, metrics, and strategies/}).filter({visible:true}).first();
  const indicator=(await indicatorButton.count())?indicatorButton:page.getByText('Indicators',{exact:true}).filter({visible:true}).first();
  if(await indicator.count()){
   await indicator.click({timeout:10000});
   await sleep(3000);
   await stage(page,'02-indicator-dialog',report);
   // Look for strategies in indicator library; menu state depends on guest entitlement.
   const strategies=page.getByText(/^Strategies$/).first();
   if(await strategies.count()){
    try {await strategies.click({timeout:5000});await sleep(2300);
     await stage(page,'03-strategies-tab',report);report.strategyPanelVisible=true;
     // Apply the real built-in strategy directly from the visible STRATEGIES
     // tab. Searching globally mixes strategies with user-made indicators.
     const builtin=page.getByText('Moving average crossover',{exact:true}).filter({visible:true}).first();
     if(await builtin.count()){
       const before=report.wsMethodsSent.create_study||0;
       try{
         await builtin.click({timeout:7000});await sleep(7500);
         report.indicatorSelected=(report.wsMethodsSent.create_study||0)>before;
         await stage(page,'04-builtin-strategy-clicked',report);
         try {await page.keyboard.press('Escape');await sleep(700);}catch{}
         await stage(page,'05-builtin-chart',report);
       }catch(e){report.errors.push('BUILTIN_STRATEGY:'+String(e).slice(0,260));}
     }
}
    catch(e){report.errors.push('STRATEGIES_CLICK:'+String(e).slice(0,180))}
   }
   if(!report.indicatorSelected){
   const inputs=page.locator('input[placeholder*="Search"],input[placeholder*="search"],input[role="searchbox"]');
   let input=null; if(await inputs.count())input=inputs.first();
   else if(await page.getByRole('textbox').count())input=page.getByRole('textbox').first();
   if(input){
    await input.fill('Moving Average Cross',{timeout:5000});
    await sleep(2500);await stage(page,'04-strategy-search',report);
    const candidates=page.getByText(/Moving Average Cross|Moving Average Crossover|MA Cross/i);
    report.strategySearchCandidates=await candidates.count();
    if(await candidates.count()){
      // Clicking exact public strategy result may be denied without a login.
      try {await candidates.last().click({timeout:6000});
       await sleep(6500);
       report.indicatorSelected=(report.wsMethodsSent.create_study||0)>report.baseStudyCommands;
       await stage(page,'05-selected-study',report);}
      catch(e){report.errors.push('ADD_STRATEGY:'+String(e).slice(0,170))}
    }
   }
   }
  } else report.errors.push('INDICATORS_BUTTON_MISSING');
  // Strategy Tester is present only if official chart has a strategy and user entitlement.
  const tester=page.getByText(/Strategy Tester|Strategy Report/i).first();
  if(await tester.count()){
   try {await tester.click({timeout:5000});await sleep(3500);await stage(page,'06-strategy-tester',report);}
   catch(e){report.errors.push('OPEN_TESTER:'+String(e).slice(0,220))}
  }
  const body=await page.locator('body').innerText();
  report.authWall=/Access over 100,000 trading indicators|You'll need a free account|Join for free|sign in to access/i.test(body);
  report.indicatorSelected=!report.authWall&&(report.wsMethodsSent.create_study||0)>report.baseStudyCommands;
  report.status=report.authWall?'AUTH_REQUIRED_TO_ADD_OFFICIAL_STRATEGY':
    report.indicatorSelected?'OFFICIAL_STRATEGY_REQUEST_OBSERVED':'OFFICIAL_STRATEGY_NOT_MOUNTED';
 }catch(e){
  report.errors.push('FATAL:'+String(e).slice(0,600));
 }finally{
  report.completed=new Date().toISOString();
  fs.writeFileSync(path.join(out,'strategy-ui-network.json'),JSON.stringify(report,null,2));
  console.log('TV_OFFICIAL_STRATEGY_INSPECTOR_RESULT',JSON.stringify({
   navigationStatus:report.navigationStatus,status:report.status,indicatorSelected:report.indicatorSelected,
   strategyPanelVisible:report.strategyPanelVisible,authWall:report.authWall,
   methodsSent:report.wsMethodsSent,methodsReceived:report.ws_methods,
   httpPaths:report.httpPaths,stages:report.stages.map(s=>s.name),errors:report.errors
  }));
  await context.close();await browser.close();
 }
})().catch(e=>{console.error(e);process.exit(1)});
