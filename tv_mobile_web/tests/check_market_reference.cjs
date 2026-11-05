/* The exact 2026-11-05 uploaded HTML snapshot had ten content sections,
 * 47 innermost data widgets and 258 distinct visible symbol hrefs.
 * These counts are NOT a claim about TradingView's entire universe. */
const fs=require("node:fs");
const vm=require("node:vm");
const assert=require("node:assert/strict");
const context={window:{}};
for(const file of ["market_names_stocks.js","market_names_assets.js",
 "market_names_bonds_etfs.js","market_home_data.js"]){
 const content=fs.readFileSync("tv_mobile_web/web/"+file,"utf8");
 vm.runInNewContext(content,context,{filename:file});
}
const s=context.window.TVMarketSource;
assert.equal(s.groups.length,10,"one original content section must not be omitted");
const widgets=s.groups.flatMap(x=>x.widgets);
assert.equal(widgets.length,47,"all 47 actual innermost widgets retained");
assert.equal(new Set(widgets.map(x=>x.id)).size,47,"no duplicate widget IDs");
const symbols=[...new Set(widgets.flatMap(x=>x.symbols))];
assert.equal(symbols.length,258,"all distinct source-visible symbol hrefs retained");
for(const symbol of symbols){
 assert.ok(context.window.TVSourceNames[symbol],"source name missing: "+symbol);
 assert.ok(s.symbol(symbol),"original exchange prefix absent: "+symbol);
}
assert.equal(s.symbol("KRX-005930"),"KRX:005930");
assert.equal(s.symbol("BTCUSD"),"CRYPTO:BTCUSD");
assert.equal(s.symbol("USDKRW"),"FX_IDC:USDKRW");
assert.equal(s.symbol("ELSAUSDT.P"),"BINANCE:ELSAUSDT.P");
assert.equal(s.symbol("SPX"),"SP:SPX");
assert.equal(s.name("KRX-005930"),"삼성전자");
assert.ok(widgets.some(x=>x.id==="economic-indicators-heatmap"));
assert.ok(widgets.some(x=>x.id==="yield-curve"));
assert.ok(widgets.some(x=>x.id==="stocks-ipo-calendar"));
console.log("USER_HTML_MARKETS_PARITY_INVENTORY_PASSED",JSON.stringify({
 sections:s.groups.length,widgets:widgets.length,visibleUniqueSymbols:symbols.length,
 verifiedOriginalExchangePrefixForAll:true
}));
