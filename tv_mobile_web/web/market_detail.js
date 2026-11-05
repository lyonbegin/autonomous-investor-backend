/* Markets detailed widget pages, original category tabs and actual ten-item
   scanner pagination. Ranking-specific parity is disclosed separately. */
"use strict";
(() => {
 const esc=x=>String(x??"").replace(/[&<>"']/g,c=>({
  "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
 }[c]));
 const fmt=v=>typeof v==="number"&&Number.isFinite(v)?
    v.toLocaleString("ko-KR",{maximumFractionDigits:5}):"—";
 let seq=0,page=1,sort="volume";
 const rankings={
  "stocks-volume-leaders":"volume",
  "market-movers-volatile-volume":"volatility",
  "stocks-gainers":"gainers","stocks-losers":"losers",
  "hotlist-coin-gainers":"gainers","hotlist-coin-losers":"losers",
  "world-stocks-biggest-companies":"market_cap",
  "most-traded":"volume"
 };
 function render(groupId,widgetId){
  const src=window.TVMarketSource;
  const g=src?.groups.find(x=>x.id===groupId)||src?.groups[0];
  if(!g)return;
  const w=g.widgets.find(x=>x.id===widgetId)||g.widgets[0],root=document.getElementById("view");
  if(!root)return;
  ++seq;page=1;sort="volume";
  root.innerHTML='<div class="tv-copy-detail"><button data-d-back class="tv-copy-back">← 전체 시장</button>'+
   '<header class="tv-copy-detail-head"><div><small>MARKETS / '+esc(g.title)+'</small>'+
   '<h1>'+esc(w.title)+'</h1><p>원본 화면의 세부 시장 위젯과 연결된 상세 화면</p></div>'+
   '<a href="https://kr.tradingview.com'+esc(w.href||g.href)+'" target="_blank" rel="noopener noreferrer">'+
   '원본 상세 보기 ↗</a></header>'+
   '<nav class="tv-copy-detail-tabs" aria-label="세부 시장 탭">'+g.widgets.map(x=>
   '<button data-d-widget="'+esc(x.id)+'"'+(x.id===w.id?' class="active"':'')+'>'+
   esc(x.title)+'</button>').join("")+'</nav>'+
   '<div class="tv-copy-detail-grid"><div><div class="tv-copy-detail-filter">'+
   '<label>정렬 <select id="tvCopySort"><option value="volume">거래량</option>'+
   '<option value="change">등락률</option><option value="close">가격</option>'+
   '<option value="market_cap_basic">시가총액</option></select></label>'+
   '<span>종목 목록 10개씩 조회</span></div>'+
   '<div id="tvCopyData">실제 시장 종목 조회 중…</div>'+
   '<div id="tvCopyPager"></div></div>'+
   '<aside class="tv-copy-detail-aside"><h3>원본 HTML의 종목들</h3>'+
   '<p>원본 2026-11-05 스냅샷 종목 코드이며 현재 가격이 아닙니다.</p>'+
   w.symbols.map(code=>'<button data-d-code="'+esc(code)+'">'+
    '<b>'+esc(src.name(code))+'</b><small>'+esc(code)+'</small></button>').join("")+
   '</aside></div></div>';
  root.querySelector("[data-d-back]").onclick=()=>window.tvMarketNavigate?.("markets");
  root.querySelectorAll("[data-d-widget]").forEach(b=>b.onclick=()=>window.tvMarketOpenDetail?.(g.id,b.dataset.dWidget));
  root.querySelectorAll("[data-d-code]").forEach(b=>b.onclick=()=>{
   const symbol=src.symbol(b.dataset.dCode);
   if(symbol)window.tvMarketNavigate?.("chart",{symbol});
   else window.tvMarketNotLinked?.(b.dataset.dCode);
  });
  root.querySelector("#tvCopySort").onchange=e=>{sort=e.target.value;page=1;load(g,w);};
  load(g,w);
 }
 async function load(g,w){
  const rows=document.getElementById("tvCopyData"),pager=document.getElementById("tvCopyPager");
  if(!rows||!pager)return;
  if(!g.scanner){
   rows.innerHTML='<p class="tv-copy-data-warning">이 시장의 실거래·경제 데이터 스캐너는 아직 연결되지 않았습니다. 원본 종목 식별자는 보존되어 있습니다.</p>';
   return;
  }
  const current=++seq;rows.textContent="실제 시장 종목 10개 조회 중…";
  const specific=!!rankings[w.id]&&sort==="volume";
  const url=specific?
   "/api/explore/ranking/"+encodeURIComponent(g.scanner)+"/"+rankings[w.id]+
    "?limit=10&offset="+((page-1)*10):
   "/api/markets/"+encodeURIComponent(g.scanner)+"?limit=10&offset="+
    ((page-1)*10)+"&order="+sort;
  try{
   const response=await fetch(url,{cache:"no-store"});
   if(!response.ok)throw Error("HTTP "+response.status);
   const result=await response.json();if(current!==seq||!rows.isConnected)return;
   const items=Array.isArray(result.items)?result.items:[];
   rows.innerHTML='<p class="tv-copy-data-warning">'+
    (specific?"실제 스캐너의 해당 정렬값을 사용했습니다. 원본 위젯과 완전한 필터 동등성은 미검증입니다.":
    "실제 시장 전체 종목을 조회했습니다. 이 위젯만의 전용 조건과 일치한다는 뜻은 아닙니다.")+
    '</p><div class="tv-copy-detail-table"><div class="tv-copy-detail-labels">'+
    '<span>종목</span><span>가격</span><span>변동률</span></div>'+
    items.map(x=>{
     const s=String(x.ticker||x.symbol||"").trim();
     return '<button data-d-chart="'+esc(s)+'"><span><b>'+esc(s)+'</b>'+
      '<small>'+esc(x.description||x.name||"")+'</small></span>'+
      '<strong>'+fmt(x.close)+'</strong><strong>'+fmt(x.change)+
      (typeof x.change==="number"?"%":"")+'</strong></button>';
    }).join("")+'</div>';
   rows.querySelectorAll("[data-d-chart]").forEach(b=>b.onclick=()=>window.tvMarketNavigate?.("chart",{symbol:b.dataset.dChart}));
   let total=result.total_count==null?Math.max(1,page+(items.length===10?1:0)):
    Math.max(1,Math.ceil(Number(result.total_count)/10));
   pager.innerHTML='<nav class="tv-copy-detail-pager"><button data-d-prev'+(page===1?' disabled':'')+
    '>이전</button><span>'+page+' / '+total+'페이지</span>'+
    '<button data-d-next'+(page>=total?' disabled':'')+'>다음</button>'+
    '<form><input type="number" name="page" min="1" max="'+total+'" value="'+page+
    '" aria-label="종목 페이지 직접 선택"><button type="submit">이동</button></form></nav>';
   pager.querySelector("[data-d-prev]").onclick=()=>{page=Math.max(1,page-1);load(g,w);};
   pager.querySelector("[data-d-next]").onclick=()=>{page=Math.min(total,page+1);load(g,w);};
   pager.querySelector("form").onsubmit=e=>{
    e.preventDefault();const n=Number(e.target.elements.page.value);
    if(Number.isSafeInteger(n)&&n>=1&&n<=total){page=n;load(g,w);}
   };
  }catch(error){
   if(current===seq&&rows.isConnected)
    rows.innerHTML='<p class="tv-copy-data-warning">원본 데이터 엔진 응답 실패: '+esc(error.message)+
     ' · 시험용 가격으로 대신 채우지 않았습니다.</p>';
  }
 }
 window.TVMarketDetail={render};
})();
