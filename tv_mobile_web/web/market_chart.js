/* Inline Markets chart: actual stored 5-year daily OHLCV only.
   1D/1M/3M/1Y/5Y/전체 are display ranges, NOT collection intervals.
   No fake candles and no 5 years of minute bars. */
"use strict";
(() => {
 const esc=x=>String(x??"").replace(/[&<>"']/g,c=>({
  "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
 }[c]));
 const ranges={"1D":1,"1M":31,"3M":92,"1Y":366,"5Y":1828,"전체":Infinity};
 function draw(host,store){
  const canvas=host.querySelector("canvas"),note=host.querySelector(".tv-copy-chart-state");
  if(!canvas||!note)return;
  const all=store.bars;
  if(!all.length){note.textContent="이 종목의 실제 5년 일봉은 저장되지 않았습니다.";return;}
  const last=all.at(-1).time_ms;
  let bars=all.filter(b=>last-b.time_ms<=ranges[store.range]*86400000);
  if(bars.length<2)bars=all.slice(-2);
  const ctx=canvas.getContext("2d");
  if(!ctx){note.textContent="차트 표시 불가";return;}
  const w=canvas.width,h=canvas.height,pad=24;
  ctx.clearRect(0,0,w,h);
  const low=Math.min(...bars.map(x=>x.low??x.close));
  const hi=Math.max(...bars.map(x=>x.high??x.close));
  const span=Math.max(.000001,hi-low);
  const y=v=>h-pad-(v-low)/span*(h-2*pad);
  const dx=(w-pad*2)/Math.max(1,bars.length-1);
  ctx.lineWidth=1;ctx.strokeStyle="#dee3eb";
  for(let j=0;j<4;j++){
   const h0=pad+(h-2*pad)*j/3;
   ctx.beginPath();ctx.moveTo(pad,h0);ctx.lineTo(w-pad,h0);ctx.stroke();
  }
  if(store.style==="candle"){
   const bw=Math.max(1,Math.min(6,dx*.7));
   bars.forEach((b,i)=>{
    const x=pad+i*dx,up=b.close>=(b.open??b.close);
    ctx.strokeStyle=up?"#139b73":"#dd5060";ctx.fillStyle=ctx.strokeStyle;
    ctx.beginPath();ctx.moveTo(x,y(b.high??b.close));
    ctx.lineTo(x,y(b.low??b.close));ctx.stroke();
    ctx.fillRect(x-bw/2,Math.min(y(b.open??b.close),y(b.close)),bw,
     Math.max(1,Math.abs(y(b.open??b.close)-y(b.close))));
   });
  }else{
   ctx.beginPath();bars.forEach((b,i)=>{
    const x=pad+dx*i;if(i===0)ctx.moveTo(x,y(b.close));
    else ctx.lineTo(x,y(b.close));
   });
   ctx.strokeStyle="#2476e5";ctx.lineWidth=2;ctx.stroke();
  }
  note.textContent=bars.length+"개 저장된 실제 1D 봉 · "+store.range+
    " 기간 · 최근 저장일 "+new Date(last).toISOString().slice(0,10);
 }
 async function show(host,symbol){
  if(!host||!/^[A-Z0-9_]{1,30}:[A-Z0-9_.!/-]{1,65}$/i.test(symbol))return;
  const store={bars:[],range:"5Y",style:"area"};
  host.innerHTML='<div class="tv-copy-chart-title"><b>'+esc(symbol)+'</b>'+
   '<button data-copy-open-chart>전체 차트 ↗</button></div>'+
   '<div class="tv-copy-chart-options"><div>'+
   Object.keys(ranges).map(x=>'<button data-copy-range="'+x+
    '"'+(x==="5Y"?' class="active"':'')+'>'+x+'</button>').join("")+'</div>'+
   '<div><button class="active" data-copy-style="area">영역</button>'+
   '<button data-copy-style="candle">캔들</button></div></div>'+
   '<canvas width="1000" height="240" aria-label="실제 1D 가격 차트"></canvas>'+
   '<div class="tv-copy-chart-state">저장된 5년 일봉 검증 중…</div>';
  host.querySelector("[data-copy-open-chart]").onclick=()=>window.tvMarketNavigate?.("chart",{symbol});
  host.querySelectorAll("[data-copy-range]").forEach(b=>b.onclick=()=>{
   store.range=b.dataset.copyRange;
   host.querySelectorAll("[data-copy-range]").forEach(x=>x.classList.toggle("active",x===b));
   draw(host,store);
  });
  host.querySelectorAll("[data-copy-style]").forEach(b=>b.onclick=()=>{
   store.style=b.dataset.copyStyle;
   host.querySelectorAll("[data-copy-style]").forEach(x=>x.classList.toggle("active",x===b));
   draw(host,store);
  });
  try{
   const response=await fetch("/api/chart/history?symbol="+encodeURIComponent(symbol),{cache:"no-store"});
   if(!response.ok)throw Error("이 종목의 5년 일봉은 아직 저장되지 않았습니다.");
   const json=await response.json();
   if(!host.isConnected)return;
   store.bars=(json.bars||[]).filter(x=>Number.isFinite(x.time_ms)&&
    Number.isFinite(x.close)&&Number.isFinite(x.open)&&
    Number.isFinite(x.high)&&Number.isFinite(x.low))
    .sort((a,b)=>a.time_ms-b.time_ms);
   draw(host,store);
  }catch(error){
   if(!host.isConnected)return;
   const note=host.querySelector(".tv-copy-chart-state");
   note.textContent=error.message+" · ";
   const link=document.createElement("a");
   link.href="https://www.tradingview.com/chart/?symbol="+encodeURIComponent(symbol);
   link.target="_blank";link.rel="noopener noreferrer";link.textContent="원본 차트 열기 ↗";
   note.appendChild(link);
  }
 }
 window.TVMarketChart={show};
})();
