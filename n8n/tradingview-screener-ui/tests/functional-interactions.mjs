import {chromium} from 'playwright';
import fs from 'node:fs/promises';
import {CRYPTO_TAB_COLS} from '../src/crypto-tab-presets.js';
const ROOT='http://127.0.0.1:4173';
const SCENARIOS=[
 {key:'stock',url:'/screener/',enum:'섹터',enumField:'sector',number:'가격',numberField:'close'},
 {key:'etf',url:'/etf-screener/',enum:'자산 클래스',enumField:'asset_class',number:'AUM',numberField:'aum'},
 {key:'bond',url:'/bond-screener/',enum:'발급자 유형',enumField:'bond_issuer_type',number:'쿠폰 %',numberField:'current_coupon'},
 {key:'coin',url:'/crypto-coins-screener/',enum:'카테고리',enumField:'crypto_common_categories',number:'시가총액',numberField:'market_cap_calc'},
 {key:'cex',url:'/cex-screener/',enum:'거래소',enumField:'exchange',number:'달러 표시 거래량',numberField:'24h_vol|5'},
 {key:'dex',url:'/dex-screener/',enum:'블록체인',enumField:'blockchain-id',number:'유동성',numberField:'dex_total_liquidity'}
];
const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_SYSTEM_CHROME?{executablePath:process.env.PLAYWRIGHT_SYSTEM_CHROME}:{}),args:['--no-sandbox','--disable-dev-shm-usage']});
const results=[],failures=[];
function assert(k,flag,details={}){const value={name:k,pass:!!flag,...details};results.push(value);console.log((flag?'PASS ':'FAIL ')+k+' '+JSON.stringify(details).slice(0,500));if(!flag)failures.push(value);}
function expr(payload,field){return (payload?.filter||[]).find(x=>x.left===field);}
async function nextScan(page,action){
 const requested=page.waitForRequest(req=>req.url().endsWith('/api/scan')&&req.method()==='POST',{timeout:12000});
 await action();const req=await requested;return {body:req.postDataJSON(),response:await req.response().catch(()=>null)};
}
function resultStatus(scan){return scan.response?scan.response.status():null;}
for(const s of SCENARIOS){
 const page=await browser.newPage({viewport:{width:1565,height:960},locale:'ko-KR'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  const response=await page.goto(ROOT+s.url,{waitUntil:'domcontentloaded',timeout:30000});
  await page.locator('[data-testid="screener-app"]').waitFor();
  await page.locator('[data-testid="filter-'+s.enum+'"]').click();
  const editor=page.locator('[data-testid="filter-editor"]');
  await editor.waitFor();
  await page.waitForTimeout(900);
  const enumID=s.key==='coin'?'crypto_common_categories':s.key==='dex'?'blockchain-id':s.enumField;
  const enumResponse=await page.request.get(ROOT+'/api/enum?product='+s.key+'&id='+encodeURIComponent(enumID),{timeout:25000});
  await editor.locator('.filter-values label').first().waitFor({timeout:20000}).catch(()=>{});
  const enumJSON=await enumResponse.json().catch(()=>null);
  console.log('ENUM-DIAGNOSTIC',s.key,'HTTP',enumResponse.status(),'keys',Object.keys(enumJSON||{}).slice(0,20).join(','),'target',s.enumField);
  const opts=editor.locator('.filter-values label');
  const cnt=await opts.count();
  assert(s.key+': enum menu populates from server',cnt>0,{count:cnt});
  if(cnt>0){
    const picked=await opts.first().locator('small').innerText();
    await opts.first().locator('input[type="checkbox"]').check();
    const scan=await nextScan(page,()=>editor.locator('[data-testid="filter-apply"]').click());
    const got=expr(scan.body.payload,s.enumField);
    assert(s.key+': enum selected ID forwarded to scanner',!!got&&got.right.includes(picked),{selected:picked,condition:got,HTTP:resultStatus(scan)});
    assert(s.key+': enum result is HTTP 200',resultStatus(scan)===200,{HTTP:resultStatus(scan)});
    assert(s.key+': enum applied pill visually updates',await page.locator('[data-testid="filter-'+s.enum+'"]').getAttribute('class').then(x=>x.includes('filter-applied')));
    const undo=await nextScan(page,()=>page.locator('[data-qa-id="screener-undo-button"]').click());
    assert(s.key+': undo removes enum condition',!expr(undo.body.payload,s.enumField));
    const redo=await nextScan(page,()=>page.locator('[data-qa-id="screener-redo-button"]').click());
    assert(s.key+': redo restores enum condition',!!expr(redo.body.payload,s.enumField));
  }else{await page.locator('.pop-header button').click();}
  await page.locator('[data-testid="filter-'+s.number+'"]').click();
  const ne=page.locator('[data-testid="filter-editor"]');
  assert(s.key+': numeric condition selector',await ne.locator('[aria-label="비교 조건"] option').count()>=6);
  await ne.locator('[aria-label="조건값"]').fill('10');
  const numScan=await nextScan(page,()=>ne.locator('[data-testid="filter-apply"]').click());
  const numeric=expr(numScan.body.payload,s.numberField);
  assert(s.key+': numeric >=10 applied to scanner',numeric?.operation==='egreater'&&numeric?.right===10,{condition:numeric,HTTP:resultStatus(numScan)});
  assert(s.key+': numeric scan HTTP 200',resultStatus(numScan)===200,{HTTP:resultStatus(numScan)});
  await page.locator('[data-testid="filter-'+s.number+'"]').click();
  const ee=page.locator('[data-testid="filter-editor"]');
  await ee.locator('[aria-label="비교 조건"]').selectOption('less');
  await ee.locator('[aria-label="조건값"]').fill('50');
  const changed=await nextScan(page,()=>ee.locator('[data-testid="filter-apply"]').click());
  assert(s.key+': comparison operator and threshold changed',expr(changed.body.payload,s.numberField)?.operation==='less'&&expr(changed.body.payload,s.numberField)?.right===50,{condition:expr(changed.body.payload,s.numberField),HTTP:resultStatus(changed)});
  await page.locator('[data-testid="filter-'+s.number+'"]').click();
  const reset=await nextScan(page,()=>page.locator('[data-testid="filter-editor"] .filter-edit-actions button').first().click());
  assert(s.key+': reset removes numeric condition',!expr(reset.body.payload,s.numberField));
  await page.locator('[data-qa-id="screener-topbar-settings"]').click();
  const row=page.locator('.screener-table thead th[data-field]').first();
  const before=await row.evaluate(el=>el.getBoundingClientRect().height);
  await page.locator('.settings-list input').first().check();
  const after=await row.evaluate(el=>el.getBoundingClientRect().height);
  assert(s.key+': compact table setting changes rendered height',after<before,{before,after});
  await page.locator('.settings-list .apply-btn').click();
  const sortField=await page.locator('.screener-table thead th[data-field]').nth(1).getAttribute('data-field');
  const sorted=await nextScan(page,()=>page.locator('.screener-table thead th[data-field]').nth(1).click());
  assert(s.key+': column sorting reaches scanner',sorted.body.payload.sort?.sortBy===(sortField==='isin-displayed'?'isin':sortField?.replace(/\.tr$/,'')),{column:sortField,sort:sorted.body.payload.sort});
  const paginate=await nextScan(page,()=>page.locator('select[aria-label="페이지당 행 수"]').selectOption('50'));
  assert(s.key+': page size reflected in scanner payload',JSON.stringify(paginate.body.payload.range)==='[0,50]',{range:paginate.body.payload.range});
  await page.locator('[data-qa-id="screener-add-column-button"]').click();
  const options=page.locator('.popover-columns .option-list button');
  if(await options.filter({hasText:'close'}).count()){
   const first=options.filter({hasText:'close'}).first();
   const text=await first.innerText();
   const beforeColumns=await page.locator('th[data-field]').count();
   const col=await nextScan(page,()=>first.click());
   const afterColumns=await page.locator('th[data-field]').count();
   assert(s.key+': add or remove column changes scanner request and table',beforeColumns!==afterColumns,{label:text,old:beforeColumns,new:afterColumns,columns:col.body.payload.columns?.length});
  }
  if(CRYPTO_TAB_COLS[s.key]){
    const tabRequest=await nextScan(page,()=>page.locator('[data-testid="tab-1"]').click());
    assert(s.key+': original performance tab exact request columns',JSON.stringify(tabRequest.body.payload.columns)===JSON.stringify(CRYPTO_TAB_COLS[s.key][1]),{columns:tabRequest.body.payload.columns?.length,HTTP:resultStatus(tabRequest)});
    assert(s.key+': original performance tab scan returns HTTP 200',resultStatus(tabRequest)===200,{HTTP:resultStatus(tabRequest)});
  }
  await page.screenshot({path:'artifacts/functional-'+s.key+'.png'});
  assert(s.key+': no browser exceptions',errors.length===0,{errors});
 }catch(e){assert(s.key+': scenario complete',false,{error:String(e).slice(0,500)});}
 finally{await page.close();}
}
const stock=await browser.newPage();
try{
 await stock.goto(ROOT+'/screener/',{waitUntil:'domcontentloaded'});
 await stock.locator('[data-testid="market-filter"]').click();
 const scan=await nextScan(stock,()=>stock.locator('.popover-market button').filter({hasText:'일본'}).first().click());
 assert('stock: country selector changes market and scan endpoint',scan.body.market==='japan'&&scan.body.payload.markets[0]==='japan',{market:scan.body.market,HTTP:resultStatus(scan)});
}catch(e){assert('stock: country scenario',false,{error:String(e)});}finally{await stock.close();}
await browser.close();
await fs.mkdir('artifacts',{recursive:true});
await fs.writeFile('artifacts/functional-results.json',JSON.stringify({scenarios:SCENARIOS.map(x=>x.key),checks:results.length,failures},null,2));
console.log('FUNCTIONAL FINAL '+JSON.stringify({checks:results.length,failed:failures.length}));
process.exitCode=failures.length?1:0;
