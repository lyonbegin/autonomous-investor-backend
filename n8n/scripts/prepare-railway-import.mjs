// Prepare private one-time n8n imports. Bearer token is written only to /tmp,
// then encrypted at rest by n8n import:credentials. Never log secret values.
import fs from 'node:fs';
import path from 'node:path';
const token=process.env.ALPHA_NODE_API_KEY;
const upstream=(process.env.INVESTMENT_N8N_BACKEND_API||'http://investment-n8n-ops-api.railway.internal:8000').replace(/\/$/,'');
if (!token || token.length < 20) throw Error('ALPHA_NODE_API_KEY is required (20+ chars)');
if (!upstream.startsWith('http://investment-n8n-ops-api.railway.internal:') && !upstream.startsWith('http://invest-backend:')) throw Error('Backend must be Railway-private or Docker-private');
const credId='inv-hdr-2026';
const credName='Autonomous Investor Internal API';
const target='/tmp/ai-n8n-railway-workflows';
fs.mkdirSync(target,{recursive:true});
let total=0;
for (const group of ['scenarios','operations']){
 const source='/home/node/import/'+group;
 for(const filename of fs.readdirSync(source).filter(x=>x.endsWith('.json'))){
  const obj=JSON.parse(fs.readFileSync(path.join(source,filename),'utf8'));
  for(const node of obj.nodes||[]){
   if(node.type!=='n8n-nodes-base.httpRequest')continue;
   node.parameters.url=node.parameters.url.replace('http://invest-backend:8000',upstream);
   node.parameters.authentication='genericCredentialType';
   node.parameters.genericAuthType='httpHeaderAuth';
   node.credentials={httpHeaderAuth:{id:credId,name:credName}};
  }
  fs.writeFileSync(path.join(target,filename),JSON.stringify(obj),{mode:0o600});
  total++;
 }
}
if(total!==13)throw Error('Expected 13 workflows, found '+total);
fs.writeFileSync('/tmp/ai-n8n-credentials.json',JSON.stringify([{
 id:credId,name:credName,type:'httpHeaderAuth',
 data:{name:'Authorization',value:'Bearer '+token}
}]),{mode:0o600});
console.log('Prepared '+total+' internal workflow imports and one encrypted credential input; no credentials logged.');
