// Read-only inventory regression on the actual upstream n8n Vue canvas, not a replacement graph.
import { createRequire } from 'node:module';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const require=createRequire(new URL('../../investment_studio/package.json',import.meta.url));
const {chromium,expect}=require('@playwright/test');
const base=process.env.N8N_PAN_GATEWAY_URL || 'http://127.0.0.1:39087/';
if(!/^http:\/\/127\.0\.0\.1:39087\/?$/.test(base))throw Error('Only 127.0.0.1:39087 sandbox allowed');
const dir=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'artifacts');await fs.mkdir(dir,{recursive:true});
const report={app:'official n8n upstream 2.44.5 Vue',flows:[],timestamp:new Date().toISOString()};
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1700,height:1000}});
let bad=false;
try{
 await page.goto(base,{waitUntil:'domcontentloaded',timeout:45000});
 await expect(page.locator('button.flow')).toHaveCount(13,{timeout:40000});
 const frame=page.frameLocator('#n8n-canvas');
 for(let i=0;i<13;i++){
   const button=page.locator('button.flow').nth(i);
   const file=await button.getAttribute('data-workflow');
   if(!file)throw Error('Flow index '+i+' missing file mapping');
   const resp=await page.request.get(new URL('demo-data/'+file,base).href,{timeout:15000});
   if(!resp.ok())throw Error('Flow JSON fetch failed '+file+' HTTP '+resp.status());
   const json=await resp.json();
   const expectedNodes=json.nodes?.length||0;
   const expectedEdges=Object.values(json.connections||{}).reduce((total,outputs)=>total+Object.values(outputs).reduce((n,ports)=>n+(Array.isArray(ports)?ports.reduce((m,p)=>m+(Array.isArray(p)?p.length:0),0):0),0),0);
   await button.click();
   await expect(frame.locator('.vue-flow__node')).toHaveCount(expectedNodes,{timeout:30000});
   await expect(frame.locator('.vue-flow__edge')).toHaveCount(expectedEdges,{timeout:30000});
   const row={index:i+1,file,nodes:expectedNodes,edges:expectedEdges,status:'PASS'};
   report.flows.push(row);console.log('OFFICIAL_N8N_FLOW',JSON.stringify(row));
 }
 await page.screenshot({path:path.join(dir,'13-original-n8n-workflows.png'),fullPage:true});
 console.log('PASS_ALL_13_REAL_N8N_WORKFLOW_GRAPHS',report.flows.length);
}catch(e){bad=true;report.error=String(e?.stack||e);console.error(report.error);await page.screenshot({path:path.join(dir,'13-flow-failure.png'),fullPage:true}).catch(()=>{});}
finally{await fs.writeFile(path.join(dir,'all-13-workflows-results.json'),JSON.stringify(report,null,2));await browser.close();if(bad)process.exitCode=1;}
