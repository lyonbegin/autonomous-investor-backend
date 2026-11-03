const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('n8n/admin-console/index.html','utf8');
const exact='https://www.tradingview.com/script/LkgKT3TG-Displaced-Donchian-Decycler-Trend-Breakout-Strategy-with-MFI/';
assert(html.includes(exact),'ORIGINAL_DDDS_PUBLICATION_URL_REQUIRED');
assert(html.includes('publication-live-original-link'),'REAL_ORIGINAL_LINK_MISSING');
assert(!html.includes("'<img id=\"publication-official-image\""),'ORIGINAL_CHART_IMAGE_STILL_RENDERED');
assert(html.includes('별도 300봉 Python 실행 (원본 비교 아님)'),'DIAGNOSTIC_MISLABELLED_AS_PARITY');
assert(html.includes('frame-ancestors none'),'FRAME_RESTRICTION_NOT_DISCLOSED');
const chunks=[...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)]
 .map(x=>x[1].trim()).filter(Boolean);
assert(chunks.length>0,'NO_ADMIN_INLINE_JS_FOUND');
for(const [i,js] of chunks.entries())new vm.Script(js,{filename:'admin-inline-'+i+'.js'});
console.log('WF02_REAL_ORIGINAL_CHART_UI_STATIC_PASS scripts='+chunks.length);
