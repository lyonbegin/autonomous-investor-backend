/* Markets front page reconstructed from user-supplied HTML.
   Includes all 10 source sections and 47 source leaf widget IDs.
   Source tickers are historical reference identifiers, not live quotes. */
"use strict";
(() => {
const S=()=>window.TVMarketSource;
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let observer;
function card(code){
 const name=S().name(code);
 return '<button class="tv-copy-ticker" data-copy-symbol="'+esc(code)+'">'+
 '<b class="tv-copy-logo">'+esc(name.slice(0,2).toUpperCase())+'</b>'+
 '<span><strong>'+esc(name)+'</strong><small>'+esc(code)+'</small></span>'+
 '<span class="tv-copy-price"><b>—</b><small>시세 미확인</small></span></button>';
}
function hydrate(node){
 if(node.dataset.ready)return;
 node.dataset.ready="1";
 const w=S().groups.flatMap(g=>g.widgets).find(w=>w.id===node.dataset.widget);
 const body=node.querySelector(".tv-copy-widget-body");
 if(["heatmap","map","curve"].includes(w.kind)){
  body.innerHTML='<div class="tv-copy-dataviz"><div class="tv-copy-mosaic">'+
  Array.from({length:28},()=>'<i></i>').join("")+'</div><b>'+esc(w.title)+
  '</b><small>원본 시각화 데이터 미연결</small></div>';
 }else if(w.kind==="calendar"){
  body.innerHTML='<div class="tv-copy-calendar">'+w.symbols.map(code=>
  '<div class="tv-copy-calendar-row">'+card(code)+
  '<small>행사일 확인 전</small></div>').join("")+'</div>';
 }else if(w.kind==="summary"){
  body.innerHTML='<div class="tv-copy-carousel" tabindex="0">'+w.symbols.map(card).join("")+
  '</div><div class="tv-copy-chart-space">종목을 선택하면 실제 5년 일봉 차트를 이곳에 표시합니다.</div>';
 }else{
  body.innerHTML='<div class="tv-copy-rank">'+w.symbols.map((code,i)=>
  '<div class="tv-copy-rank-item"><em>'+(i+1)+'</em>'+card(code)+'</div>').join("")+'</div>';
 }
}
function render(){
 const d=S(),root=document.getElementById("view");
 if(!d||!root)return;
 observer?.disconnect();
 root.innerHTML='<div class="tv-copy-home"><header class="tv-copy-hero">'+
 '<small>GLOBAL MARKETS</small><h1>모든 곳의 <span>시장</span></h1>'+
 '<p>세계 금융 시장, 시세·차트·상승·하락·경제 정보</p>'+
 '<button data-copy-source>시장 데이터 원장·공급원 ↗</button></header>'+
 '<nav class="tv-copy-tabs" aria-label="시장 영역 탐색">'+
 d.groups.map(g=>'<button data-copy-anchor="'+esc(g.id)+'">'+esc(g.title)+'</button>').join("")+
 '</nav>'+d.groups.map(g=>
 '<section class="tv-copy-section" id="copy-'+esc(g.id)+'">'+
 '<header class="tv-copy-section-heading"><div><h2>'+esc(g.title)+'</h2>'+
 '<p>'+esc(g.subtitle)+'</p></div>'+
 '<button data-copy-region="'+esc(g.id)+'">모두 보기 ›</button></header>'+
 '<div class="tv-copy-grid">'+g.widgets.map(w=>
 '<article class="tv-copy-widget'+(w.kind==="summary"?" featured":"")+
 '" data-widget="'+esc(w.id)+'"><header><h3>'+esc(w.title)+'</h3>'+
 '<button data-copy-widget="'+esc(w.id)+'">전체 보기 ›</button></header>'+
 '<div class="tv-copy-widget-body"><div class="tv-copy-skeleton">조회 준비 중…</div></div>'+
 '</article>').join("")+'</div></section>').join("")+
 '<footer class="tv-copy-foot">첨부 HTML에서 확인된 시장 구성과 종목 식별자를 사용했습니다. '+
 '저장된 일봉 외 현재가·실적·경제 정보는 연동 여부를 별도로 검증해야 합니다.</footer></div>';
 root.onclick=e=>{
  const b=e.target.closest("button");if(!b)return;
  if(b.hasAttribute("data-copy-source"))return window.tvMarketNavigate?.("market-sources");
  if(b.dataset.copyAnchor)return document.getElementById("copy-"+b.dataset.copyAnchor)
   ?.scrollIntoView({behavior:"smooth",block:"start"});
  if(b.dataset.copyRegion)return window.tvMarketOpenDetail?.(b.dataset.copyRegion,null);
  if(b.dataset.copyWidget){
   const w=d.groups.flatMap(g=>g.widgets).find(x=>x.id===b.dataset.copyWidget);
   return window.tvMarketOpenDetail?.(w?.section,w?.id);
  }
  if(b.dataset.copySymbol){
   const sym=d.symbol(b.dataset.copySymbol);
   if(!sym)return window.tvMarketNotLinked?.(b.dataset.copySymbol);
   const article=b.closest("[data-widget]");
   const w=d.groups.flatMap(g=>g.widgets).find(x=>x.id===article?.dataset.widget);
   if(w?.kind==="summary"&&window.TVMarketChart)return window.TVMarketChart.show(
    article.querySelector(".tv-copy-chart-space"),sym);
   window.tvMarketNavigate?.("chart",{symbol:sym});
  }
 };
 const all=[...root.querySelectorAll("[data-widget]")];
 if(!window.IntersectionObserver){all.forEach(hydrate);return;}
 observer=new IntersectionObserver(entries=>{
  for(const entry of entries)if(entry.isIntersecting){hydrate(entry.target);observer.unobserve(entry.target);}
 },{rootMargin:"400px"});
 all.forEach(node=>observer.observe(node));
}
window.TVMarketHome={render,widgets:()=>S()?.groups.flatMap(g=>g.widgets)||[]};
})();
