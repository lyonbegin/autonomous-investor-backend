// Startup-only Railway E2E diagnostic, never a real order and never prints tokens.
// Proves webhook -> n8n Redis Worker -> real private FastAPI -> persistent run events.
const base="http://127.0.0.1:5678";
const api=(process.env.INVESTMENT_N8N_BACKEND_API||"http://investment-n8n-ops-api.railway.internal:8000").replace(/\/$/,"");
const token=process.env.ALPHA_NODE_API_KEY||"";
const ids=["01-new-strategy","02-version-update","03-capital-race","04-partial-fill",
 "05-long-backtest","06-strategy-drift","07-broker-timeout","08-agent-crash",
 "09-unsupported-pine","10-strategy-retire"];
const sleep=ms=>new Promise(ok=>setTimeout(ok,ms));
async function run(){
 for(let n=0;n<100;n++){
  try{const r=await fetch(base+"/healthz",{signal:AbortSignal.timeout(2000)});if(r.ok)break}catch{}
  await sleep(1400);
 }
 const jobs=[];
 for(const id of ids){
  let matched=false;
  for(let attempt=0;attempt<8;attempt++){
   try{
    const r=await fetch(base+"/webhook/ai-scenario-"+id,{
      method:"POST",headers:{"content-type":"application/json"},body:"{}",
      signal:AbortSignal.timeout(18000)});
    if(!r.ok)throw Error("webhook HTTP "+r.status);
    const obj=await r.json();
    if(obj.scenario_id!==id||!obj.run_id)throw Error("invalid runId response");
    jobs.push({id,run_id:obj.run_id});matched=true;break;
   }catch(e){if(attempt===7)console.error("E2E webhook failed "+id+": "+String(e).slice(0,90));await sleep(1200)}
  }
  if(!matched)throw Error("N8N_E2E_CANNOT_DISPATCH_"+id);
 }
 const deadline=Date.now()+120000;
 let completed=0;
 while(Date.now()<deadline){
  let total=0;
  for(const j of jobs){
   const r=await fetch(api+"/api/v1/alpha/scenarios/runs/"+j.run_id,{
     headers:{"Authorization":"Bearer "+token},signal:AbortSignal.timeout(6000)});
   if(!r.ok)throw Error("snapshot "+j.id+" HTTP "+r.status);
   const snap=await r.json();
   if(snap.status==="failed"||snap.status==="interrupted")throw Error("failed backend execution: "+j.id);
   if(snap.status==="completed"&&snap.completed_steps===snap.total_steps)total++;
  }
  completed=total;
  if(total===10)break;
  await sleep(700);
 }
 if(completed!==10)throw Error("ONLY_"+completed+"_OF_10_N8N_EXECUTIONS_COMPLETE");
 console.log("RAILWAY_REAL_N8N_WORKER_TO_FASTAPI_10_OF_10_PASS");
}
run().catch(e=>console.error("RAILWAY_REAL_N8N_WORKER_E2E_FAILED "+String(e).slice(0,220)));
