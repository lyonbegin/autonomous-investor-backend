// Isolated, authenticated *official n8n* editor and SQLite persistence E2E.
// Never target external URLs or production systems. Run only against 127.0.0.1.
import { createRequire } from 'node:module';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const require=createRequire(new URL('../../investment_studio/package.json', import.meta.url));
const {chromium,expect}=require('@playwright/test');
const {parse:parseFlatted}=require('flatted'); // n8n server uses flatted.stringify for execution.data
const base=process.env.N8N_AUTH_SANDBOX_URL || 'http://127.0.0.1:39088/';
if(!/^http:\/\/127\.0\.0\.1:39088\/?$/.test(base))throw Error('Only loopback:39088 ephemeral sandbox is allowed');
const dir=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'artifacts');
await fs.mkdir(dir,{recursive:true});
const log={target:base,checks:[],workflowId:null};
const record=(name,ok,details={})=>{const item={name,result:ok?'PASS':'FAIL',...details};log.checks.push(item);console.log('AUTHENTICATED_N8N_E2E',JSON.stringify(item));if(!ok)throw Error(name+' '+JSON.stringify(details));};
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1700,height:1050}});
const api=async(method,url,data)=>{
 const r=await page.request.fetch(new URL(url,base).href,{method,data,timeout:30000});
 const raw=await r.text();let json;try{json=JSON.parse(raw)}catch{json={raw:raw.slice(0,1000)}}
 if(!r.ok())throw Error(method+' '+url+' HTTP '+r.status()+': '+JSON.stringify(json).slice(0,800));
 return json.data ?? json;
};
const nodes=[
 {id:'ci-safe-trigger',name:'Safe Manual Trigger',type:'n8n-nodes-base.manualTrigger',typeVersion:1,position:[240,240],parameters:{}},
 {id:'ci-safe-noop',name:'Safe NoOp',type:'n8n-nodes-base.noOp',typeVersion:1,position:[620,240],parameters:{}},
];
const connections={'Safe Manual Trigger':{main:[[{node:'Safe NoOp',type:'main',index:0}]]}};
try{
 const settings=await api('GET','rest/settings');
 record('non_preview_authorized_sandbox',settings.previewMode!==true,{previewMode:settings.previewMode});
 await api('POST','rest/owner/setup',{email:'e2e-owner@example.test',firstName:'E2E',lastName:'Owner',password:'LocalOnly!NoRealCredential2026'});
 record('ephemeral_owner_initialized',true);
 const made=await api('POST','rest/workflows',{name:'SAFE CHROME TEST - NO EXTERNAL SERVICES',nodes,connections,settings:{executionOrder:'v1'},active:false});
 const id=made.id;record('synthetic_workflow_created',typeof id==='string'&&!!id,{id});
 log.workflowId=id;
 const read=await api('GET','rest/workflows/'+id);
 record('workflow_stored_in_server_db',read.nodes?.length===2&&read.connections?.['Safe Manual Trigger']?.main?.[0]?.[0]?.node==='Safe NoOp',{count:read.nodes?.length});
 await page.goto(new URL('workflow/'+id,base).href,{waitUntil:'domcontentloaded',timeout:60000});
 const native=page.locator('.vue-flow__node');
 await expect(native).toHaveCount(2,{timeout:90000});
 record('official_authenticated_vue_canvas',true,{nodes:await native.count()});
 const item=native.filter({hasText:'Safe NoOp'});
 await expect(item).toHaveCount(1);
 const before=await item.boundingBox();
 if(!before)throw Error('No native node box');
 await page.mouse.move(before.x+before.width/2,before.y+before.height/2);
 await page.mouse.down();
 await page.mouse.move(before.x+before.width/2+145,before.y+before.height/2+105,{steps:25});
 await page.mouse.up();
 const after=await item.boundingBox();
 record('native_node_mouse_drag',!!after&&Math.abs(after.x-before.x)>55&&Math.abs(after.y-before.y)>45,{before,after});
 const save=page.locator('[data-test-id="workflow-save-button"]');
 if(await save.isVisible().catch(()=>false)){
   await expect(save).toBeEnabled({timeout:15000});
   await save.click();
 }else{
   // Native UI supports save via keyboard when save button is not rendered.
   await page.keyboard.press('Control+s');
 }
 let remote;
 for(let attempt=0;attempt<30;attempt++){
   remote=await api('GET','rest/workflows/'+id);
   const pos=remote.nodes?.find(n=>n.id==='ci-safe-noop')?.position;
   if(pos&&Math.abs(pos[0]-620)>45&&Math.abs(pos[1]-240)>40)break;
   await page.waitForTimeout(700);
 }
 const updated=remote.nodes?.find(n=>n.id==='ci-safe-noop')?.position;
 record('native_server_save_persists_coordinates',!!updated&&Math.abs(updated[0]-620)>45&&Math.abs(updated[1]-240)>40,{position:updated});
 await page.screenshot({path:path.join(dir,'authenticated-n8n-before-reload.png'),fullPage:true});
 await page.reload({waitUntil:'domcontentloaded',timeout:60000});
 await expect(native).toHaveCount(2,{timeout:60000});
 const loaded=await api('GET','rest/workflows/'+id);
 const saved=loaded.nodes?.find(n=>n.id==='ci-safe-noop')?.position;
 record('server_db_reopen_retains_node_connections',JSON.stringify(saved)===JSON.stringify(updated)&&loaded.connections?.['Safe Manual Trigger']?.main?.[0]?.[0]?.node==='Safe NoOp',{saved});
 await page.screenshot({path:path.join(dir,'authenticated-n8n-after-reload.png'),fullPage:true});
 // Manual Trigger and NoOp only: zero external services/credentials.
 const result=await api('POST','rest/workflows/'+id+'/run',{triggerToStartFrom:{name:'Safe Manual Trigger'}});
 record('safe_real_n8n_run_started',typeof result?.executionId==='string'||typeof result?.executionId==='number'||typeof result?.waitingForWebhook==='boolean',{executionId:result?.executionId});
 if(result?.executionId){
   let detail;
   for(let attempt=0;attempt<35;attempt++){
     detail=await api('GET','rest/executions/'+result.executionId);
     if(['success','error','canceled','crashed','waiting'].includes(detail.status))break;
     await page.waitForTimeout(350);
   }
   record('n8n_execution_record_readable',!!detail?.id,{id:detail?.id,status:detail?.status});
   record('safe_manual_execution_completed',detail.status==='success'&&detail.finished===true,{status:detail.status,finished:detail.finished});
   const executionData=typeof detail.data==='string'?parseFlatted(detail.data):detail.data;
   const runData=executionData?.resultData?.runData||{};
   record('node_input_output_results_present',Array.isArray(runData['Safe Manual Trigger'])&&Array.isArray(runData['Safe NoOp']),{nodes:Object.keys(runData)});
 }
 record('no_live_trade_or_bid_nodes',loaded.nodes.every(n=>['n8n-nodes-base.manualTrigger','n8n-nodes-base.noOp'].includes(n.type)));
}catch(error){log.error=String(error?.stack||error);console.error(log.error);process.exitCode=1;await page.screenshot({path:path.join(dir,'authenticated-n8n-failure.png'),fullPage:true}).catch(()=>{});}
finally{await fs.writeFile(path.join(dir,'authenticated-db-results.json'),JSON.stringify(log,null,2));await browser.close();}
