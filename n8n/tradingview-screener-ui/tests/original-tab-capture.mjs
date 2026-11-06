import {chromium} from 'playwright';
import fs from 'node:fs/promises';
const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_SYSTEM_CHROME?{executablePath:process.env.PLAYWRIGHT_SYSTEM_CHROME}:{}),args:['--no-sandbox','--disable-dev-shm-usage']});
const pages=[
 {key:'coin',url:'https://kr.tradingview.com/crypto-coins-screener/'},
 {key:'cex',url:'https://kr.tradingview.com/cex-screener/'},
 {key:'dex',url:'https://kr.tradingview.com/dex-screener/'}
];
const report={captured:new Date().toISOString(),originalTabs:{}};
for(const p of pages){
 const tabRecords={};
 const pg=await browser.newPage({viewport:{width:1565,height:960},locale:'ko-KR'});
 let last=null,requests=[],statusCodes=[];
 pg.on('request',req=>{if(req.url().includes('/scan?')&&req.method()==='POST'){try{last=req.postDataJSON();requests.push({url:req.url(),payload:last});}catch{}}});
 pg.on('response',resp=>{if(resp.url().includes('/scan?'))statusCodes.push(resp.status());});
 try{
  await pg.goto(p.url,{waitUntil:'domcontentloaded',timeout:45000});
  await pg.waitForTimeout(2200);
  const tabs=pg.locator('button[role="tab"]');
  const length=await tabs.count();
  console.log('ORIGINAL TAB INVENTORY',p.key,length);
  for(let i=0;i<length;i++){
   const tab=tabs.nth(i),label=(await tab.innerText()).trim().slice(0,60);
   const before=requests.length;
   try{await tab.click({timeout:8000});await pg.waitForTimeout(1200);}catch(err){console.log('TAB CLICK FAILED',p.key,i,String(err).slice(0,130));}
   const recent=requests.at(-1);
   tabRecords[String(i)]={label,requestReceived:requests.length>before,columns:recent?.payload?.columns||null,sort:recent?.payload?.sort||null,filter2:recent?.payload?.filter2||null,scanURL:recent?.url||null,status:statusCodes.at(-1)||null};
   console.log('ORIGINAL TAB',p.key,i,label,'COLUMNS',JSON.stringify(tabRecords[String(i)].columns));
  }
 }catch(err){tabRecords.error=String(err).slice(0,400);console.log('ORIGINAL ERROR',p.key,tabRecords.error);}
 report.originalTabs[p.key]=tabRecords;await pg.close();
}
await browser.close();await fs.mkdir('artifacts',{recursive:true});
await fs.writeFile('artifacts/original-crypto-tab-columns.json',JSON.stringify(report,null,2));
console.log('ORIGINAL TAB FINAL '+JSON.stringify({tabs:Object.fromEntries(Object.entries(report.originalTabs).map(([k,v])=>[k,Object.keys(v).length]))}));
