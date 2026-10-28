import {createRequire} from 'node:module';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const require=createRequire(new URL('../../investment_studio/package.json',import.meta.url));
const {chromium,expect}=require('@playwright/test');
const base=process.env.STOCK_SHARED_URL||'http://127.0.0.1:39089/';
const artifacts=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'artifacts');
await fs.mkdir(artifacts,{recursive:true});
const report={url:base,test:'shared-editor-stock-integration',checks:[]};
const pass=(name,extra={})=>{report.checks.push({name,status:'PASS',...extra});console.log('STOCK_SHARED_EDITOR_PASS',name,JSON.stringify(extra));};
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1790,height:1120},acceptDownloads:true});
try{
 await page.goto(base,{waitUntil:'domcontentloaded',timeout:60000});
 await expect(page.getByText('Shared n8n Studio',{exact:true}).first()).toBeVisible();
 await expect(page.getByText('투자 자동화 · 공통 편집기')).toBeVisible();
 const buttons=page.locator('button[data-stock-flow]');
 await expect(buttons).toHaveCount(13,{timeout:20000});
 await expect(page.locator('.vue-flow__node')).toHaveCount(5,{timeout:25000});
 await expect(page.locator('.vue-flow__edge')).toHaveCount(4,{timeout:20000});
 pass('shared_not_legacy_iframe',{flows:13,nodes:5,edges:4});
 if(await page.locator('iframe#n8n-canvas').count())throw Error('legacy iframe remains in shared UI');
 const originalIdList=await page.locator('.vue-flow__node').evaluateAll(els=>els.map(el=>el.getAttribute('data-id')));
 if(!originalIdList.includes('aiOperationF01post'))throw Error('Original F01 n8n node IDs not loaded '+JSON.stringify(originalIdList));
 pass('real_workflow_original_node_ids',{originalIdList});
 // All 13 real stock workflows: validate exact original native node identities,
 // not just counts. No synthetic template may substitute the real graph.
 for(let i=0;i<13;i++){
   const button=buttons.nth(i);
   const file=await button.getAttribute('data-stock-flow');
   const response=await page.request.get(new URL('stock-workflows/'+file,base).href);
   if(!response.ok())throw Error('Missing original workflow '+file);
   const raw=await response.json();
   await button.click();
   await expect(page.locator('.vue-flow__node')).toHaveCount(raw.nodes.length,{timeout:12000});
   const actual=await page.locator('.vue-flow__node').evaluateAll(els=>els.map(el=>el.getAttribute('data-id')).sort());
   const expected=raw.nodes.map(n=>n.id).sort();
   await expect.poll(async()=>await page.locator('.vue-flow__node').evaluateAll(els=>els.map(el=>el.getAttribute('data-id')).sort()),{timeout:12000}).toEqual(expected);
 }
 pass('all_13_original_stock_workflows',{flows:13});
 await buttons.first().click();
 await expect(page.locator('.vue-flow__node')).toHaveCount(5,{timeout:12000});
 // The shared editor fits the view with a 150ms animation after loading.
 // Settle before evaluating user gesture deltas in the REAL remote browser.
 await page.waitForTimeout(1100);
 // Choose a verified EMPTY canvas point. A fixed percentage can overlap
 // a node after the browser restores a saved viewport on a real deployment.
 const getTransform=async()=>page.locator('.vue-flow__transformationpane').evaluate(el=>{
   const m=new DOMMatrixReadOnly(getComputedStyle(el).transform);
   return {x:m.m41,y:m.m42};
 });
 const blank=await page.evaluate(()=>{
   const pane=document.querySelector('.vue-flow__pane');
   if(!pane)throw Error('Missing real Vue Flow pane');
   const b=pane.getBoundingClientRect();
   for(const [fx,fy] of [[.58,.80],[.42,.76],[.72,.64],[.3,.6],[.48,.48],[.2,.8]]){
     const x=b.left+b.width*fx,y=b.top+b.height*fy;
     const el=document.elementFromPoint(x,y);
     if(el&&el.closest('.vue-flow__pane')&&!el.closest('.vue-flow__node,.vue-flow__controls,.vue-flow__minimap,.canvas-watermark,.canvas-controls-hint,.vue-flow__edge'))return {x,y,element:el.className?.baseVal||el.className};
   }
   throw Error('No safe blank canvas coordinate found in actual browser');
 });
 const beforePan=await getTransform();
 await page.mouse.move(blank.x,blank.y);
 await page.mouse.down();
 await page.mouse.move(blank.x+135,blank.y-55,{steps:24});
 await page.mouse.up();
 await expect.poll(async()=>await getTransform(),{timeout:12000,intervals:[200,500,1000]}).toMatchObject({x:expect.any(Number),y:expect.any(Number)});
 const afterPan=await getTransform();
 if(afterPan.x-beforePan.x<65||afterPan.y-beforePan.y>-20)throw Error('Blank pan did not move correctly: '+JSON.stringify({blank,beforePan,afterPan}));
 pass('canvas_left_blank_pan',{blank,beforePan,afterPan});
 await page.getByRole('button',{name:'확대',exact:true}).first().click();
 const zoomed=await page.locator('.vue-flow__node').first().boundingBox();
 await page.getByRole('button',{name:/Fit/}).click();
 pass('zoom_and_fit',{zoomedWidth:zoomed.width});
 await buttons.nth(3).click();
 await expect(page.locator('.vue-flow__node')).toHaveCount(6,{timeout:25000});
 await expect(page.locator('.vue-flow__edge')).toHaveCount(5,{timeout:25000});
 const ids=await page.locator('.vue-flow__node').evaluateAll(els=>els.map(el=>el.getAttribute('data-id')));
 if(!ids.includes('webhook-1')||!ids.includes('manual-01'))throw Error('S01 original node identities missing');
 pass('S01_original_nodes_edges',{nodes:6,edges:5});
 const original=page.locator('.vue-flow__node[data-id="webhook-1"]');
 await original.click();
 const inspector=page.getByRole('textbox',{name:'노드 이름'});
 await inspector.fill('시나리오 Webhook 접수 테스트');
 await inspector.blur();
 await expect(original).toContainText('시나리오 Webhook 접수 테스트');
 await page.getByRole('button',{name:'서버 저장'}).click();
 await expect(page.getByText(/서버 DB 저장 성공/)).toBeVisible({timeout:15000});
 const apiPath=new URL('api/studio/workflows/scenarios/01-new-strategy.json',base).href;
 const savedResponse=await page.request.get(apiPath);
 if(!savedResponse.ok())throw Error('Shared SQLite API unavailable: '+savedResponse.status());
 const savedRemote=await savedResponse.json();
 if(savedRemote.version!==1||savedRemote.source!=='server'||!savedRemote.workflow.nodes.some(n=>n.id==='webhook-1'&&n.name==='시나리오 Webhook 접수 테스트'))throw Error('Actual server DB did not persist edited native JSON');
 pass('n8n_workflow_server_db_saved',{version:savedRemote.version,nodeName:'시나리오 Webhook 접수 테스트'});
 const stale=await page.request.put(apiPath,{data:{workflow:savedRemote.workflow,expectedVersion:0},headers:{'Content-Type':'application/json'}});
 if(stale.status()!==409)throw Error('Concurrent stale version should be refused, got HTTP '+stale.status());
 pass('server_version_conflict_protection',{http:409});
 const historyResponse=await page.request.get(apiPath+'/versions');
 const history=await historyResponse.json();
 if(history.versions?.[0]?.version!==1)throw Error('Version history not recorded');
 pass('server_revision_history',{versions:history.versions.length});
 const healthResponse=await page.request.get(new URL('api/studio/health',base).href);
 const health=await healthResponse.json();
 if(health.executionEnabled!==false||health.storage!=='sqlite')throw Error('Unsafe execution flag detected');
 pass('safe_no_execution_or_broker',{executionEnabled:false});
 const beforeReload=await page.evaluate(()=>({url:location.href,selected:localStorage.getItem('shared-n8n-studio:investment:selected'),keys:Object.keys(localStorage).filter(x=>x.includes('investment')),count:JSON.parse(localStorage.getItem('shared-n8n-studio:investment:v1:scenarios/01-new-strategy.json')||'{}')?.nodes?.length}));
 console.log('SHARED_STOCK_RELOAD_BEFORE',JSON.stringify(beforeReload));
 await page.reload({waitUntil:'domcontentloaded'});
 await page.waitForTimeout(1200);
 const afterReload=await page.evaluate(()=>({url:location.href,selected:localStorage.getItem('shared-n8n-studio:investment:selected'),keys:Object.keys(localStorage).filter(x=>x.includes('investment')),count:JSON.parse(localStorage.getItem('shared-n8n-studio:investment:v1:scenarios/01-new-strategy.json')||'{}')?.nodes?.length,active:[...document.querySelectorAll('[data-stock-flow].active')].map(x=>x.getAttribute('data-stock-flow')),status:document.querySelector('.bottom-status')?.textContent,nodes:document.querySelectorAll('.vue-flow__node').length}));
 console.log('SHARED_STOCK_RELOAD_AFTER',JSON.stringify(afterReload));
 await expect(page.locator('.vue-flow__node')).toHaveCount(6,{timeout:25000});
 await expect(page.locator('.vue-flow__node[data-id="webhook-1"]')).toContainText('시나리오 Webhook 접수 테스트');
 const remoteAfterReload=await page.request.get(apiPath);
 const afterJson=await remoteAfterReload.json();
 if(afterJson.version!==1||afterJson.workflow.nodes.find(n=>n.id==='webhook-1')?.name!=='시나리오 Webhook 접수 테스트')throw Error('Server DB reload lost saved node');
 pass('stock_server_db_reload_restore',{persistedName:true,version:afterJson.version});
 // Real Chrome version history: change again, save as v2, then restore v1
 // through the common editor's user-visible history controls as v3.
 const historyBefore=page.locator('[data-testid="stock-version-history"]');
 await expect(historyBefore.locator('[data-restore-version="1"]')).toBeVisible({timeout:15000});
 const n=page.locator('.vue-flow__node[data-id="webhook-1"]');
 await n.click();
 const rename=page.getByRole('textbox',{name:'노드 이름'});
 await rename.fill('두 번째 수정 버전');
 await rename.blur();
 await page.getByRole('button',{name:'서버 저장'}).click();
 await expect(page.getByText(/서버 DB 저장 성공 · v2/)).toBeVisible({timeout:15000});
 await expect(historyBefore.locator('[data-restore-version="2"]')).toBeVisible({timeout:10000});
 page.once('dialog',d=>d.accept());
 await historyBefore.locator('[data-restore-version="1"]').click();
 await expect(page.locator('.vue-flow__node[data-id="webhook-1"]')).toContainText('시나리오 Webhook 접수 테스트',{timeout:22000});
 await expect(page.getByText(/이전 버전 v1을 서버 v3으로 복원했습니다/)).toBeVisible({timeout:12000});
 const restoredRes=await page.request.get(apiPath);
 const restored=await restoredRes.json();
 if(restored.version!==3||restored.workflow.nodes.find(n=>n.id==='webhook-1')?.name!=='시나리오 Webhook 접수 테스트')throw Error('Historical server revision was not restored as a new current version');
 pass('shared_history_ui_restores_as_new_version',{restoredFrom:1,currentVersion:3});
 // Imported result is a SYNTHETIC E2E fixture with the genuine official n8n
 // execution resultData.runData shape. This does not perform an engine run.
 const resultFile={
   id:'synthetic-inspector-test-1',status:'error',finished:false,
   data:{resultData:{runData:{
     [restored.workflow.nodes[0].name]:[{startTime:1000,executionTime:3,data:{main:[[{json:{password:'synthetic-secret',ok:true}}]]}}],
     [restored.workflow.nodes[1].name]:[{startTime:1005,executionTime:8,error:{message:'Synthetic n8n node failure',headers:{authorization:'Bearer TEST_SECRET'}},data:{main:[]}}]
   }}}
 };
 await page.locator('input[aria-label="n8n 실행 JSON 파일"]').setInputFiles({
   name:'synthetic-n8n-execution-fixture.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(resultFile))
 });
 await expect(page.locator('[data-testid="imported-run-status"]')).toContainText('error',{timeout:12000});
 await expect(page.locator('.node-status-dot.error')).toHaveCount(1);
 const failedNode=page.locator('.vue-flow__node[data-id="'+restored.workflow.nodes[1].id+'"]');
 await failedNode.click();
 const inspectorPanel=page.locator('[data-testid="n8n-node-execution-inspector"]');
 await expect(inspectorPanel).toContainText('Synthetic n8n node failure');
 await expect(inspectorPanel).not.toContainText('TEST_SECRET');
 const successNode=page.locator('.vue-flow__node[data-id="'+restored.workflow.nodes[0].id+'"]');
 await successNode.click();
 await expect(inspectorPanel).toContainText('[REDACTED]');
 await expect(inspectorPanel).not.toContainText('synthetic-secret');
 pass('imported_n8n_run_per_node_status_error_output_and_redaction',{nodes:2,source:'synthetic_e2e_fixture'});
 await page.reload({waitUntil:'domcontentloaded'});
 await expect(page.locator('.vue-flow__node')).toHaveCount(6,{timeout:20000});
 await expect(page.locator('[data-testid="n8n-execution-file-panel"]')).toContainText('공식 n8n에서 내보낸 실행 JSON');
 await expect(page.locator('.node-status-dot.error')).toHaveCount(0);
 pass('uploaded_execution_not_persisted_as_authoritative_run');
 const downloading=page.waitForEvent('download',{timeout:18000});
 await page.locator('button[title="JSON 내보내기"]').click();
 await page.waitForTimeout(550);
 const exportStatus=await page.locator('.bottom-status').innerText();
 console.log('STOCK_SHARED_EXPORT_DEBUG',JSON.stringify({exportStatus,buttons:await page.getByRole('button',{name:/JSON/}).allTextContents(),href:page.url()}));
 if(/실패|오류/.test(exportStatus))throw Error('JSON export actual UI error: '+exportStatus);
 const download=await downloading;
 const raw=JSON.parse(await fs.readFile(await download.path(),'utf-8'));
 if(raw.nodes?.length!==6||raw.nodes[0]?.type!=='n8n-nodes-base.webhook'||!raw.connections?.['시나리오 Webhook 접수 테스트'])throw Error('Original n8n graph roundtrip failed');
 pass('n8n_original_json_export',{nodes:raw.nodes.length,originalType:raw.nodes[0].type});
 await page.screenshot({path:path.join(artifacts,'stock-shared-editor-final.png'),fullPage:true});
 console.log('STOCK_SHARED_EDITOR_ALL_PASS');
}catch(e){report.error=String(e?.stack||e);process.exitCode=1;console.error(report.error);await page.screenshot({path:path.join(artifacts,'stock-shared-editor-failure.png'),fullPage:true}).catch(()=>{});}
finally{await fs.writeFile(path.join(artifacts,'stock-shared-editor-results.json'),JSON.stringify(report,null,2));await browser.close();}
