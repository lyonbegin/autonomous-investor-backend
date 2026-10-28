// Real compiled upstream n8n Vue demo, NEVER the standalone VueFlow playground.
// Preview-only Pan regression; editable/server persistence has a separate hard gate.
import { createRequire } from 'node:module';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const require = createRequire(new URL('../../investment_studio/package.json', import.meta.url));
const { chromium, expect } = require('@playwright/test');
const base = process.env.N8N_PAN_GATEWAY_URL || 'http://127.0.0.1:39087/';
const dest = path.resolve(path.dirname(fileURLToPath(import.meta.url)), 'artifacts');
await fs.mkdir(dest,{recursive:true});
const report={target:base, official_n8n:true, note:'Read-only official Vue preview. No production credentials or execution.', results:{}};
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1800,height:1050},deviceScaleFactor:1});
const mark=(name,passed,data={})=>{report.results[name]={status:passed?'PASS':'FAIL',...data};console.log('OFFICIAL_N8N_CHROME',JSON.stringify({name,...report.results[name]}));if(!passed)throw Error(name+' FAILED '+JSON.stringify(data));};
const viewportState=async frame=>frame.evaluate(()=>{
  const v=document.querySelector('.vue-flow__viewport');
  if(!v)throw Error('Missing official VueFlow viewport');
  const css=getComputedStyle(v).transform;
  const m=new DOMMatrix(css==='none'?'matrix(1,0,0,1,0,0)':css);
  return {x:m.m41,y:m.m42,zoom:m.a,css};
});
const blank=async(frame,iframe)=>{
  const inside=await frame.evaluate(()=>{
    const p=document.querySelector('.vue-flow__pane');
    if(!p)throw Error('Official pane missing');
    const b=p.getBoundingClientRect();
    for(const [rx,ry] of [[.85,.78],[.75,.85],[.9,.65],[.1,.85],[.9,.35],[.5,.9],[.1,.1]]){
      const x=b.left+b.width*rx,y=b.top+b.height*ry;
      const el=document.elementFromPoint(x,y);
      if(el?.closest('.vue-flow__pane')&&!el.closest('.vue-flow__node,.vue-flow__edge,.vue-flow__handle,.vue-flow__controls'))return {x,y};
    }
    throw Error('No empty pane position found');
  });
  const outer=await iframe.boundingBox();
  if(!outer)throw Error('Iframe not visible');
  return {x:outer.x+inside.x,y:outer.y+inside.y};
};
async function drag(a,b,button='left'){
  await page.mouse.move(a.x,a.y);await page.mouse.down({button});
  await page.mouse.move(b.x,b.y,{steps:18});await page.mouse.up({button});
  await page.waitForTimeout(450);
}
try{
  const settings=await page.request.get(new URL('rest/settings',base).toString(),{timeout:20000});
  mark('sandbox_settings_available',settings.status()===200,{status:settings.status()});
  const json=await settings.json();
  mark('n8n_preview_mode',json?.data?.previewMode===true,{previewMode:json?.data?.previewMode});
  await page.goto(base,{waitUntil:'domcontentloaded',timeout:45000});
  await expect(page.locator('button.flow')).toHaveCount(13,{timeout:45000});
  await page.locator('button.flow').nth(3).click();
  const iframe=page.locator('#n8n-canvas'), inner=page.frameLocator('#n8n-canvas');
  const nodes=inner.locator('.vue-flow__node'),edges=inner.locator('.vue-flow__edge');
  await expect(nodes).toHaveCount(6,{timeout:90000});
  await expect(edges).toHaveCount(5,{timeout:30000});
  mark('original_s01_nodes_edges',true,{nodes:await nodes.count(),edges:await edges.count()});
  const frame=page.frames().find(f=>f.url().includes('/workflows/demo'));
  if(!frame)throw Error('Original n8n editor iframe missing');
  mark('actual_editable_official_preview',frame.url().includes('editable=true'),{url:frame.url()});
  const initialNodeStyles=await nodes.evaluateAll(all=>all.map(x=>x.getAttribute('style')));
  const probe=async()=>frame.evaluate(()=>{
    const els=[...document.querySelectorAll('.vue-flow__viewport,.vue-flow__pane,.vue-flow,.vue-flow__transformationpane')];
    const root=document.querySelector('[data-test-id="canvas"]');
    return {url:location.href, rootClass:root?.className, elements:els.slice(0,15).map(el=>({tag:el.tagName,cls:typeof el.className==='string'?el.className:String(el.className?.baseVal),style:el.getAttribute('style'),transform:getComputedStyle(el).transform,pointerEvents:getComputedStyle(el).pointerEvents,bounds:el.getBoundingClientRect().toJSON()})),events:window.__panProbeEvents||[]};
  });
  await frame.evaluate(()=>{
    window.__panProbeEvents=[];
    for(const kind of ['pointerdown','mousedown','mousemove','pointermove','mouseup']){
      document.addEventListener(kind,e=>{
        if(window.__panProbeEvents.length>=32)return;
        window.__panProbeEvents.push({kind,button:e.button,target:e.target?.className?.baseVal||e.target?.className||e.target?.tagName,x:e.clientX,y:e.clientY,shift:e.shiftKey});
      },{capture:true,passive:true});
    }
  });
  const start=await viewportState(frame);
  const beforeProbe=await probe();
  const at=await blank(frame,iframe);
  await drag(at,{x:at.x+155,y:at.y+105});
  const afterLeft=await viewportState(frame);
  const afterProbe=await probe();
  console.log('OFFICIAL_N8N_PAN_DEBUG',JSON.stringify({at,start,afterLeft,beforeProbe,afterProbe}).slice(0,18000));
  report.panProbe={at,start,afterLeft,beforeProbe,afterProbe};
  mark('left_blank_pan',Math.abs(afterLeft.x-start.x)>25&&Math.abs(afterLeft.y-start.y)>20,{start,after:afterLeft});
  const afterNodeStyles=await nodes.evaluateAll(all=>all.map(x=>x.getAttribute('style')));
  mark('pan_does_not_edit_node_coordinates',JSON.stringify(initialNodeStyles)===JSON.stringify(afterNodeStyles));
  await page.screenshot({path:path.join(dest,'official-n8n-left-pan.png'),fullPage:true});
  const at2=await blank(frame,iframe),beforeMiddle=await viewportState(frame);
  await drag(at2,{x:at2.x-85,y:at2.y-65},'middle');
  const afterMiddle=await viewportState(frame);
  mark('middle_blank_pan',Math.abs(afterMiddle.x-beforeMiddle.x)>20&&Math.abs(afterMiddle.y-beforeMiddle.y)>15,{before:beforeMiddle,after:afterMiddle});
  const at3=await blank(frame,iframe),beforeShift=await viewportState(frame);
  await page.keyboard.down('Shift');
  try{await drag(at3,{x:at3.x-70,y:at3.y-40});}finally{await page.keyboard.up('Shift');}
  const afterShift=await viewportState(frame);
  mark('shift_marquee_does_not_pan',Math.abs(afterShift.x-beforeShift.x)<4&&Math.abs(afterShift.y-beforeShift.y)<4,{before:beforeShift,after:afterShift});
  const beforeZoom=await viewportState(frame);
  const at4=await blank(frame,iframe);await page.mouse.move(at4.x,at4.y);
  await page.keyboard.down('Control');
  try{await page.mouse.wheel(0,-550);}finally{await page.keyboard.up('Control');}
  await page.waitForTimeout(650);
  const afterZoom=await viewportState(frame);
  mark('ctrl_wheel_zoom',Math.abs(afterZoom.zoom-beforeZoom.zoom)>.015,{before:beforeZoom,after:afterZoom});
  mark('graph_kept_after_pan_zoom',(await nodes.count())===6&&(await edges.count())===5);
  // User gestures on native n8n: verify nodes move independently of viewport.
  const node=nodes.filter({hasText:'시나리오 Webhook 접수'});
  await expect(node).toHaveCount(1);
  const beforeStyle=await node.getAttribute('style');
  const box=await node.boundingBox();
  if(!box)throw Error('Native node has no DOM bounding box');
  const nodeStart={x:box.x+box.width/2,y:box.y+box.height/2};
  const beforeNodeDragViewport=await viewportState(frame);
  await drag(nodeStart,{x:nodeStart.x+112,y:nodeStart.y+76});
  const afterStyle=await node.getAttribute('style');
  const afterNodeDragViewport=await viewportState(frame);
  mark('native_node_drag',beforeStyle!==afterStyle,{beforeStyle,afterStyle});
  mark('node_drag_does_not_pan',Math.abs(afterNodeDragViewport.x-beforeNodeDragViewport.x)<3&&Math.abs(afterNodeDragViewport.y-beforeNodeDragViewport.y)<3);
  // Test only: official native NoOp creator, browser-local saved snapshot.
  await page.locator('#addSafeNoOp').click();
  await expect(nodes).toHaveCount(7,{timeout:30000});
  mark('native_add_noop',true,{nodes:await nodes.count()});
  await page.locator('#saveDraft').click();
  await expect(page.locator('#status')).toContainText('초안 저장 성공',{timeout:18000});
  const draftKey='n8n-native-editable-test:v1:scenarios/01-new-strategy.json';
  const snapshot=await page.evaluate(key=>JSON.parse(localStorage.getItem(key)||'null'),draftKey);
  mark('native_local_snapshot',snapshot?.nodes?.length===7&&snapshot.nodes.some(n=>n.type==='n8n-nodes-base.noOp'),{nodes:snapshot?.nodes?.length});
  await page.reload({waitUntil:'domcontentloaded'});
  await expect(page.locator('#status')).toContainText('저장된 초안 복원',{timeout:70000});
  await expect(nodes).toHaveCount(7,{timeout:70000});
  mark('native_reload_restore',true,{nodes:await nodes.count()});
  await page.evaluate(key=>localStorage.removeItem(key),draftKey);

  report.results['node_edit_server_save']={status:'NOT_TESTED',reason:'Local snapshot only; authenticated n8n server DB is a separate gate'};
  report.results['actual_node_execution']={status:'NOT_TESTED',reason:'No execution permitted on preview'};
  await page.screenshot({path:path.join(dest,'official-n8n-post-zoom.png'),fullPage:true});
  console.log('OFFICIAL_N8N_PAN_PREVIEW_PASS');
}catch(e){report.error=String(e?.stack||e);console.error(report.error);process.exitCode=1;await page.screenshot({path:path.join(dest,'official-n8n-failure.png'),fullPage:true}).catch(()=>{});}
finally{await fs.writeFile(path.join(dest,'official-pan-results.json'),JSON.stringify(report,null,2));await browser.close();}
