/* Live Chromium validation: administration selected-only catalog -> real
 * original public React /scripts cards -> Pine source/detail -> SAME dataset
 * Vela Pine & generated Python chart. Never accepts a fake static screenshot.
 * The only optional mutation is explicitly publishing the already-proven DDDS
 * after server candidates returns publish_ready for exact immutable source.
 */
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path');
const BASE=process.env.VERIFIED_ADMIN_BASE||'https://investment-n8n-native-editor-production.up.railway.app';
const ID='PUB;5442675d418140c58486eb4a7ae12768';
const SHA='5a245e99447f13012dd026528235fc2c299cad5cb7b228653c684886dcba6507';
const OUT=process.env.VERIFIED_ADMIN_EVIDENCE||'/tmp/verified-admin-e2e';
async function json(response){let body;try{body=await response.json()}catch{body={error:(await response.text()).slice(0,500)}}return{status:response.status(),body}}
(async()=>{
 fs.mkdirSync(OUT,{recursive:true});
 const browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
 const context=await browser.newContext({viewport:{width:1700,height:1120},locale:'ko-KR',ignoreHTTPSErrors:false});
 const page=await context.newPage();
 const errors=[],failures=[];
 page.on('pageerror',e=>errors.push('PAGE '+e.message.slice(0,400)));
 page.on('requestfailed',r=>failures.push('NETWORK '+r.url()+' '+r.failure()?.errorText));
 const state={steps:[],errors,failures,base:BASE,source_id:ID};
 const snapshot=async name=>{try{await page.screenshot({path:path.join(OUT,name+'.png'),fullPage:true,timeout:15000})}catch(e){console.log('SCREENSHOT_ERROR',name,String(e))}};
 try{
   const adminResp=await page.goto(BASE+'/admin/index.html?section=verified',{waitUntil:'domcontentloaded',timeout:60000});
   if(adminResp.status()!==200)throw Error('ADMIN_HTTP_'+adminResp.status());
   await page.getByText('검증 완료 TradingView 전략', {exact:false}).first().waitFor({timeout:25000});
   state.steps.push('ADMIN_TAB_RENDERED');
   const candidates=await json(await context.request.get(BASE+'/api/investment/verified-scripts/candidates'));
   if(candidates.status!==200)throw Error('CANDIDATES_HTTP_'+JSON.stringify(candidates));
   const target=candidates.body.items?.find(x=>x.source_id===ID&&x.source_sha256===SHA);
   state.candidate={version_key:target?.version_key,rights_state:target?.rights_state,
     free_pyne_generated_stored:target?.free_pyne_generated_stored,publish_ready:target?.publish_ready,
     published:target?.published,reason:target?.reason};
   if(!target||!target.publish_ready)throw Error('ACTUAL_DDDS_SOURCE_NOT_VERIFIED_READY '+JSON.stringify(state.candidate));
   if(!target.published){
     // A real admin click (not a forged API request) makes the user's selected
     // verified DDDS accumulate. The endpoint itself checks immutable evidence.
     const button=page.locator('[data-action="verified-publish"][data-source="PUB;5442675d418140c58486eb4a7ae12768"]');
     await button.waitFor({timeout:20000});
     await button.click();
     await page.getByText('누적 목록 등록 완료').first().waitFor({timeout:35000});
     state.steps.push('ADMIN_SELECTED_APPROVED_DDDS_PUBLISHED');
   }else state.steps.push('EXACT_DDDS_ALREADY_PUBLISHED_IDEMPOTENT');
   const catalog=await json(await context.request.get(BASE+'/api/investment/verified-scripts/catalog?limit=100&offset=0'));
   if(catalog.status!==200||!catalog.body.published_only)throw Error('PUBLISHED_CATALOG_NOT_ONLY_VERIFIED '+JSON.stringify(catalog));
   const stored=catalog.body.items?.find(x=>x.script_id_part===ID&&x.source_hash===SHA);
   if(!stored||stored.numeric_points!==864||stored.numeric_mismatches!==0)
     throw Error('DDDS_NOT_PERSISTED_EXACT_IN_CATALOG '+JSON.stringify(stored));
   state.catalog={count:catalog.body.count,matched_ddds_id:stored.script_id_part,
      numeric_points:stored.numeric_points,pine_sha:stored.source_hash,python_sha:stored.python_sha256};
   state.steps.push('PERMANENT_VERIFIED_LIST_INCLUDES_DDDS');
   const iframe=page.frameLocator('#verified-strategies-frame');
   const card=iframe.locator('.script-card').filter({hasText:'Displaced Donchian'});
   await card.waitFor({timeout:45000});
   await snapshot('01-admin-verified-DDDS-list');
   await card.click();
   await iframe.getByText('Pine Script Source').first().waitFor({timeout:55000});
   const pine=await iframe.locator('pre.pine-code').innerText({timeout:20000});
   if(!pine.includes('//@version=6')||!pine.includes('strategy('))throw Error('ORIGINAL_PINE_SOURCE_NOT_REUSED');
   state.steps.push('SAME_ORIGINAL_SCRIPT_DETAIL_AND_PINE_SOURCE');
   await snapshot('02-original-DDDS-Pine-source-detail');
   await iframe.getByRole('button',{name:/원본 Pine.*Python 좌우 비교/}).click({timeout:15000});
   await iframe.locator('[data-testid="ddds-shared-chart-comparison"]').waitFor({timeout:60000});
   await page.waitForTimeout(1800);
   const innerFrame=page.frame({url: /\/verified\/index\.html/});
   if(!innerFrame)throw Error('ADMIN_SCRIPT_IFRAME_NOT_FOUND');
   await innerFrame.waitForFunction(()=>{
     const status=document.querySelector('[data-testid="ddds-same-bar-status"]')?.textContent||'';
     const compare=document.querySelector('[data-testid="ddds-visible-plot-stats"]')?.textContent||'';
     const sync=document.querySelector('[data-testid="ddds-viewport-sync"]')?.textContent||'';
     return status.includes('300/300')&&compare.includes('불일치 0개')&&sync.includes('양쪽 차트 날짜 동기화 확인');
   },null,{timeout:150000});
   const summary=await innerFrame.evaluate(()=>{
     const sel=q=>document.querySelector(q);
     const vala=sel('.ddds-shared-compare .native-pine-chart');
     const py=sel('[data-testid="ddds-python-chart"]');
     return {
       sameBar:sel('[data-testid="ddds-same-bar-status"]')?.textContent?.trim(),
       plot:sel('[data-testid="ddds-visible-plot-stats"]')?.textContent?.trim(),
       interval:sel('[data-testid="ddds-visible-interval"]')?.textContent?.trim(),
       symbol:sel('[data-testid="ddds-shared-symbol-timeframe"]')?.textContent?.trim(),
       vela:{from:vala?.dataset.visibleFrom,to:vala?.dataset.visibleTo},
       python:{from:py?.dataset.visibleFrom,to:py?.dataset.visibleTo},
     };
   });
   state.compare=summary;
   if(!summary.sameBar.includes('300/300')||!summary.symbol.includes('NASDAQ:AMZN')||
       !summary.symbol.includes('2시간봉')||
       Math.abs(Number(summary.vela.from)-Number(summary.python.from))>7200000||
       Math.abs(Number(summary.vela.to)-Number(summary.python.to))>7200000)
     throw Error('ADMIN_ACTUAL_DUAL_RENDERER_PROVENANCE_DIFFERENCE '+JSON.stringify(summary));
   state.steps.push('PINE_PYTHON_REAL_CHART_SAME_OHLCV_SAME_VISIBLE_UTC');
   await snapshot('03-admin-original-DDDS-Pine-Python-matched-300');
   // Regression: reloading does not erase the persistent approved catalog.
   await page.reload({waitUntil:'domcontentloaded',timeout:60000});
   await page.getByText('누적 목록 등록 완료').first().waitFor({timeout:35000});
   state.steps.push('PERSISTENT_CATALOG_SURVIVES_REFRESH');
   if(errors.length)throw Error('UNCAUGHT_JS_ERRORS '+errors.join(';'));
   state.success=true;
   fs.writeFileSync(path.join(OUT,'verified-admin-real-browser.json'),JSON.stringify(state,null,2));
   console.log('VERIFIED_ADMIN_REAL_BROWSER_E2E_PASS '+JSON.stringify(state));
 }catch(error){
   state.success=false;state.failure=String(error);
   try{state.currentUrl=page.url();state.body=(await page.locator('body').innerText({timeout:8000})).slice(0,2000)}catch{}
   await snapshot('FAILED-admin-verification');
   fs.writeFileSync(path.join(OUT,'verified-admin-real-browser.json'),JSON.stringify(state,null,2));
   console.error('VERIFIED_ADMIN_REAL_BROWSER_E2E_FAIL '+JSON.stringify(state));
   process.exitCode=1;
 }finally{await browser.close()}
})();
