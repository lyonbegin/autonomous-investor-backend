// Read-only compatibility probe against the actual TradingView scanner.
// A 200 status verifies only that a specific predicate is accepted; 400 is a
// candidate schema mismatch, not proof that the concept is unsupported.
// This test never substitutes artificial or cached market results.
import fs from 'node:fs/promises';
import {FILTER_DEFS,specFor,makeExpressions,initialPending} from '../src/filter-spec.js';

const settings={
  stock:{market:'korea',label:'stock',sort:'market_cap_basic'},
  etf:{market:'america',label:'etf',sort:'aum'},
  bond:{market:'bond',label:'bond',sort:'bond_snp_rating_lt'},
  coin:{market:'coin',label:'coin',sort:'crypto_total_rank',order:'asc'},
  cex:{market:'crypto',label:'crypto-cex',sort:'24h_vol|5',
       filter2:{operator:'and',operands:[{expression:{left:'centralization',operation:'equal',right:'cex'}}]}},
  dex:{market:'crypto',label:'crypto-dex',sort:'dex_txs_count_24h',
       filter2:{operator:'and',operands:[{expression:{left:'centralization',operation:'equal',right:'dex'}}]}}
};
const sleep=ms=>new Promise(done=>setTimeout(done,ms));
const pool=4;
const outcomes=[];
async function request(url,opts={}){
  let last;
  for(let tries=0;tries<2;tries++){
    try{
      const r=await fetch(url,{headers:{'Accept':'application/json','Content-Type':'application/json','Origin':'https://kr.tradingview.com','Referer':'https://kr.tradingview.com/'},signal:AbortSignal.timeout(16000),...opts});
      const body=await r.text();
      let j=null;try{j=JSON.parse(body)}catch{}
      last={status:r.status,body:body.slice(0,380),json:j};
      if(r.status!==429&&r.status<500)break;
    }catch(e){last={status:0,body:String(e).slice(0,250)};}
    await sleep(600*(tries+1));
  }
  return last;
}
function bodyBase(p){
 const s=settings[p];
 return {
  columns:['ticker-view'],
  ignore_unknown_fields:false,
  options:{lang:'ko'},range:[0,1],
  sort:{sortBy:s.sort,sortOrder:s.order||'desc'},
  markets:[s.market],
  ...(s.filter2?{filter2:s.filter2}:{})
 };
}
async function evaluateField(product,label){
 const conf=settings[product],spec=specFor(product,label);
 const endpoint='https://scanner.tradingview.com/'+conf.market+'/scan?label-product=screener-'+conf.label;
 let item=initialPending(spec);
 let enumeration=null;
 if(spec.type==='enum'){
   const url='https://scanner.tradingview.com/enum/ordered?lang=ko&label-product=screener-'+conf.label+'&id='+encodeURIComponent(spec.enum||spec.field);
   const r=await request(url);
   const vals=r.json?.[spec.enum||spec.field];
   enumeration={http:r.status,options:Array.isArray(vals)?vals.length:0,error:r.status!==200?r.body:null};
   if(!Array.isArray(vals)||!vals.length)return {product,label,field:spec.field,type:spec.type,result:'no_enum_options',enum:enumeration};
   item={...item,choices:[String(vals[0].id)]};
 }else if(spec.type==='date'){
   item={...item,min:'2024-01-01'};
 }else{
   item={...item,min:'1'};
 }
 const {conditions,invalid}=makeExpressions(product,{[label]:item});
 if(invalid.length||!conditions.length)return {product,label,field:spec.field,result:'invalid_payload',invalid};
 const payload={...bodyBase(product),filter:conditions};
 const resp=await request(endpoint,{method:'POST',body:JSON.stringify(payload)});
 return {product,label,field:spec.field,type:spec.type,operation:conditions[0].operation,
  result:resp.status===200?'accepted':resp.status===400?'rejected_400':'remote_error',http:resp.status,
  message:resp.status===200?'':resp.json?.msg||resp.json?.error||resp.body,
  count:resp.json?.totalCount,enum:enumeration};
}
const tasks=[];
for(const [product,defs] of Object.entries(FILTER_DEFS))for(const label of Object.keys(defs))tasks.push({product,label});
const queue=[...tasks];
await Promise.all(Array.from({length:pool},async()=>{
 while(queue.length){
  const task=queue.shift();
  try{
    const row=await evaluateField(task.product,task.label);
    outcomes.push(row);console.log('FILTER_AUDIT',JSON.stringify(row));
  }catch(e){const row={...task,result:'exception',error:String(e).slice(0,200)};outcomes.push(row);console.log('FILTER_AUDIT',JSON.stringify(row));}
 }
}));
outcomes.sort((a,b)=>a.product.localeCompare(b.product)||a.label.localeCompare(b.label,'ko'));
const tally={};
for(const r of outcomes)tally[r.result]=(tally[r.result]||0)+1;
const report={captured:new Date().toISOString(),source:'TradingView public scanner HTTP, direct no mocked responses',total:outcomes.length,byStatus:tally,outcomes};
await fs.mkdir('artifacts',{recursive:true});
await fs.writeFile('artifacts/complete-filter-catalog-audit.json',JSON.stringify(report,null,2),'utf-8');
console.log('CATALOG_FINAL',JSON.stringify({total:report.total,byStatus:tally}));
