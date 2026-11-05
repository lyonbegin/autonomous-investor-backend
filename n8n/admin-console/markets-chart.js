/* Real OHLCV market renderer. Never substitutes synthetic quotes for missing data. */
(function(){
"use strict";
function candleSVG(bars,period){
  const filtered=(period==="1D"?bars.filter(b=>b.t>=bars[bars.length-1].t-86400):bars);
  const data=filtered.length>2?filtered:bars;
  const step=Math.max(1,Math.ceil(data.length/110)),groups=[];
  for(let i=0;i<data.length;i+=step){
    const g=data.slice(i,i+step);
    groups.push({t:g[0].t,o:g[0].o,c:g[g.length-1].c,h:Math.max(...g.map(x=>x.h)),l:Math.min(...g.map(x=>x.l))});
  }
  const left=12,right=708,top=14,bottom=250,W=800,H=286;
  const low=Math.min(...groups.map(b=>b.l)),high=Math.max(...groups.map(b=>b.h));
  const pad=(high-low)*.07||1,min=low-pad,max=high+pad;
  const y=p=>top+(max-p)/(max-min)*(bottom-top);
  const width=(right-left)/groups.length,body=Math.max(1,Math.min(9,width*.63));
  const fmt=n=>Number(n).toLocaleString("ko-KR",{maximumFractionDigits:3});
  let svg='<svg viewBox="0 0 '+W+' '+H+'" style="width:100%;height:270px;display:block" role="img" aria-label="실제 공급원 시세 봉차트">';
  for(let i=0;i<5;i++){
    let p=min+(max-min)*i/4,yy=y(p);
    svg+='<line x1="12" x2="'+right+'" y1="'+yy+'" y2="'+yy+'" stroke="#343944" stroke-dasharray="3 5"/><text x="715" y="'+(yy+4)+'" fill="#aeb3c2" font-size="11">'+fmt(p)+'</text>';
  }
  groups.forEach((b,i)=>{
    let x=left+(i+.5)*width,green=b.c>=b.o,color=green?"#27b79a":"#ed6871";
    svg+='<line x1="'+x+'" x2="'+x+'" y1="'+y(b.h)+'" y2="'+y(b.l)+'" stroke="'+color+'" stroke-width="1"/>';
    svg+='<rect x="'+(x-body/2)+'" y="'+Math.min(y(b.o),y(b.c))+'" width="'+body+'" height="'+Math.max(1,Math.abs(y(b.o)-y(b.c)))+'" fill="'+color+'"/>';
  });
  for(let i=0;i<5;i++){
    let g=groups[Math.round((groups.length-1)*i/4)],x=left+i*(right-left)/4;
    let label=new Date(g.t*1000).toLocaleDateString("ko-KR",{year:"2-digit",month:"2-digit",day:"2-digit",timeZone:"UTC"});
    svg+='<text x="'+x+'" y="274" fill="#9aa4b7" font-size="10">'+label+'</text>';
  }
  return svg+'</svg>';
}
function tvFallback(el,tvSymbol,reason){
  el.replaceChildren();
  const warn=document.createElement("p");warn.className="small";
  warn.textContent="독립 시세 API 미연결 ("+reason+"). TradingView 공식 차트 위젯을 표시합니다.";
  el.appendChild(warn);
  const box=document.createElement("div");box.className="tradingview-widget-container";box.style.cssText="width:100%;height:290px;position:relative";
  const widget=document.createElement("div");widget.className="tradingview-widget-container__widget";widget.style.cssText="width:100%;height:100%";
  box.appendChild(widget);
  el.appendChild(box);
  const script=document.createElement("script");script.async=true;
  script.src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
  script.textContent=JSON.stringify({autosize:true,symbol:tvSymbol,interval:"D",timezone:"Etc/UTC",theme:"dark",style:"1",locale:"kr",hide_top_toolbar:true,hide_side_toolbar:true,allow_symbol_change:false,calendar:false,save_image:false,support_host:"https://www.tradingview.com"});
  script.onerror=()=>{warn.textContent="외부 차트 제공사 연결 실패. 아래 원본 링크로 이동해 확인하세요."};
  box.appendChild(script);
  const link=document.createElement("a");link.href=tvSymbolHref(tvSymbol);
  link.target="_blank";link.rel="noopener noreferrer";
  link.style.cssText="display:block;color:#9dc6ff;padding:5px 0;text-decoration:underline";
  link.textContent="원본 차트로 이동 ↗";el.appendChild(link);
}
window.renderMarketChart=function(id){
  const el=document.getElementById("chart-"+id);if(!el)return;
  const selected=state.selected[id]||0,s=symbols[id][selected],period=state.period[id]||"1D";
  state.request=state.request||{};const token=state.request[id]=(state.request[id]||0)+1;
  if(!s[1]){el.textContent="이 상품군은 가격 데이터가 아직 연결되지 않았습니다.";return;}
  el.innerHTML='<div class="placeholder">실제 시세 조회 중…</div>';
  const endpoint="/api/markets/ohlcv?symbol="+encodeURIComponent(s[1])+"&period="+encodeURIComponent(period);
  fetch(endpoint,{headers:{"Accept":"application/json"}}).then(async r=>{
    const v=await r.json();
    if(!r.ok||v.status!=="OK"||!Array.isArray(v.bars)||v.bars.length<2)throw Error(v.reason||v.status||"NO_BARS");
    return v;
  }).then(v=>{
    if(!el.isConnected||state.request[id]!==token)return;
    el.innerHTML=candleSVG(v.bars,period);
    const meta=document.createElement("div");meta.className="small";
    meta.style.cssText="padding:4px 6px";
    meta.textContent="실제 "+v.source+" · "+v.bar_count+"봉 · "+v.interval+" · "+new Date(v.asof_utc*1000).toLocaleString("ko-KR",{timeZone:"UTC"})+" UTC · 실시간 여부 미확인";
    el.appendChild(meta);
    const section=document.getElementById(id),card=section&&section.querySelectorAll(".symbol")[selected];
    const price=card&&card.querySelector(".empty-price");
    if(price)price.textContent=Number(v.latest_close).toLocaleString("ko-KR",{maximumFractionDigits:4})+" "+(v.currency||"");
  }).catch(err=>{
    if(!el.isConnected||state.request[id]!==token)return;
    console.warn("market provider unavailable",id,err.message);
    tvFallback(el,s[1],String(err.message).slice(0,55));
  });
};
})();
