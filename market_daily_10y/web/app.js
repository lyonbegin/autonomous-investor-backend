/* Markets: live catalog + actual disk-based 10Y daily OHLC. No demo prices. */
"use strict";
const CATEGORIES=[
{id:"index",name:"지수",icon:"▥",description:"한국 · 세계 주요 지수"},
{id:"equity",name:"주식",icon:"▤",description:"국가 · 거래소별 주식"},
{id:"etf",name:"ETF",icon:"◈",description:"상장지수펀드"},
{id:"crypto",name:"암호화폐",icon:"⬡",description:"현물 · 파생상품"},
{id:"futures",name:"선물·원자재",icon:"≋",description:"지수 · 원유 · 금속 · 농산물"},
{id:"fx",name:"외환",icon:"⇄",description:"국가별 통화쌍"},
{id:"bonds",name:"채권",icon:"▱",description:"국채 · 채권형 ETF"},
{id:"economy",name:"경제",icon:"▦",description:"금리 · 물가 · 경제 지표"},
];
const el=id=>document.getElementById(id);
const number=n=>Number(n||0).toLocaleString("ko-KR");
const escapeHtml=s=>String(s??"—").replace(/[&<>"']/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
let state={category:"equity",page:1,perPage:40,summary:null,rows:[],total:0,
selected:null,bars:[],years:10,job:null,authToken:"",pending:null};
let searchTimer=null,jobTimer=null,toastTimer=null;
const authHeaders=()=>({"Authorization":"Bearer "+state.authToken});
const endpoint=(path,query={})=>{
  const url=new URL(path,window.location.origin);
  for(const [k,v] of Object.entries(query))if(v!==null&&v!==undefined&&v!=="")url.searchParams.set(k,v);
  return url.pathname+url.search;
};
async function getJSON(path, options={}){
 const res=await fetch(path,{cache:"no-store",...options});
 let body;
 try{body=await res.json();}catch{body={detail:"서버 응답을 확인할 수 없습니다."};}
 if(!res.ok){
   const err=new Error(typeof body.detail==="string"?body.detail:"요청을 처리하지 못했습니다.");
   err.status=res.status;throw err;
 }
 return body;
}
function toast(message){
 const target=el("toast"); target.textContent=message;target.classList.add("show");
 clearTimeout(toastTimer);toastTimer=setTimeout(()=>target.classList.remove("show"),3600);
}
function requireKey(action){
 if(state.authToken){action();return;}
 state.pending=action;el("keyModal").hidden=false;el("keyInput").focus();
}
function handleUnauthorized(err,retry){
 if(err.status===401||err.status===403){
  state.authToken="";state.pending=retry;el("keyModal").hidden=false;
  el("keyError").hidden=false;
  el("keyInput").focus();
  return;
 }
 toast(err.message);
}
function setActiveCategory(cat){
 if(!CATEGORIES.some(x=>x.id===cat))cat="equity";
 state.category=cat;state.page=1;
 el("search").value="";el("exchangeSelect").value="";el("statusSelect").value="";
 const meta=CATEGORIES.find(x=>x.id===cat);
 el("currentCategory").textContent=meta.name;
 el("currentCategoryCaption").textContent=cat.toUpperCase()+" · MARKET DATA";
 el("categoryDescription").textContent=meta.description+" · 실제 저장 파일만 10년 확보로 표시";
 document.querySelectorAll("[data-category]").forEach(node=>{
  node.classList.toggle("active",node.dataset.category===cat);
  node.setAttribute("aria-current",node.dataset.category===cat?"page":"false");
 });
 loadRows();
}
function makeCategoryNav(){
 el("sideCategories").innerHTML=CATEGORIES.map(c=>{
  const count=state.summary?.groups?.[c.id]?.listed||0;
  return '<button class="side-link '+(c.id===state.category?"active":"")+
    '" data-category="'+c.id+'"><span class="nav-icon">'+c.icon+'</span>'+
    escapeHtml(c.name)+'<span class="nav-count">'+number(count)+'</span></button>';
 }).join("");
 el("categoryTiles").innerHTML=CATEGORIES.map(c=>{
  const group=state.summary?.groups?.[c.id]||{};
  return '<button class="category-tile '+(c.id===state.category?"active":"")+
   '" data-category="'+c.id+'"><span class="tile-icon">'+c.icon+'</span><h3>'+
   escapeHtml(c.name)+'</h3><p>'+escapeHtml(c.description)+'</p>'+
   '<span class="tile-count">'+number(group.listed)+'개 등록 · '+number(group.eligible)+'개 품질 통과</span></button>';
 }).join("");
 document.querySelectorAll("[data-category]").forEach(node=>node.addEventListener("click",()=>{
   setActiveCategory(node.dataset.category);
   document.querySelector(".market-table-section").scrollIntoView({behavior:"smooth"});
 }));
}
async function loadSummary(){
 try{
  const data=await getJSON("/api/markets/summary");
  state.summary=data;
  el("asof").textContent=data.asof_exclusive+" 이전";
  el("statListed").textContent=number(data.totals.listed);
  el("statStored").textContent=number(data.totals.stored_files);
  el("statEligible").textContent=number(data.totals.eligible_10y_any_snapshot);
  el("statMissing").textContent=number(data.totals.missing);
  el("updateSchedule").textContent=data.cron_enabled?"자동 스케줄 설정":"Cron 없음 · 수동 전용";
  makeCategoryNav();
 }catch(err){toast("실제 저장 현황 조회 실패: "+err.message);}
}
function statusClass(s){
 if(s==="10년 확보")return"good";
 if(s==="갱신 필요")return"stale";
 if(s==="미확보")return"missing";
 return"bad";
}
async function loadRows(){
 const body=el("rows");
 body.innerHTML='<tr><td colspan="7" class="empty">목록을 읽는 중입니다…</td></tr>';
 try{
  const data=await getJSON(endpoint("/api/markets/instruments",{
    category:state.category,q:el("search").value,exchange:el("exchangeSelect").value,
    status:el("statusSelect").value,page:state.page,per_page:state.perPage
  }));
  state.rows=data.items;state.total=data.total;
  const prev=el("exchangeSelect").value;
  el("exchangeSelect").innerHTML='<option value="">모든 거래소</option>'+data.exchanges.map(x=>
    '<option value="'+escapeHtml(x)+'">'+escapeHtml(x)+'</option>').join("");
  el("exchangeSelect").value=prev;
  body.innerHTML=data.items.length?data.items.map(r=>{
   return '<tr><td><span class="ticker">'+escapeHtml(r.symbol)+'</span>'+
    '<span class="ticker-secondary">'+escapeHtml(r.vendor_symbol)+'</span></td>'+
    '<td>'+escapeHtml(r.country)+' <span class="ticker-secondary">'+escapeHtml(r.exchange)+'</span></td>'+
    '<td><span class="status '+statusClass(r.status)+'">'+escapeHtml(r.status)+'</span></td>'+
    '<td class="num">'+(r.rows?number(r.rows):"—")+'</td>'+
    '<td>'+escapeHtml(r.first_date)+'</td><td>'+escapeHtml(r.last_date)+'</td>'+
    '<td><button class="table-button" data-key="'+escapeHtml(r.key)+'">10년 일봉 보기</button></td></tr>';
  }).join(""):'<tr><td colspan="7" class="empty">이 분류에 등록된 종목이 없습니다. 거래소 목록이 아직 연결되지 않았을 수 있습니다.</td></tr>';
  const first=data.total?((state.page-1)*state.perPage+1):0;
  el("paginationLabel").textContent=number(first)+"–"+number(Math.min(data.total,state.page*state.perPage))+" / "+number(data.total)+" 종목";
  el("prevPage").disabled=state.page<=1;
  el("nextPage").disabled=state.page*state.perPage>=data.total;
  body.querySelectorAll("[data-key]").forEach(b=>b.addEventListener("click",()=>{
   const row=state.rows.find(x=>x.key===b.dataset.key);
   if(row)openDetail(row);
  }));
 }catch(err){
  body.innerHTML='<tr><td colspan="7" class="empty">실제 종목 목록 조회 오류: '+escapeHtml(err.message)+'</td></tr>';
 }
}
function createMetric(title,value){return '<div class="metric"><span>'+escapeHtml(title)+'</span><b>'+escapeHtml(value)+'</b></div>';}
function openDetail(row){
 state.selected=row;state.bars=[];state.years=10;
 el("detailPanel").classList.add("open");el("detailPanel").setAttribute("aria-hidden","false");
 el("detailBackdrop").hidden=false;document.body.style.overflow="hidden";
 el("detailTitle").textContent=row.symbol;
 el("detailSub").textContent=row.exchange+" · "+row.vendor_symbol+" · "+row.asset_class;
 el("detailState").textContent=row.status+" · "+(row.reasons||[]).join(", ");
 el("panelMetrics").innerHTML=[
   createMetric("일봉 수",number(row.rows)),createMetric("품질 충족",row.eligible?"예":"아니요"),
   createMetric("첫 거래일",row.first_date||"—"),createMetric("마지막 거래일",row.last_date||"—")
 ].join("");
 el("detailRows").innerHTML="";
 document.querySelectorAll(".period").forEach(p=>p.classList.toggle("active",p.dataset.years==="10"));
 if(row.has_file)requireKey(()=>loadBars(row.key));else showChartEmpty("저장된 실제 일봉이 없습니다. 업데이트 버튼으로 해당 종목을 수집할 수 있습니다.");
}
function showChartEmpty(message){
 el("priceChart").style.visibility="hidden";el("chartEmpty").hidden=false;
 el("chartEmpty").textContent=message;
 el("chartTooltip").textContent="원본 데이터를 만들거나 임의 가격으로 보충하지 않습니다.";
}
function closeDetail(){
 el("detailPanel").classList.remove("open");
 el("detailPanel").setAttribute("aria-hidden","true");
 el("detailBackdrop").hidden=true;document.body.style.overflow="";
 state.selected=null;state.bars=[];
}
async function loadBars(key){
 const attempt=()=>loadBars(key);
 try{
  const data=await getJSON(endpoint("/api/markets/bars",{key}),{headers:authHeaders()});
  if(state.selected?.key!==key)return;
  state.bars=data.bars||[];
  el("detailState").textContent=(data.eligible?"10년 품질 통과":"10년 미충족")+" · "+
   data.rows.toLocaleString("ko-KR")+"개 실제 일봉 · "+data.window_start+" ~ "+data.last_date;
  el("panelMetrics").innerHTML=[
   createMetric("확보 일봉",number(data.rows)),createMetric("품질 통과",data.eligible?"예":"아니요"),
   createMetric("첫 거래일",data.first_date),createMetric("마지막 거래일",data.last_date)
  ].join("");
  if(!state.bars.length){showChartEmpty("저장된 봉이 없습니다.");return;}
  el("chartEmpty").hidden=true;el("priceChart").style.visibility="visible";
  drawChart();
  el("detailRows").innerHTML=state.bars.slice(-15).reverse().map(d=>
    '<tr><td>'+escapeHtml(d.date)+'</td>'+["open","high","low","close","volume"].map(k=>
    '<td>'+formatPrice(d[k])+'</td>').join("")+'</tr>').join("");
 }catch(err){
  if(err.status===403||err.status===401){handleUnauthorized(err,attempt);return;}
  showChartEmpty("저장 데이터 조회 실패: "+err.message);
 }
}
const formatPrice=v=>v==null?"—":Number(v).toLocaleString("ko-KR",{maximumFractionDigits:5});
function visibleBars(){
 const bars=state.bars; if(!bars.length)return[];
 if(state.years===10)return bars;
 const newest=new Date(bars[bars.length-1].date+"T00:00:00Z");
 const since=new Date(newest);
 since.setUTCDate(since.getUTCDate()-Math.round(state.years*365.25));
 return bars.filter(b=>new Date(b.date+"T00:00:00Z")>=since);
}
function chartPoint(evt,points,rect,padding,xScale){
 const pos=(evt.clientX-rect.left)*((el("priceChart").width)/(rect.width));
 const index=Math.max(0,Math.min(points.length-1,Math.round((pos-padding)/xScale)));
 const bar=points[index];
 if(!bar)return;
 el("chartTooltip").textContent=bar.date+" · 시가 "+formatPrice(bar.open)+" · 고가 "+
  formatPrice(bar.high)+" · 저가 "+formatPrice(bar.low)+" · 종가 "+formatPrice(bar.close)+
  " · 거래량 "+formatPrice(bar.volume);
}
function drawChart(){
 const canvas=el("priceChart"),bars=visibleBars();
 if(!bars.length){showChartEmpty("선택한 범위에 실제 일봉이 없습니다.");return;}
 const rect=canvas.getBoundingClientRect();
 const dpr=window.devicePixelRatio||1,width=Math.max(300,Math.floor(rect.width*dpr)),
       height=Math.max(200,Math.floor(rect.height*dpr));
 canvas.width=width;canvas.height=height;
 const g=canvas.getContext("2d");g.clearRect(0,0,width,height);
 const left=58*dpr,right=18*dpr,top=26*dpr,bottom=35*dpr;
 const w=width-left-right,h=height-top-bottom;
 const clean=bars.filter(b=>typeof b.close==="number"&&Number.isFinite(b.close));
 if(clean.length<2){showChartEmpty("표시 가능한 일봉이 부족합니다.");return;}
 const prices=clean.map(b=>b.close);
 let min=Math.min(...prices),max=Math.max(...prices),range=max-min||1;
 min-=range*.07;max+=range*.07;range=max-min;
 const xStep=w/Math.max(1,clean.length-1);
 g.strokeStyle="#e8edf4";g.lineWidth=dpr;g.font=(10*dpr)+"px Arial";
 g.fillStyle="#8190a2";
 for(let i=0;i<=4;i++){
  const y=top+h*i/4;
  g.beginPath();g.moveTo(left,y);g.lineTo(width-right,y);g.stroke();
  g.fillText(formatPrice(max-range*i/4),8*dpr,y+3*dpr);
 }
 for(let i=0;i<=5;i++){
  const at=Math.round((clean.length-1)*i/5);
  const x=left+xStep*at;
  g.fillText(clean[at].date.slice(0,7),Math.max(left,x-22*dpr),height-13*dpr);
 }
 g.beginPath();clean.forEach((bar,i)=>{
   const x=left+i*xStep,y=top+(max-bar.close)/range*h;
   if(i===0)g.moveTo(x,y);else g.lineTo(x,y);
 });
 g.strokeStyle="#2563eb";g.lineWidth=1.5*dpr;g.lineJoin="round";g.stroke();
 const last=clean[clean.length-1].close;
 g.fillStyle="#245fe0";g.beginPath();
 g.arc(left+(clean.length-1)*xStep,top+(max-last)/range*h,3.5*dpr,0,Math.PI*2);g.fill();
 canvas.onmousemove=evt=>chartPoint(evt,clean,canvas.getBoundingClientRect(),left,xStep);
}
async function updateRequest(scope){
 const retry=()=>updateRequest(scope);
 const maxValue=el("batchSize").value;
 let payload={scope,max_items:maxValue==="all"?null:Number(maxValue)};
 if(scope==="category")payload.category=state.category;
 if(scope==="instrument"){payload.key=state.selected?.key;payload.max_items=1;}
 if(!payload.key&&scope==="instrument")return;
 try{
  const data=await getJSON("/api/markets/update",{method:"POST",
   headers:{"Content-Type":"application/json",...authHeaders()},body:JSON.stringify(payload)});
  state.job=data;displayJob(data);
  toast("사용자 요청에 따른 수동 수집을 시작했습니다.");
  if(jobTimer)clearInterval(jobTimer);
  jobTimer=setInterval(refreshJob,2500);
 }catch(err){handleUnauthorized(err,retry);}
}
function displayJob(job){
 if(!job||job.state==="idle")return;
 el("jobBox").hidden=false;
 const translations={running:"실행 중",completed:"완료",completed_with_errors:"일부 실패",interrupted:"중단됨",stopped_disk_low:"저장공간 부족"};
 el("jobState").textContent=translations[job.state]||job.state;
 const total=Math.max(1,job.total||0);
 el("jobProgress").style.width=(Math.min(100,(job.attempted||0)/total*100))+"%";
 el("jobMeta").textContent="요청 "+number(job.total)+"개 · 처리 "+number(job.attempted)+
  "개 · 성공 "+number(job.completed)+"개 · 실패 "+number(job.failed)+"개"+
  (job.catalog_count?" · 등록 목록 "+number(job.catalog_count)+"개":"")+
  (job.catalog_error?" · 목록 오류: "+job.catalog_error:"")+
  (job.current?" · 최근 "+job.current:"")+(job.last_error?" · 오류: "+job.last_error:"");
}
async function refreshJob(){
 try{
  const data=await getJSON("/api/markets/update-status");
  if(data.state==="idle")return;
  const previous=state.job?.state;
  state.job=data;displayJob(data);
  if(data.state!=="running"){
   if(jobTimer){clearInterval(jobTimer);jobTimer=null;}
   if(previous==="running")toast("수동 수집이 종료되었습니다. 수집 결과를 확인해 주세요.");
   await loadSummary();await loadRows();
   if(state.selected)openDetail(state.selected);
  }
 }catch(err){console.warn("Job status",err);}
}
function init(){
 el("keyForm").addEventListener("submit",e=>{
  e.preventDefault();const token=el("keyInput").value.trim();
  if(!token){el("keyError").hidden=false;return;}
  state.authToken=token;el("keyInput").value="";
  el("keyError").hidden=true;el("keyModal").hidden=true;
  const cb=state.pending;state.pending=null;
  if(cb)cb();else toast("관리 키가 현재 화면에 적용됐습니다.");
 });
 el("keyCancel").addEventListener("click",()=>{el("keyModal").hidden=true;state.pending=null;});
 el("authButton").addEventListener("click",()=>{state.authToken="";requireKey(()=>toast("관리 키가 적용됐습니다."));});
 el("refreshCatalogButton").addEventListener("click",()=>requireKey(()=>updateRequest("catalog")));
 el("updateAllButton").addEventListener("click",()=>requireKey(()=>updateRequest("all")));
 el("updateCategoryButton").addEventListener("click",()=>requireKey(()=>updateRequest("category")));
 el("updateOneButton").addEventListener("click",()=>requireKey(()=>updateRequest("instrument")));
 el("closePanel").addEventListener("click",closeDetail);
 el("detailBackdrop").addEventListener("click",closeDetail);
 document.addEventListener("keydown",e=>{if(e.key==="Escape")closeDetail();});
 el("search").addEventListener("input",()=>{clearTimeout(searchTimer);
  searchTimer=setTimeout(()=>{state.page=1;loadRows();},220);});
 ["exchangeSelect","statusSelect"].forEach(id=>el(id).addEventListener("change",()=>{state.page=1;loadRows();}));
 el("prevPage").addEventListener("click",()=>{state.page=Math.max(1,state.page-1);loadRows();});
 el("nextPage").addEventListener("click",()=>{state.page++;loadRows();});
 document.querySelectorAll(".period").forEach(b=>b.addEventListener("click",()=>{
   state.years=Number(b.dataset.years);
   document.querySelectorAll(".period").forEach(x=>x.classList.toggle("active",x===b));
   if(state.bars.length)drawChart();
 }));
 window.addEventListener("resize",()=>{if(state.bars.length)drawChart();});
 loadSummary().then(loadRows);refreshJob();
}
document.addEventListener("DOMContentLoaded",init);