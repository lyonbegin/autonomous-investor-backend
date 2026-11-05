/* Actual live-scanner quote hydration, viewport-lazy and failure-honest.
   Never substitutes 2026-11-05 archived snapshot prices or fake values. */
"use strict";
(() => {
 const saved=new Map(), loaded=new Set(), pending=new Map();
 const fmt=v=>typeof v==="number"&&Number.isFinite(v)?
    v.toLocaleString("ko-KR",{maximumFractionDigits:5}):"—";
 function paint(root){
  if(!root)return;
  for(const button of root.querySelectorAll("[data-copy-symbol]")){
   const symbol=window.TVMarketSource?.symbol(button.dataset.copySymbol);
   const row=symbol?saved.get(symbol.toUpperCase()):null;
   if(!row)continue;
   const price=button.querySelector(".tv-copy-price b");
   const state=button.querySelector(".tv-copy-price small");
   if(price)price.textContent=fmt(row.close);
   if(state){
    state.textContent=typeof row.change==="number"?
      (row.change>0?"+":"")+fmt(row.change)+"%":"응답 있음";
    state.className=typeof row.change==="number"?(row.change>=0?"up":"down"):"";
    state.title="기존 TradingView 스캐너에서 반환한 데이터; 거래소별 실시간 여부 미검증";
   }
  }
 }
 async function fetchRegion(id){
  const root=document.getElementById("copy-"+id);
  const item=window.TVMarketSource?.groups.find(x=>x.id===id);
  if(!item||!root||!item.scanner||loaded.has(id)||pending.has(id))return;
  pending.set(id,true);
  try{
   const controller=new AbortController();
   const timer=setTimeout(()=>controller.abort(),18000);
   let response;
   try{
    response=await fetch("/api/markets/"+encodeURIComponent(item.scanner)+
      "?limit=10&offset=0&order=volume",{
       signal:controller.signal,cache:"no-store",headers:{"Accept":"application/json"}
      });
   }finally{clearTimeout(timer);}
   if(!response.ok)throw Error("HTTP "+response.status);
   const data=await response.json();
   if(!Array.isArray(data.items)||data.items.length>10)
     throw Error("INVALID_SCANNER_PAGE");
   for(const row of data.items){
    const sym=String(row.ticker||row.symbol||"").trim().toUpperCase();
    if(sym)saved.set(sym,row);
   }
   loaded.add(id);
   paint(root);
  }catch(error){
   // The original reference items remain navigable, but their quotes stay —.
   root.dataset.scannerStatus="unavailable";
  }finally{pending.delete(id);}
 }
 let io=null;
 function attach(root){
  io?.disconnect();
  if(!root)return;
  if(!window.IntersectionObserver){
   window.TVMarketSource?.groups.forEach(g=>fetchRegion(g.id));return;
  }
  io=new IntersectionObserver(entries=>{
   for(const entry of entries)if(entry.isIntersecting){
    const id=entry.target.dataset.copySection;
    io.unobserve(entry.target);
    fetchRegion(id);
   }
  },{rootMargin:"250px"});
  root.querySelectorAll(".tv-copy-section").forEach(x=>{
   x.dataset.copySection=x.id.slice("copy-".length);
   io.observe(x);
  });
 }
 window.TVMarketLive={attach,paint,saved};
})();
