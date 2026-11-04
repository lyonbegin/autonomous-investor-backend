const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('n8n/admin-console/index.html','utf8');
const scripts=[...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)]
  .map(m=>m[1]).filter(s=>s.trim());
assert(scripts.length>0,'ADMIN_SCRIPT_MISSING');
for(let i=0;i<scripts.length;i++)new vm.Script(scripts[i],{filename:'admin-'+i+'.js'});
assert(html.includes("['verified','검증 완료 전략'"),'VERIFIED_ADMIN_MENU_MISSING');
assert(html.includes('/verified/index.html?view=list'),'ORIGINAL_SCRIPT_UI_MISSING');
assert(html.includes("verified-publish"),'NO_ADMIN_EXPLICIT_SELECTION');
assert(html.includes('/api/investment/verified-scripts/publish'),'NO_SERVER_PROOF_GATE');
console.log('ADMIN_VERIFIED_SCRIPTS_JS_AND_EMBED_PASS');
