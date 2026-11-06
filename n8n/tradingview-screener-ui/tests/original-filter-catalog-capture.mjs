import {chromium} from 'playwright';
import fs from 'node:fs/promises';
const SITES=[
 ['stock','/screener/',['보안 정보','마켓 데이터','테크니컬즈','파이낸셜','평가','성장','마진','배당']],
 ['etf','/etf-screener/',['보안 정보','마켓 데이터','테크니컬즈','분석','배당']],
 ['bond','/bond-screener/',['보안 정보','위험 및 스프레드','등급','발행자','금액','쿠폰','채권 용어']],
 ['coin','/crypto-coins-screener/',['코인 인포','마켓 데이터','테크니컬즈','평가','파생상품','보유자','거래','센티멘트']],
 ['cex','/cex-screener/',['보안 정보','마켓 데이터','테크니컬즈','평가']],
 ['dex','/dex-screener/',['풀 정보','마켓 데이터','테크니컬즈','거래 활동']]
];
const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_SYSTEM_CHROME?{executablePath:process.env.PLAYWRIGHT_SYSTEM_CHROME}:{}),args:['--no-sandbox','--disable-dev-shm-usage']});
const capture={captured:new Date().toISOString(),source:'original public TradingView GUI with Chromium',products:{}};
await fs.mkdir('artifacts',{recursive:true});
for(const [product,path,categories] of SITES){
 const page=await browser.newPage({viewport:{width:1565,height:960},locale:'ko-KR'});
 capture.products[product]={path,categories:{}};
 try{
  await page.goto('https://kr.tradingview.com'+path,{waitUntil:'domcontentloaded',timeout:45000});
  await page.waitForTimeout(2200);
  async function open(){
   const adder=page.locator('[data-qa-id="screener-add-new-filter"]');
   try{await adder.click({timeout:6000});}catch{await page.keyboard.press('Shift+F');}
   await page.waitForTimeout(600);
  }
  await open();
  const dialog=page.locator('[role="dialog"]').last();
  console.log('GROUP',product,'dialogs',await page.locator('[role="dialog"]').count(),'dialog',JSON.stringify((await dialog.innerText().catch(()=>'' )).slice(0,500)));
  for(const name of categories){
   try{
    await open();
    const group=page.getByText(name,{exact:true}).last();
    await group.click({timeout:5000});
    await page.waitForTimeout(500);
    const snapshot=await page.evaluate(()=>{
     const all=[...document.querySelectorAll('[role="dialog"],[role="listbox"]')];
     const root=all.findLast(x=>x.getBoundingClientRect().width>100 && x.getBoundingClientRect().height>50)||all.at(-1);
     if(!root)return {error:'dialog_not_found'};
     const visible=x=>x.getBoundingClientRect().width>0&&x.getBoundingClientRect().height>0;
     const nodes=[...root.querySelectorAll('button,[role="option"],[role="menuitem"],label,[role="checkbox"]')].filter(visible).slice(0,350);
     return {text:root.innerText.slice(0,30000),html:root.outerHTML.slice(0,3000),count:nodes.length,
       items:nodes.map(x=>({tag:x.tagName,role:x.getAttribute('role'),text:x.innerText?.trim()?.slice(0,140),
         aria:x.getAttribute('aria-label'),title:x.getAttribute('title'),dataset:{...x.dataset}}))};
    });
    capture.products[product].categories[name]=snapshot;
    const texts=snapshot.items?.map(x=>x.text)?.filter(Boolean)||[];
    console.log('CATEGORY',product,name,'count',snapshot.count,'items',JSON.stringify(texts.slice(0,18)));
    const slug=String(name).replace(/[^\uAC00-\uD7A3a-zA-Z0-9]/g,'_');
    await page.screenshot({path:'artifacts/original-picker-'+product+'-'+slug+'.png'});
   }catch(e){
    capture.products[product].categories[name]={error:String(e).slice(0,250)};
    console.log('GROUP_FAIL',product,name,String(e).slice(0,210));
   }finally{
    await page.keyboard.press('Escape').catch(()=>{});
    await page.waitForTimeout(180);
   }
  }
 }catch(e){capture.products[product].error=String(e).slice(0,400);console.log('PAGE_FAIL',product,String(e).slice(0,270));}
 finally{await page.close();}
}
await browser.close();
await fs.writeFile('artifacts/original-filter-catalog-gui.json',JSON.stringify(capture,null,2),'utf-8');
console.log('GROUP_CAPTURE_FINAL',JSON.stringify(Object.fromEntries(Object.entries(capture.products).map(([k,v])=>[k,Object.fromEntries(Object.entries(v.categories).map(([name,s])=>[name,s.items?.length||0]))]))));
