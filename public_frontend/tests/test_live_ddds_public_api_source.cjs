/* Read-only verification of the REAL deployed site's exact DDDS catalog:
 * never swaps in a different script for missing original source/market bars.
 */
const API=process.env.PUBLIC_API||'https://autonomous-investor-public-api-production.up.railway.app';
const ID='PUB;5442675d418140c58486eb4a7ae12768';
const SHA='5a245e99447f13012dd026528235fc2c299cad5cb7b228653c684886dcba6507';
(async()=>{
 const endpoints=[
   ['meta','/api/public/scripts/'+encodeURIComponent(ID)+'/meta'],
   ['source','/api/public/scripts/'+encodeURIComponent(ID)+'/source'],
   ['chart','/api/public/scripts/'+encodeURIComponent(ID)+'/chart?symbol=NASDAQ%3AAMZN&horizon=2h']
 ];
 const results={source_id:ID,base:API};
 let failure=0;
 for(const [name,path] of endpoints){
  try{
   const r=await fetch(API+path,{signal:AbortSignal.timeout(25000)});
   let json=await r.json().catch(()=>({}));
   const report={http:r.status,
      script_id:json.script_id||json.script_id_part||null,
      sha:json.source_hash||json.source_sha256||null,
      symbol:json.symbol||null,horizon:json.horizon||null,
      bars:Array.isArray(json.bars)?json.bars.length:0,
      fallback_used:json.market_data?.fallback_used===true,
      reason:json.reason||null};
   results[name]=report;
   if(name==='source'&&(r.status!==200||report.sha!==SHA||typeof json.source!=='string'||!json.source.length))failure++;
   else if(name==='chart'&&(r.status!==200||report.bars<40||report.symbol!=='NASDAQ:AMZN'||report.horizon!=='2h'||report.fallback_used))failure++;
   else if(name==='meta'&&r.status!==200)failure++;
  }catch(e){results[name]={error:String(e).slice(0,220)};failure++}
 }
 console.log('LIVE_DDDS_PUBLIC_SITE_SOURCE_PROBE '+JSON.stringify(results));
 if(failure)process.exitCode=3;
})();
