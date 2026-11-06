const products=['stock','etf','bond','coin','cex','dex'];
const labels=['stock','etf','bond','coin','crypto','crypto-coins','cex','crypto-cex','dex','crypto-dex'];
const errors=[];
function shape(data){if(!data||typeof data!=='object')return{type:typeof data};
 const keys=Object.keys(data),best=keys.filter(x=>/category|exchange|blockchain|sector|issuer|asset_class|brand|curren/i.test(x));
 return {type:Array.isArray(data)?'array':'object',keys:keys.length,first:keys.slice(0,16),relevant:best.slice(0,22),counts:Object.fromEntries(best.slice(0,16).map(k=>[k,Array.isArray(data[k])?data[k].length:typeof data[k]]))};}
await Promise.all([...products.map(async p=>{try{const r=await fetch('http://127.0.0.1:4173/api/enum?product='+p,{signal:AbortSignal.timeout(20000)});const body=await r.text();let json;try{json=JSON.parse(body)}catch{};console.log('ENUM_LOCAL',p,r.status,JSON.stringify(shape(json)), 'raw',body.slice(0,160));}catch(e){console.log('ENUM_LOCAL_ERR',p,String(e));errors.push(p);}}),
 ...labels.map(async p=>{try{const u='https://scanner.tradingview.com/enum/ordered?lang=ko&label-product=screener-'+p;const r=await fetch(u,{signal:AbortSignal.timeout(20000)});let raw=await r.text(),json;try{json=JSON.parse(raw)}catch{}console.log('ENUM_UPSTREAM',p,r.status,JSON.stringify(shape(json)),'raw',raw.slice(0,100));}catch(e){console.log('ENUM_UPSTREAM_ERR',p,String(e));errors.push(p);}})]);
console.log('ENUM FINISHED errors='+errors.length);
