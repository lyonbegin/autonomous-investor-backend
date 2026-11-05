/* Mobile application parity lab. All prices are upstream-sourced. Never invent OHLCV. */
"use strict";
const $=id=>document.getElementById(id);
const esc=x=>String(x??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const money=n=>typeof n==="number"&&Number.isFinite(n)?n.toLocaleString("ko-KR",{maximumFractionDigits:5}):"—";
const mainTabs=[
 {id:"watchlist",label:"관심목록",icon:"☆"},
 {id:"markets",label:"마켓",icon:"▥"},
 {id:"chart",label:"차트",icon:"⌁"},
 {id:"ideas",label:"아이디어",icon:"☷"},
 {id:"menu",label:"메뉴",icon:"☰"},
];
const mainPages={"market-detail":"마켓 상세","market-sources":"시장 데이터 원장",markets:"마켓",watchlist:"관심목록",chart:"차트",ideas:"아이디어",
 menu:"전체 메뉴",alerts:"알림",news:"뉴스",calendar:"경제 캘린더",
 brokers:"브로커",settings:"설정",profile:"프로필",features:"전체 기능 검수",
 search:"종목 검색",symbols:"종목 상세",indicators:"지표",drawings:"그리기 도구",
 replay:"바 리플레이",community:"커뮤니티",billing:"구독",
 widgets:"Android 위젯",sharing:"공유·미디어",system:"시스템·연동"};
const localKey="tv-android-web-independent-lab-v1";
function getSaved(){try{const parsed=JSON.parse(localStorage.getItem(localKey)||"{}");return parsed&&typeof parsed==="object"?parsed:{};}catch{return{};}}
let saved=getSaved();
let state={
 page:"markets",market:"korea",marketGroup:"주식",marketRows:[],
 marketSection:"stocks",marketWidget:null,
 marketTotal:null,marketOffset:0,marketSort:"volume",
 chartSymbol:"NASDAQ:AAPL",chartRange:"60M",theme:saved.theme==="dark"?"dark":"light",
 watchlists:Array.isArray(saved.watchlists)?saved.watchlists:[{id:"default",name:"기본 관심목록",symbols:[]}],
 currentList:saved.currentList||"default",localAlerts:Array.isArray(saved.alerts)?saved.alerts:[],
 sourceCatalog:null,marketRequest:0,searchTimer:null,ideas:[],
};
function persist(){try{localStorage.setItem(localKey,JSON.stringify({
 theme:state.theme,watchlists:state.watchlists,
 currentList:state.currentList,alerts:state.localAlerts
}));}catch{}}
function navigate(page, params={}){
 if(!mainPages[page])page="menu";
 state.page=page;
 if(params.market)state.market=params.market;
 if(params.symbol)state.chartSymbol=params.symbol;
 if(params.section)state.marketSection=params.section;
 if(Object.prototype.hasOwnProperty.call(params,"widget"))state.marketWidget=params.widget;
 window.location.hash="#/"+page+(page==="chart"?"/"+encodeURIComponent(state.chartSymbol):
  page==="market-detail"?"/"+encodeURIComponent(state.marketSection)+
  (state.marketWidget?"/"+encodeURIComponent(state.marketWidget):""):"");
 render();
 window.scrollTo(0,0);
}
function activeRoot(){
 if(state.page==="market-detail"||state.page==="market-sources")return "markets";
 return mainTabs.some(x=>x.id===state.page)?state.page:"menu";
}
function updateNavigation(){
 const html=mainTabs.map(tab=>{
 const active=activeRoot()===tab.id;
 return '<button class="nav-btn'+(active?" active":"")+'" data-nav="'+tab.id+'"><span class="nav-icon">'+tab.icon+'</span><span>'+tab.label+'</span></button>';
 }).join("");
 $("desktopNav").innerHTML=html;
 $("mobileNav").innerHTML=mainTabs.map(tab=>'<button class="bottom-tab'+
 (activeRoot()===tab.id?" active":"")+'" data-nav="'+tab.id+'"><span class="bottom-icon">'+tab.icon+
 '</span><span>'+tab.label+'</span></button>').join("");
 document.querySelectorAll("[data-nav]").forEach(node=>node.onclick=()=>navigate(node.dataset.nav));
}
function toast(message){
 const node=$("toast");node.textContent=message;node.classList.add("show");
 clearTimeout(toast.timer);toast.timer=setTimeout(()=>node.classList.remove("show"),3500);
}
function modal(title,content,actions=[]){
 const wrap=$("modalOverlay");
 $("modalCard").innerHTML='<h2>'+esc(title)+'</h2>'+content+'<div class="modal-actions"><button class="btn" id="cancelModal">취소</button>'+
 actions.map((a,i)=>'<button class="btn '+(a.primary?"primary":"")+'" data-modal-action="'+i+'">'+esc(a.label)+'</button>').join("")+'</div>';
 wrap.hidden=false;
 $("cancelModal").onclick=()=>{wrap.hidden=true};
 $("modalCard").querySelectorAll("[data-modal-action]").forEach(b=>{
 b.onclick=()=>{const action=actions[Number(b.dataset.modalAction)];if(action)action.run();};
 });
}
function closeModal(){$("modalOverlay").hidden=true;}
function screenHeader(kicker,title,description,action=""){
 return '<div class="screen-head"><div><div class="screen-kicker">'+esc(kicker)+'</div>'+
 '<h1>'+esc(title)+'</h1><p>'+esc(description)+'</p></div>'+
 (action?'<div class="screen-actions">'+action+'</div>':"")+'</div>';
}
function empty(title,description,icon="○"){
 return '<div class="empty-state"><span class="empty-icon">'+icon+'</span><b>'+esc(title)+'</b><br>'+esc(description)+'</div>';
}
function disclosure(message){
 return '<div class="disclaimer">'+message+'</div>';
}
function setContent(html){$("view").innerHTML=html;updateNavigation();$("breadcrumbs").textContent=mainPages[state.page]||"마켓";}
async function request(path){
 const response=await fetch(path,{cache:"no-store",headers:{"Accept":"application/json"}});
 let body;try{body=await response.json()}catch{body={detail:"데이터 서버 응답이 JSON이 아닙니다."}}
 if(!response.ok){
  const err=new Error(typeof body.detail==="string"?body.detail:
     body.detail?.code||"실제 데이터 연결이 실패했습니다.");
  err.status=response.status;throw err;
 }
 return body;
}
function formatPct(value){
 if(typeof value!=="number"||!Number.isFinite(value))return'<span>—</span>';
 return '<span class="'+(value>=0?"up":"down")+'">'+(value>0?"+":"")+money(value)+'%</span>';
}
function rowSymbol(row){return String(row.ticker||row.symbol||row.name||"").trim();}
function makeMarketTable(rows){
 if(!rows.length)return empty("조회된 종목 없음","현재 응답에서 종목 데이터가 확인되지 않았습니다. 임의 종목은 채우지 않습니다.");
 return '<div class="table-scroll"><table class="stocks-table"><thead><tr><th>심볼 / 종목</th>'+
 '<th>거래소</th><th class="num">현재가</th><th class="num">변동률</th><th class="num">거래량</th><th>차트</th><th>관심</th></tr></thead><tbody>'+
 rows.map(row=>{
  const symbol=rowSymbol(row);
  const exchange=row.exchange||symbol.split(":")[0]||"—";
  const val=row.close??null;
  return '<tr><td><span class="stock-symbol">'+esc(symbol)+'</span><span class="stock-name">'+
   esc(row.description||row.name||"TradingView scanner")+'</span></td><td>'+esc(exchange)+'</td>'+
   '<td class="num">'+money(val)+'</td><td class="num">'+formatPct(row.change)+'</td>'+
   '<td class="num">'+money(row.volume)+'</td><td><button class="btn small" data-symbol="'+
   esc(symbol)+'">차트</button></td><td><button class="btn small icon" data-watch-symbol="'+
   esc(symbol)+'" title="관심목록 추가">☆</button></td></tr>';
 }).join("")+'</tbody></table></div>';
}
function wireMarketRows(container=$("view")){
 container.querySelectorAll("[data-symbol]").forEach(button=>button.onclick=()=>navigate("chart",{symbol:button.dataset.symbol}));
 container.querySelectorAll("[data-watch-symbol]").forEach(button=>button.onclick=()=>addToWatchlist(button.dataset.watchSymbol));
}
function currentWatchlist(){
 return state.watchlists.find(x=>x.id===state.currentList)||state.watchlists[0];
}
function addToWatchlist(symbol){
 if(!symbol||!/^[A-Z0-9_.!/\-]{1,40}:[A-Z0-9_.!/\-]{1,70}$/i.test(symbol)){
  toast("거래소:심볼 형식이 확인되지 않아 등록하지 않았습니다.");return;
 }
 if(!state.watchlists.length)state.watchlists=[{id:"default",name:"기본 관심목록",symbols:[]}];
 const list=currentWatchlist();if(!list){toast("관심목록이 없습니다");return;}
 if(!list.symbols.includes(symbol))list.symbols.push(symbol);
 persist();toast("브라우저 관심목록에 저장했습니다. 서버 동기화는 미연결입니다.");
}
function renderMarketSources(){
 const categories=state.sourceCatalog?.markets||[];
 const byGroup={};
 categories.forEach(x=>(byGroup[x.group]??=[]).push(x));
 const groupNames=Object.keys(byGroup);
 setContent(
 screenHeader("MARKETS · LIVE SCANNER","마켓","기존 TradingView 연동 서비스가 반환하는 실제 종목 목록입니다.",
 '<button id="marketReload" class="btn">↻ 다시 조회</button>')+
 disclosure("상장 목록과 5년 일봉 확보는 별개입니다. 이 페이지는 기존 스캐너의 조회 응답만 표시하며 전 종목 수집 완료를 뜻하지 않습니다.")+
 '<section class="surface box-pad" id="fullGlobalMarketCatalog">'+
 empty("전체 세계 시장 원장 조회 중","자산 9개 유형, ISO 전체 국가 및 모든 공개 데이터 공급원 행을 불러옵니다.","⌛")+'</section>'+
 '<div class="section-line"><h2 class="section-title">현재 연결된 시장 스캐너 · 부분 데이터 엔진</h2></div>'+
 '<div class="filter-tabs" id="marketGroups">'+groupNames.map(g=>'<button class="filter-tab'+
 (g===state.marketGroup?" active":"")+'" data-group="'+esc(g)+'">'+esc(g)+'</button>').join("")+'</div>'+
 '<div class="card-grid" id="marketTiles">'+(byGroup[state.marketGroup]||[]).map(m=>
 '<button class="market-card" data-market="'+esc(m.id)+'"><span class="market-icon">'+
 esc(m.icon)+'</span><strong>'+esc(m.name)+'</strong><small>실시간 조회 · 시장별</small></button>').join("")+'</div>'+
 '<div class="section-line"><h2 class="section-title" id="marketCurrentName">시장 종목</h2><span class="pill" id="marketCount">조회 대기</span></div>'+
 '<div class="input-wrap"><label class="sr-only" for="marketSort">정렬</label><select class="field" id="marketSort" style="max-width:180px"><option value="volume">거래량</option><option value="change">변동률</option><option value="close">가격</option><option value="name">이름</option><option value="market_cap_basic">시가총액</option></select></div>'+
 '<div class="surface" id="marketContent">'+empty("시장 데이터를 조회 중","실제 스캐너 응답을 불러오는 중입니다.","⌛")+'</div>'+
 '<div id="marketPager" class="world-pager" aria-label="시장 종목 페이지 이동"></div>'
 );
 $("marketGroups").querySelectorAll("[data-group]").forEach(b=>b.onclick=()=>{
  state.marketGroup=b.dataset.group;
  const selected=byGroup[state.marketGroup]?.[0];if(selected)state.market=selected.id;
  state.marketOffset=0;renderMarketSources();
 });
 $("marketTiles").querySelectorAll("[data-market]").forEach(b=>b.onclick=()=>{
  state.market=b.dataset.market;state.marketOffset=0;loadMarket();
 });
 $("marketSort").value=state.marketSort;
 $("marketSort").onchange=()=>{state.marketSort=$("marketSort").value;state.marketOffset=0;loadMarket()};
 $("marketReload").onclick=loadMarket;
 loadMarket();
 if(typeof window.loadGlobalMarketsPanel==="function")window.loadGlobalMarketsPanel();
}
function renderMarkets(){
 setContent("");
 if(window.TVMarketHome)window.TVMarketHome.render();
 else $("view").innerHTML=empty("마켓 홈 코드 연결 실패","원본형 화면을 불러올 수 없습니다.");
}
function renderMarketDetail(){
 setContent("");
 if(window.TVMarketDetail)window.TVMarketDetail.render(state.marketSection,state.marketWidget);
 else $("view").innerHTML=empty("시장 상세 코드 연결 실패","상세 화면을 불러올 수 없습니다.");
}
window.tvMarketNavigate=(page,params={})=>navigate(page,params);
window.tvMarketOpenDetail=(section,widget)=>navigate("market-detail",{section,widget});
window.tvMarketNotLinked=code=>toast("원본 심볼 "+code+"의 정확한 거래소 접두사를 아직 검증하지 않았습니다.");
async function loadMarket(){
 const current=state.sourceCatalog?.markets?.find(m=>m.id===state.market);
 const title=$("marketCurrentName");if(!title)return;
 title.textContent=(current?.name||state.market)+" · 종목";
 $("marketCount").textContent="로드 중";
 $("marketContent").innerHTML=empty("실제 스캐너 조회 중","가격과 거래량을 임의로 표시하지 않습니다.","⌛");
 const seq=++state.marketRequest;
 try{
  const x=await request("/api/markets/"+encodeURIComponent(state.market)+
   "?limit=10&offset="+state.marketOffset+"&order="+encodeURIComponent(state.marketSort));
  if(seq!==state.marketRequest||state.page!=="market-sources")return;
  state.marketRows=x.items;
  state.marketTotal=x.total_count;
  $("marketCount").textContent=x.total_count==null?
    "이번 응답 "+x.items.length+"개":money(x.total_count)+"개 · 서버 표시 수";
  $("marketContent").innerHTML=makeMarketTable(x.items);
  renderMarketPagination(x);
  wireMarketRows();
 }catch(err){
  if(seq!==state.marketRequest||state.page!=="market-sources")return;
  $("marketCount").textContent="조회 실패";
  $("marketContent").innerHTML='<div class="empty-state error-state"><b>실제 데이터 연결 실패</b><br>'+
   esc(err.message)+'<br>원본 데이터를 만들거나 이전 성공 응답을 현재 시세로 표시하지 않습니다.</div>';
   if($("marketPager"))$("marketPager").innerHTML="";
 }
}
function renderMarketPagination(response){
 const host=$("marketPager");if(!host)return;
 const page=Math.floor(state.marketOffset/10)+1;
 const total=Number(response.total_count);
 const hasTotal=response.total_count!==null&&response.total_count!==undefined&&
   Number.isFinite(total)&&total>=0;
 const max=hasTotal?Math.max(1,Math.ceil(total/10)):null;
 const last=hasTotal?max:page+(response.items.length===10?1:0);
 const start=Math.max(1,Math.min(page-2,Math.max(1,last-4)));
 const end=Math.min(last,start+4);
 const buttons=[];
 if(start>1)buttons.push(1);
 for(let n=start;n<=end;n++)if(!buttons.includes(n))buttons.push(n);
 if(end<last&&!buttons.includes(last))buttons.push(last);
 host.innerHTML='<button type="button" class="btn small" data-scanner-page="'+(page-1)+'"'+
 (page<=1?' disabled':'')+'>이전</button>'+
 buttons.map(n=>'<button type="button" class="btn small world-page-btn'+
 (n===page?' active':'')+'" data-scanner-page="'+n+'"'+
 (n===page?' aria-current="page"':'')+'>'+n+'</button>').join("")+
 '<button type="button" class="btn small" data-scanner-page="'+(page+1)+'"'+
 ((hasTotal?page>=max:response.items.length<10)?' disabled':'')+'>다음</button>'+
 '<form id="marketJumpForm" class="world-jump-form"><label>페이지 이동 <input type="number" min="1"'+
 (max?' max="'+max+'"':'')+' name="page" class="field world-page-number" value="'+page+
 '" aria-label="시장 종목 이동 페이지"></label><button type="submit" class="btn small">이동</button></form>'+
 '<span class="world-page-status">'+page+'/'+(max||"미확인")+'페이지 · 10개씩 조회</span>';
 const go=n=>{
  if(!Number.isSafeInteger(n)||n<1||hasTotal&&n>max)return;
  state.marketOffset=(n-1)*10;
  loadMarket();
 };
 host.querySelectorAll("[data-scanner-page]").forEach(b=>b.onclick=()=>go(Number(b.dataset.scannerPage)));
 $("marketJumpForm").onsubmit=event=>{
  event.preventDefault();
  go(Number($("marketJumpForm").querySelector('input[name="page"]').value));
 };
}
function renderWatchlist(){
 const list=currentWatchlist();
 setContent(screenHeader("WATCHLIST · LOCAL DRAFTS","관심목록","추가·삭제·목록 관리는 브라우저에 임시 저장됩니다.",
 '<button class="btn primary" id="newList">+ 새 목록</button>')+
 disclosure("TradingView 계정의 실제 관심목록과 동기화되지 않습니다. 앱 복제 UI의 사용자 조작 구현이며, 서버 관심목록 기능은 미연결입니다.")+
 '<div class="filter-tabs">'+state.watchlists.map(w=>'<button class="filter-tab'+
 (w.id===state.currentList?" active":"")+'" data-list="'+esc(w.id)+'">'+esc(w.name)+'</button>').join("")+'</div>'+
 '<div class="surface box-pad"><div class="split-actions"><h2 class="section-title" style="margin:0">'+esc(list?.name||"관심목록")+
 '</h2><div><button id="renameList" class="btn small">이름 수정</button> <button id="deleteList" class="btn small">삭제</button></div></div>'+
 '<div class="input-wrap" style="margin-top:18px"><input id="addWatchSymbol" class="field" placeholder="예: NASDAQ:AAPL" autocomplete="off"><button class="btn primary" id="addWatch">추가</button></div>'+
 (list?.symbols?.length?'<div class="list-stack">'+list.symbols.map(s=>
 '<div class="list-row"><span class="row-icon">☆</span><div class="grow"><h3>'+esc(s)+'</h3><p>개별 차트에서 현재 데이터 확인</p></div><button class="btn small" data-symbol="'+esc(s)+'">차트</button><button class="btn small" data-remove="'+esc(s)+'">제거</button></div>').join("")+'</div>':
 empty("관심 종목이 없습니다","거래소:심볼을 입력해 추가할 수 있습니다."))+'</div>');
 $("newList").onclick=()=>modal("새 관심목록 만들기",
 '<input class="field" id="newListName" maxlength="60" placeholder="목록 이름">',
 [{label:"만들기",primary:true,run:()=>{const name=$("newListName").value.trim();
 if(!name)return toast("이름을 입력하세요");if(state.watchlists.length>=30)return toast("목록 제한 30개");
 const id="list-"+Date.now();state.watchlists.push({id,name,symbols:[]});state.currentList=id;
 persist();closeModal();renderWatchlist();}}]);
 $("view").querySelectorAll("[data-list]").forEach(b=>b.onclick=()=>{
  state.currentList=b.dataset.list;persist();renderWatchlist();
 });
 $("addWatch").onclick=()=>{addToWatchlist($("addWatchSymbol").value.trim().toUpperCase());renderWatchlist()};
 $("renameList").onclick=()=>modal("관심목록 이름 변경",'<input class="field" id="newListName" maxlength="60" value="'+esc(list?.name)+'">',
 [{label:"저장",primary:true,run:()=>{const name=$("newListName").value.trim();if(!name)return;
 list.name=name;persist();closeModal();renderWatchlist()}}]);
 $("deleteList").onclick=()=>modal("관심목록 삭제","<p>이 목록의 브라우저 로컬 데이터만 삭제합니다.</p>",
 [{label:"삭제",primary:true,run:()=>{
 if(state.watchlists.length===1)return toast("최소 한 개 목록은 유지합니다.");
 state.watchlists=state.watchlists.filter(x=>x.id!==list.id);
 state.currentList=state.watchlists[0].id;persist();closeModal();renderWatchlist()}}]);
 $("view").querySelectorAll("[data-remove]").forEach(b=>b.onclick=()=>{
  list.symbols=list.symbols.filter(s=>s!==b.dataset.remove);persist();renderWatchlist();
 });
 wireMarketRows();
}
function addWidget(symbol){
 const container=$("tvWidget");if(!container)return;
 container.innerHTML="";
 const host=document.createElement("div");
 host.className="tradingview-widget-container tv-chart-widget";
 host.innerHTML='<div class="tradingview-widget-container__widget" style="height:100%;width:100%"></div>';
 const script=document.createElement("script");
 script.type="text/javascript";script.async=true;
 script.src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
 script.textContent=JSON.stringify({
  autosize:true,symbol,interval:"D",timezone:"Asia/Seoul",
  theme:state.theme==="dark"?"dark":"light",style:"1",locale:"kr",
  backgroundColor:state.theme==="dark"?"#151e2a":"#ffffff",
  allow_symbol_change:true,calendar:false,hide_top_toolbar:false,
  save_image:false,withdateranges:true,
  range:"60M",studies:[],support_host:"https://www.tradingview.com"
 });
 host.appendChild(script);container.appendChild(host);
}
function renderChart(){
 setContent(screenHeader("CHARTS · EMBEDDED OFFICIAL WIDGET","차트","기간은 최근 5년, 시간봉은 일봉(1D)입니다.",
 '<button class="btn" id="chartShare">↗ 링크 공유</button>')+
 disclosure("차트는 TradingView의 공식 임베드 위젯이 직접 실시간 데이터를 요청합니다. <strong>우리 서버의 5년 일봉 저장 완료나 원본 Android 차트 기능 동등성이 아닙니다.</strong>")+
 '<div class="chart-selectors"><input id="chartSymbolInput" class="field" aria-label="거래소:심볼" placeholder="NASDAQ:AAPL" value="'+esc(state.chartSymbol)+'">'+
 '<select id="chartTimeframe" class="field" aria-label="시간봉"><option value="1D">일봉 (1D)</option></select>'+
 '<select id="chartRange" class="field" aria-label="기간"><option value="60M">최근 5년</option></select>'+
 '<button class="btn primary" id="chartLoad">차트 열기</button><button class="btn" id="chartWatch">☆ 관심</button></div>'+
 '<div class="chart-frame"><div id="tvWidget" class="tv-chart-widget"><div class="chart-fallback">차트 연결 중…</div></div></div>'+
 '<div class="toolbar-note">위 차트는 TradingView 공식 웹 차트입니다. 아래 별도의 5년 일봉 수집은 기존 TradingView 차트 WebSocket 경로의 실제 OHLCV를 관찰하여 자체 연구 저장소에 보관합니다.</div>'+
 '<section class="surface box-pad" id="storedDaily"><div class="section-line"><h2 class="section-title" style="margin:0">5년 일봉 · 자체 저장 데이터</h2><span class="pill" id="dailyState">조회 중</span></div>'+
 '<p class="toolbar-note">기존 TradingView 차트 링크 /chart/ 및 프로젝트의 기존 WF-02 WebSocket 파서를 재사용합니다. Yahoo/임의 시세를 섞지 않습니다.</p>'+
 '<div class="screen-actions" style="flex-wrap:wrap;margin:17px 0"><button class="btn primary" id="collectDaily">현재 종목 5년 일봉 수집·저장</button>'+
 '<button class="btn" id="readDaily">저장 데이터 새로고침</button></div>'+
 '<div id="dailySummary" class="notice-block">저장된 실제 봉의 개수와 거래일 범위를 조회합니다.</div>'+
 '<div class="chart-frame" style="min-height:255px"><canvas id="dailyCanvas" width="1000" height="260" style="width:100%;height:260px;display:block" aria-label="저장된 5년 일봉 종가 그래프"></canvas></div>'+
 '<div id="dailyLast" class="toolbar-note">저장되지 않은 봉을 임의로 표시하지 않습니다.</div></section>'+
 '<div class="section-title">차트 관련 기능</div>'+
 '<div class="list-stack">'+[
  ["지표·분석","indicators","지표 검색과 템플릿의 모바일 웹 동등성 조사"],
  ["그리기 도구","drawings","선 도구·객체 편집/잠금"],
  ["바 리플레이","replay","재생·정지·과거 시점 이동"],
  ["차트 검수","features","TV-071~TV-153 기능 원장 확인"]
 ].map(x=>'<button class="list-row" style="text-align:left;color:inherit;cursor:pointer" data-page="'+x[1]+'"><span class="row-icon">⌁</span><div class="grow"><h3>'+x[0]+'</h3><p>'+x[2]+'</p></div><span>›</span></button>').join("")+'</div>');
 $("chartLoad").onclick=()=>{const sym=$("chartSymbolInput").value.trim().toUpperCase();
 if(!/^[A-Z0-9_.!/\-]{1,40}:[A-Z0-9_.!/\-]{1,70}$/.test(sym))return toast("거래소:심볼 형식으로 입력해 주세요");
 state.chartSymbol=sym;navigate("chart",{symbol:sym});};
 $("chartWatch").onclick=()=>addToWatchlist(state.chartSymbol);
 $("chartShare").onclick=()=>{const url="https://www.tradingview.com/chart/?symbol="+encodeURIComponent(state.chartSymbol)+"&interval=D";
 if(navigator.share)navigator.share({url,title:state.chartSymbol}).catch(()=>{});
 else if(navigator.clipboard)navigator.clipboard.writeText(url).then(()=>toast("원본 차트 링크를 복사했습니다."));
 else toast(url);
 };
 wirePageLinks();addWidget(state.chartSymbol);wireStoredDaily(state.chartSymbol);
}
function drawStoredDaily(bars){
 const canvas=$("dailyCanvas");if(!canvas)return;
 const g=canvas.getContext("2d"),w=canvas.width,h=canvas.height;
 g.clearRect(0,0,w,h);
 if(!Array.isArray(bars)||!bars.length){
  g.fillStyle="#8391a4";g.font="15px Arial";
  g.fillText("저장된 실제 5년 일봉 데이터가 없습니다.",24,70);return;
 }
 const obs=bars.filter(b=>typeof b.close==="number"&&Number.isFinite(b.close));
 if(obs.length<2){g.fillStyle="#8391a4";g.fillText("표시 가능한 일봉이 부족합니다.",24,60);return;}
 const min=Math.min(...obs.map(b=>b.close)),max=Math.max(...obs.map(b=>b.close)),span=max-min||1;
 const left=75,right=15,top=23,bottom=35,W=w-left-right,H=h-top-bottom;
 g.font="12px Arial";g.strokeStyle="#e4eaf1";g.fillStyle="#7b8899";g.lineWidth=1;
 for(let i=0;i<=4;i++){
  const y=top+i*H/4;g.beginPath();g.moveTo(left,y);g.lineTo(w-right,y);g.stroke();
  const val=max-i*span/4;g.fillText(val.toLocaleString("ko-KR",{maximumFractionDigits:2}),5,y+4);
 }
 g.beginPath();obs.forEach((b,i)=>{
  const x=left+i*W/(obs.length-1);
  const y=top+H-(b.close-min)/span*H;
  if(i===0)g.moveTo(x,y);else g.lineTo(x,y);
 });
 g.strokeStyle="#2464e7";g.lineWidth=2;g.stroke();
 g.fillStyle="#788698";g.fillText(new Date(obs[0].time_ms).toISOString().slice(0,10),left,h-10);
 g.fillText(new Date(obs[obs.length-1].time_ms).toISOString().slice(0,10),w-110,h-10);
}
async function loadStoredDaily(symbol){
 const host=$("dailySummary");if(!host||symbol!==state.chartSymbol)return;
 try{
  const res=await request("/api/chart/status?symbol="+encodeURIComponent(symbol));
  if(symbol!==state.chartSymbol||state.page!=="chart")return;
  const stateEl=$("dailyState");
  if(!stateEl)return;
  stateEl.className="pill "+(res.saved?(res.five_year_extent_covered?"green":"warn"):"red");
  stateEl.textContent=res.saved?(res.five_year_extent_covered?"5년 시작/끝 도달":"일부만 저장"):"미확보";
  if(!res.saved){
   host.textContent="해당 종목에 저장된 TradingView 5년 일봉이 없습니다. 사용자가 수집 버튼을 눌러야 실제 요청을 시작합니다.";
   drawStoredDaily([]);return;
  }
  const payload=await request("/api/chart/history?symbol="+encodeURIComponent(symbol));
  if(symbol!==state.chartSymbol||state.page!=="chart")return;
  const b=payload.bars||[],meta=payload.metadata,q=payload.quality||{};
  const ratio=typeof q.daily_date_coverage_ratio==="number"?
    (q.daily_date_coverage_ratio*100).toFixed(2)+"%":"미검증";
  host.textContent="실제 저장 "+Number(meta.bar_count).toLocaleString("ko-KR")+
    "봉 · 최초 "+(b.length?new Date(b[0].time_ms).toISOString().slice(0,10):"—")+
    " · 최종 "+(b.length?new Date(b[b.length-1].time_ms).toISOString().slice(0,10):"—")+
    " · 요청 시작 "+meta.requested_start+
    " · 확보율 "+ratio+" ("+(q.calendar_assumption==="24x7"?"매일":"평일")+" 기준)"+
    " · "+(meta.five_year_extent_covered?"5년 일봉 기본 품질검사 통과":"5년 일봉 확보 미완료")+
    " · 거래소별 공식 휴장일 대조 미실시";
  $("dailyLast").textContent="출처: TradingView 기존 차트 WebSocket · 파일 SHA-256 검증 · 마지막 저장 "+meta.stored_at;
  drawStoredDaily(b);
 }catch(err){
  if($("dailySummary"))host.textContent="저장 데이터 조회 실패: "+err.message;
 }
}
async function collectStoredDaily(symbol){
 const button=$("collectDaily");if(!button)return;
 button.disabled=true;
 const box=$("dailySummary");box.textContent="TradingView 공식 차트 링크를 열어 5년 1D를 요청하고, 실제 WebSocket 수신 봉을 검사 중입니다.";
 try{
  const resp=await fetch("/api/chart/collect",{method:"POST",
   headers:{"Content-Type":"application/json"},
   body:JSON.stringify({symbol,years:5,interval:"1D"})});
  const job=await resp.json();
  if(!resp.ok)throw Error(typeof job.detail==="string"?job.detail:job.detail?.code||"수집 요청 실패");
  if(job.state!=="running")throw Error("수집이 시작되지 않았습니다.");
  const id=job.id;
  for(let k=0;k<120;k++){
   if(state.page!=="chart"||state.chartSymbol!==symbol)return;
   await new Promise(done=>setTimeout(done,2500));
   const status=await request("/api/chart/jobs/current");
   if(status.id!==id)throw Error("다른 수집 작업이 현재 작업을 대체했습니다.");
   if(status.state==="running"){
    box.textContent="실제 TradingView 차트 수신 대기 중 · "+symbol+
     " · 이력 부족 시 화면을 과거로 이동해 추가 수신을 요청합니다.";continue;
   }
   if(status.state==="completed"||status.state==="saved_partial"){
    toast(status.state==="completed"?"5년 일봉 저장 완료 (거래소 결측 별도 검증)":"일부 일봉만 저장됨 · 5년 날짜 범위 미달");
    await loadStoredDaily(symbol);return;
   }
   throw Error(status.reason||"실제 차트 OHLCV 수집 실패");
  }
  throw Error("작업 조회 제한 시간 초과. 나중에 저장 상태를 다시 확인하세요.");
 }catch(err){
  if($("dailySummary"))box.textContent="5년 일봉 수집·저장 실패: "+err.message;
  toast("수집 실패. 완료로 표시하지 않습니다.");
 }finally{if($("collectDaily"))button.disabled=false;}
}
function wireStoredDaily(symbol){
 $("readDaily").onclick=()=>loadStoredDaily(symbol);
 $("collectDaily").onclick=()=>collectStoredDaily(symbol);
 drawStoredDaily([]);
 loadStoredDaily(symbol);
}
function renderIdeas(){
 setContent(screenHeader("IDEAS · LIVE FEED","아이디어","기존 TradingView 아이디어 서버 조회를 연결합니다.",
 '<button class="btn" id="ideasRefresh">↻ 새로고침</button>')+
 disclosure("좋아요·댓글·게시물 업로드는 실제 계정에 연결하지 않았습니다. 조회된 아이디어만 표시합니다.")+
 '<div class="filter-tabs"><button class="filter-tab active" data-idea-sort="trending">인기</button>'+
 '<button class="filter-tab" data-idea-sort="recent">최신</button></div>'+
 '<div id="ideasList" class="list-stack">'+empty("아이디어 요청 중","실제 데이터 서버의 응답을 기다리는 중입니다.","⌛")+'</div>');
 let current="trending";const load=async()=>{
 $("ideasList").innerHTML=empty("아이디어 가져오는 중","서버 응답이 오기 전까지 게시물을 생성하지 않습니다.","⌛");
 try{const body=await request("/api/ideas?sort="+current+"&page=1");
 if(state.page!=="ideas")return;
 const data=body.data||{};
 const rows=Array.isArray(data.items)?data.items:Array.isArray(data.ideas)?data.ideas:[];
 $("ideasList").innerHTML=rows.length?rows.slice(0,50).map(x=>{
  const title=x.title||x.name||x.description||"제목 정보 없음";
  const desc=String(x.description||x.summary||x.text||"");
  const url=String(x.url||"");
  return '<article class="list-row"><span class="row-icon">✎</span><div class="grow"><h3>'+
   esc(title)+'</h3><p>'+esc(desc.slice(0,160))+'</p></div>'+
   (url.startsWith("https://")?'<a class="btn small" href="'+esc(url)+'" target="_blank" rel="noopener">원본 보기</a>':"")+'</article>';
 }).join(""):empty("실제 게시물 응답 없음","응답에 조회 가능한 아이디어 배열이 없습니다.");
 }catch(e){$("ideasList").innerHTML=empty("아이디어 서버 연결 실패",e.message,"!");}};
 $("ideasRefresh").onclick=load;
 $("view").querySelectorAll("[data-idea-sort]").forEach(b=>b.onclick=()=>{
  current=b.dataset.ideaSort;
  $("view").querySelectorAll("[data-idea-sort]").forEach(x=>x.classList.toggle("active",x===b));
  load();
 });load();
}
function renderAlerts(){
 setContent(screenHeader("ALERTS · LOCAL DRAFTS","알림","생성한 알림 조건을 브라우저에 임시 저장합니다.",
 '<button class="btn primary" id="newAlert">+ 알림 생성</button>')+
 disclosure("알림 조건은 초안으로만 저장됩니다. 서버 평가, 푸시 알림, 이메일 발송, 브로커 주문은 <b>실행되지 않습니다.</b>")+
 (state.localAlerts.length?'<div class="list-stack">'+state.localAlerts.map((x,i)=>
 '<div class="list-row"><span class="row-icon">♧</span><div class="grow"><h3>'+esc(x.symbol)+' · '+esc(x.condition)+' '+money(x.target)+'</h3><p>'+
 esc(x.memo||"브라우저 초안")+' · 서버 미연결</p></div><span class="pill warn">초안</span><button class="btn small" data-delete-alert="'+i+'">삭제</button></div>').join("")+'</div>':
 '<div class="surface">'+empty("알림 초안이 없습니다","새 알림을 만들어 테스트할 수 있습니다.","♧")+'</div>'));
 $("newAlert").onclick=()=>modal("알림 조건 초안",
 '<label>심볼</label><input class="field" id="alertSymbol" placeholder="NASDAQ:AAPL" value="'+esc(state.chartSymbol)+'">'+
 '<label style="display:block;margin-top:12px">조건</label><select class="field" id="alertCondition"><option value="상향 돌파">상향 돌파</option><option value="하향 이탈">하향 이탈</option></select>'+
 '<label style="display:block;margin-top:12px">기준 가격</label><input class="field" type="number" id="alertPrice" step="any" min="0">'+
 '<label style="display:block;margin-top:12px">메모</label><input class="field" id="alertMemo" maxlength="120" placeholder="선택사항">'+
 '<p>실제 알림을 감시하거나 보내지 않습니다.</p>',
 [{label:"초안 저장",primary:true,run:()=>{
 const s=$("alertSymbol").value.trim().toUpperCase(),n=Number($("alertPrice").value);
 if(!/^[A-Z0-9_.!/\-]{1,40}:[A-Z0-9_.!/\-]{1,70}$/.test(s)||!Number.isFinite(n)||n<=0)
 return toast("심볼과 기준 가격을 확인해 주세요.");
 state.localAlerts.push({id:Date.now(),symbol:s,condition:$("alertCondition").value,target:n,memo:$("alertMemo").value});
 persist();closeModal();renderAlerts();
 }}]);
 $("view").querySelectorAll("[data-delete-alert]").forEach(b=>b.onclick=()=>{
 state.localAlerts.splice(Number(b.dataset.deleteAlert),1);persist();renderAlerts();
 });
}
function renderSettings(){
 setContent(screenHeader("SETTINGS · LOCAL UI","설정","기능 원장에 있는 설정 화면을 웹 환경에 맞게 검수합니다.")+
 '<div class="surface"><div class="choice-row"><div><strong>표시 테마</strong><p>밝게 / 어둡게 전환</p></div><select class="field" style="width:135px" id="themeSelect"><option value="light">라이트</option><option value="dark">다크</option></select></div>'+
 '<div class="choice-row"><div><strong>언어</strong><p>한국어. 원본의 전체 언어 목록은 추가 검증 필요</p></div><span class="pill">한국어</span></div>'+
 '<div class="choice-row"><div><strong>데이터 자동 수집</strong><p>앱을 열 때 백그라운드 수집 없음</p></div><span class="pill green">비활성</span></div>'+
 '<div class="choice-row"><div><strong>거래소·계정 데이터</strong><p>로그인 연결 전 상태</p></div><span class="pill warn">미연결</span></div></div>');
 $("themeSelect").value=state.theme;
 $("themeSelect").onchange=()=>{state.theme=$("themeSelect").value;document.documentElement.dataset.theme=state.theme;persist();renderSettings();};
}
function renderMenu(){
 const items=[
 ["alerts","알림","가격 조건 · 관리 초안","♧"],["news","뉴스","뉴스 피드 · 종목 뉴스","▣"],
 ["calendar","경제 캘린더","이벤트 · 국가 · 중요도","▦"],["indicators","지표·분석","지표와 템플릿","∑"],
 ["drawings","그리기 도구","선 · 객체 트리 · 잠금","✎"],["replay","바 리플레이","시간 이동 · 가상 포지션","▶"],
 ["community","커뮤니티","마인드 · 작성자","☷"],["brokers","브로커·거래","브로커 연결 · 주문 패널","⇄"],
 ["profile","계정·프로필","로그인 · 팔로워 · 개인정보","◉"],["settings","설정","언어 · 테마 · 알림","⚙"],
 ["billing","구독·과금","플랜 · 이용 한도","▤"],["widgets","Android 위젯","PWA 지원 범위 검토","▦"],
 ["sharing","공유·미디어","차트·링크 공유","↗"],["system","통신·시스템","딥링크 · 온보딩","⌘"],
 ["features","전체 339개 기능 원장","원본 근거·구현 상태","☑"],
 ];
 setContent(screenHeader("MORE · FULL ANDROID APP","전체 메뉴","마켓 외의 원본 APK 전체 기능 영역을 보존합니다.")+
 '<div class="list-stack">'+items.map(x=>
 '<button class="list-row" style="text-align:left;color:inherit;cursor:pointer" data-page="'+x[0]+'"><span class="row-icon">'+x[3]+'</span>'+
 '<div class="grow"><h3>'+x[1]+'</h3><p>'+x[2]+'</p></div><span>›</span></button>').join("")+'</div>');
 wirePageLinks();
}
function renderFeatures(){
 const groups=state.sourceCatalog?.function_groups||[];
 setContent(screenHeader("ANDROID APK · AUDIT REGISTER","전체 기능 검수","원본 339개 후보의 개별 기능명을 그대로 보존합니다.")+
 '<div class="audit-header"><div class="screen-kicker" style="color:#b8d1ff">REFERENCE APK · STATIC INVENTORY</div>'+
 '<h2>전체 기능 검수 원장</h2><p>사용자가 제공한 원본 CSV의 기능명 339개입니다. 기능 구현과 실제 Android 앱 동등성 검증을 혼동하지 않습니다.</p>'+
 '<div class="audit-counter"><div><strong>339</strong><small>원본 기능 후보</small></div>'+
 '<div><strong>26</strong><small>전체 기능 영역</small></div>'+
 '<div><strong>0</strong><small>Android 실기기 동등성 통과</small></div></div></div>'+
 disclosure("개별 항목 339개를 축소·삭제하지 않았습니다. 이번 웹 앱에서 메뉴를 열 수 있어도 기능이 완성됐다는 의미가 아닙니다.")+
 '<div class="audit-groups">'+groups.map(g=>
 '<button class="audit-group" data-audit-group="'+esc(g.name)+'"><strong>'+esc(g.name)+'</strong>'+
 '<small>TV-'+String(g.start).padStart(3,"0")+" ~ TV-"+String(g.end).padStart(3,"0")+
 ' · '+g.count+'개 · 원본 APK 정적 확인</small></button>').join("")+'</div>'+
 '<div class="section-title">339개 개별 기능</div><div class="input-wrap"><input class="field" id="auditSearch" placeholder="기능 ID · 기능명 검색" aria-label="원본 기능 검색"></div>'+
 '<div class="surface box-pad" id="auditDetail">'+empty("기능 원장을 읽는 중","기능명을 복원하고 있습니다.","⌛")+'</div>');
 const host=$("auditDetail");let featureList=[];
 let activeGroup="",currentPage=1;
 const show=()=>{
  if(state.page!=="features")return;
  const query=$("auditSearch")?.value.toLowerCase().trim()||"";
  const selected=featureList.filter(x=>(!activeGroup||x.group===activeGroup)&&
   (!query||(x.id+" "+x.name+" "+x.group).toLowerCase().includes(query)));
  const max=Math.max(1,Math.ceil(selected.length/10));
  currentPage=Math.min(currentPage,max);
  const pageItems=selected.slice((currentPage-1)*10,currentPage*10);
  const from=Math.max(1,Math.min(currentPage-2,Math.max(1,max-4)));
  const to=Math.min(max,from+4);
  const pages=[];
  if(from>1)pages.push(1);
  for(let i=from;i<=to;i++)if(!pages.includes(i))pages.push(i);
  if(to<max)pages.push(max);
  host.innerHTML='<div class="split-actions"><strong style="font-size:13px">'+
   esc(activeGroup||"전체")+" · 총 "+selected.length+"개 · 10개씩 표시</strong>"+
   '<span class="pill warn">전 항목 동등성 미검증</span></div>'+
   (pageItems.length?pageItems.map(item=>
   '<div class="choice-row"><div><strong>'+esc(item.id)+' · '+esc(item.name)+'</strong>'+
   '<p>'+esc(item.group)+' · 원본 APK 정적 근거 / 앱 실행 검증 필요</p></div>'+
   '<span class="pill warn">미검증</span></div>').join(""):
   empty("검색 결과 없음","기능 ID 또는 기능명을 확인해 주세요."))+
   '<nav class="world-pager" aria-label="기능 검수 페이지 이동">'+
   '<button class="btn small" data-audit-page="'+(currentPage-1)+'"'+
   (currentPage===1?' disabled':'')+'>이전</button>'+
   pages.map(n=>'<button class="btn small world-page-btn'+(n===currentPage?' active':'')+
   '" data-audit-page="'+n+'"'+(n===currentPage?' aria-current="page"':'')+'>'+n+'</button>').join("")+
   '<button class="btn small" data-audit-page="'+(currentPage+1)+'"'+
   (currentPage===max?' disabled':'')+'>다음</button>'+
   '<form id="auditJump" class="world-jump-form"><label>페이지 이동 '+
   '<input type="number" name="page" min="1" max="'+max+'" class="field world-page-number" value="'+
   currentPage+'" aria-label="검수 기능 이동 페이지"></label>'+
   '<button class="btn small" type="submit">이동</button></form>'+
   '<span class="world-page-status">'+currentPage+'/'+max+'페이지</span></nav>';
  host.querySelectorAll("[data-audit-page]").forEach(b=>b.onclick=()=>{
   const n=Number(b.dataset.auditPage);
   if(n>=1&&n<=max){currentPage=n;show();}
  });
  $("auditJump").onsubmit=e=>{
   e.preventDefault();
   const n=Number($("auditJump").querySelector('input[name="page"]').value);
   if(Number.isSafeInteger(n)&&n>=1&&n<=max){currentPage=n;show();}
  };
 };
 $("view").querySelectorAll("[data-audit-group]").forEach(b=>b.onclick=()=>{
  activeGroup=b.dataset.auditGroup;currentPage=1;show();
  host.scrollIntoView({behavior:"smooth",block:"start"});
 });
 $("auditSearch").oninput=()=>{currentPage=1;show();};
 if(typeof window.loadFeatureRegistry!=="function"){
  host.innerHTML=empty("원본 기능 목록 로드 실패","기능 레지스트리 스크립트가 없습니다.");
  return;
 }
 window.loadFeatureRegistry().then(rows=>{
  if(state.page!=="features")return;
  featureList=rows;
  if(rows.length!==339)throw new Error("원본 기능 수 불일치");
  show();
 }).catch(err=>{
  if(state.page==="features")host.innerHTML=
   empty("기능 명세 로드 실패",err.message||"압축된 원장 읽기 실패");
 });
}
const groupPageMapping={
 "공통/탐색":"menu","마켓/탐색":"markets","마켓/종목":"markets","마켓/부가":"markets",
 "마켓/랭킹":"markets","종목 검색":"search","종목 상세":"chart",
 "차트":"chart","지표·분석":"indicators","그리기 도구":"drawings",
 "리플레이":"replay","관심목록":"watchlist","알림":"alerts",
 "뉴스":"news","경제 캘린더":"calendar","아이디어":"ideas",
 "커뮤니티/마인드":"community","커뮤니티/사용자":"community",
 "거래/브로커":"brokers","계정/인증":"profile","계정/프로필":"profile",
 "설정":"settings","구독/과금":"billing","Android 위젯":"widgets",
 "공유·미디어":"sharing","통신/시스템":"system"};
function renderDomain(page){
 const names={news:"뉴스",calendar:"경제 캘린더",brokers:"브로커·거래",
 profile:"계정·프로필",indicators:"지표·분석",drawings:"그리기 도구",
 replay:"바 리플레이",community:"커뮤니티",billing:"구독·과금",
 widgets:"Android 위젯",sharing:"공유·미디어",system:"통신·시스템",symbols:"종목 상세"};
 const name=names[page]||page;
 const groups=(state.sourceCatalog?.function_groups||[]).filter(g=>groupPageMapping[g.name]===page);
 const notes={
 news:"뉴스 원본 피드/상세 API 연결 및 지역별 필터는 미검증 상태입니다.",
 calendar:"일자·국가·중요도별 경제 캘린더 API와 실측 동작이 아직 연결되지 않았습니다.",
 brokers:"실제 브로커 연결 및 주문 실행은 제공하지 않습니다. 실거래 기능 완료로 표시하지 않습니다.",
 profile:"실제 TradingView 계정·2FA·프로필 데이터를 가져오지 않았습니다.",
 indicators:"차트 위젯에서 제공되는 기본 지표 외 앱 고유 지표·템플릿 상태는 미연결입니다.",
 drawings:"차트 위젯의 도구와 Android 전용 도구 패널은 서로 다르므로 동등성 검증 필요.",
 replay:"원본 앱의 재생·스텝 이동·가상매매 기능은 구현 전입니다.",
 community:"커뮤니티 게시물 작성·수정·팔로우 등 사용자 계정 연동이 필요합니다.",
 billing:"실제 구독/결제는 수행하지 않습니다.",
 widgets:"Android 위젯은 웹/PWA에서 대체 가능한 기능을 별도로 검토해야 합니다.",
 sharing:"현재 차트 원본 링크 공유만 연결되어 있습니다.",
 system:"네이티브 딥링크 및 푸시 전송 등 모바일 웹/PWA 지원 범위 확인이 필요합니다.",
 symbols:"선택한 심볼의 실제 차트는 차트 탭에서 조회 가능합니다.",
 };
 setContent(screenHeader("APP FEATURE DOMAIN · AUDIT",name,"APK 전체 기능 원장에 대응하는 별도 기능 영역입니다.")+
 disclosure("이 영역은 <b>화면 내비게이션이 구현된 상태</b>이며 원본 기능 전체의 실제 동작은 미완료입니다.")+
 '<div class="surface box-pad"><p style="font-size:13px;line-height:1.85;color:var(--secondary)">'+
 esc(notes[page]||"원본 동등성 검증이 필요합니다.")+'</p>'+
 (groups.length?groups.map(g=>'<div class="choice-row"><div><strong>'+esc(g.name)+'</strong><p>'+
 g.count+'개 후보 · TV-'+String(g.start).padStart(3,"0")+'~TV-'+String(g.end).padStart(3,"0")+
 '</p></div><span class="pill warn">미검증</span></div>').join(""):"")+
 '<div class="split-actions" style="margin-top:20px"><button class="btn" data-page="features">전체 검수표</button>'+
 (page==="symbols"||page==="indicators"||page==="drawings"||page==="replay"?
 '<button class="btn primary" data-page="chart">차트 화면</button>':"")+'</div></div>');
 wirePageLinks();
}
function wirePageLinks(){
 $("view").querySelectorAll("[data-page]").forEach(node=>node.onclick=()=>navigate(node.dataset.page));
}
function render(){
 document.body.classList.toggle("tv-markets-mode",
  state.page==="markets"||state.page==="market-detail");
 document.documentElement.dataset.theme=state.theme;
 $("desktopDomains").innerHTML=(state.sourceCatalog?.function_groups||[]).map(g=>
 '<button class="domain-link" data-domain="'+esc(groupPageMapping[g.name]||"features")+
 '">'+esc(g.name)+'</button>').join("");
 $("desktopDomains").querySelectorAll("[data-domain]").forEach(b=>b.onclick=()=>navigate(b.dataset.domain));
 switch(state.page){
  case"markets":renderMarkets();break;
  case"market-sources":renderMarketSources();break;
  case"market-detail":renderMarketDetail();break;
  case"watchlist":renderWatchlist();break;
  case"chart":renderChart();break;case"ideas":renderIdeas();break;
  case"alerts":renderAlerts();break;case"settings":renderSettings();break;
  case"menu":renderMenu();break;case"features":renderFeatures();break;
  default:renderDomain(state.page);
 }
}
function openSearch(){
 $("searchOverlay").hidden=false;$("searchTerm").value="";$("searchResults").innerHTML=
 empty("종목명을 입력해 주세요","현재 시장 조회의 첫 페이지에서 실제 심볼을 검색합니다.","⌕");
 $("searchTerm").focus();
}
function closeSearch(){$("searchOverlay").hidden=true;}
function executeSearch(){
 const q=$("searchTerm").value.trim().toUpperCase();
 if(!q){$("searchResults").innerHTML=empty("종목명을 입력하세요","임의 검색 결과는 만들지 않습니다.","⌕");return;}
 if(q.includes(":")&&/^[A-Z0-9_.!/\-]{1,40}:[A-Z0-9_.!/\-]{1,70}$/.test(q)){
 $("searchResults").innerHTML='<div class="list-row"><div class="grow"><h3>'+esc(q)+'</h3><p>거래소:심볼 직접 지정</p></div>'+
 '<button class="btn primary" id="searchDirectChart">차트 열기</button></div>';
 $("searchDirectChart").onclick=()=>{closeSearch();navigate("chart",{symbol:q})};return;
 }
 const matches=(state.marketRows||[]).filter(r=>
 (rowSymbol(r)+" "+(r.description||r.name||"")).toUpperCase().includes(q));
 $("searchResults").innerHTML=matches.length?
 '<div class="surface">'+makeMarketTable(matches)+'</div>':
 empty("현재 시장 응답에 검색 결과 없음","시장 선택을 바꾸거나 거래소:심볼을 직접 입력하세요.");
 wireMarketRows($("searchResults"));
}
function bindGlobal(){
 $("globalSearchButton").onclick=openSearch;
 $("closeSearch").onclick=closeSearch;
 $("clearSearch").onclick=()=>{$("searchTerm").value="";executeSearch();$("searchTerm").focus()};
 $("searchTerm").addEventListener("input",()=>{
 clearTimeout(state.searchTimer);state.searchTimer=setTimeout(executeSearch,180);
 });
 $("alertsButton").onclick=()=>navigate("alerts");
 $("accountButton").onclick=()=>navigate("profile");
 $("modalOverlay").addEventListener("click",e=>{if(e.target===$("modalOverlay"))closeModal();});
 document.addEventListener("keydown",e=>{if(e.key==="Escape"){closeSearch();closeModal();}});
 window.addEventListener("hashchange",()=>{
  const path=decodeURIComponent(location.hash||"#/markets").replace(/^#\//,"").split("/");
  if(path[0]&&path[0]!==state.page){
   state.page=mainPages[path[0]]?path[0]:"markets";
   if(state.page==="market-detail"){
    state.marketSection=path[1]||"stocks";state.marketWidget=path[2]||null;
   }
   render();
  }
 });
}
async function initialize(){
 bindGlobal();document.documentElement.dataset.theme=state.theme;
 const raw=decodeURIComponent(location.hash||"#/markets").replace(/^#\//,"").split("/");
 state.page=mainPages[raw[0]]?raw[0]:"markets";
 if(raw[0]==="chart"&&raw[1])state.chartSymbol=raw.slice(1).join("/");
 if(raw[0]==="market-detail"){
  state.marketSection=raw[1]||"stocks";
  state.marketWidget=raw[2]||null;
 }
 try{
  state.sourceCatalog=await request("/api/app/catalog");
  const m=state.sourceCatalog.markets?.find(x=>x.id===state.market);
  state.marketGroup=m?.group||"주식";
  $("dataConnection").textContent="기존 TradingView 서비스 · 실데이터 요청 시 조회";
 }catch(err){
  state.sourceCatalog={markets:[],function_groups:[]};
  $("dataConnection").textContent="앱 카탈로그 연결 실패";
  toast("기능 카탈로그를 읽지 못했습니다: "+err.message);
 }
 render();
}
document.addEventListener("DOMContentLoaded",initialize);
