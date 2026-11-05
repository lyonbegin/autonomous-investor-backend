/* Untruncated world market taxonomy UI: asset classes, ISO countries and
   every public TradingView data-coverage row. No automatic source updates. */
"use strict";
(() => {
 const escapeHTML=v=>String(v??"").replace(/[&<>"']/g,c=>({
  "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
 }[c]));
 const rows=v=>Array.isArray(v)?v:[];
 const state={data:null,asset:"stocks",countrySearch:"",feedSearch:"",busy:false,error:""};
 function html(target){
  const data=state.data;
  if(!data){
   target.innerHTML='<div class="notice-block">전체 세계 시장 목록을 조회할 수 없습니다. '+
      escapeHTML(state.error||"")+' <button class="btn" data-world-action="retry">다시 시도</button></div>';
   return;
  }
  const classes=rows(data.categories),active=classes.find(x=>x.id===state.asset)||classes[0];
  const cs=state.countrySearch.trim().toLowerCase();
  const fs=state.feedSearch.trim().toLowerCase();
  const countryRows=rows(data.countries).filter(x=>
    !cs||(x.name+" "+x.iso2+" "+x.iso3).toLowerCase().includes(cs));
  const feedRows=rows(data.tradingview_source_records).filter(x=>
    !fs||(x.display+" "+rows(x.all_cells).join(" ")).toLowerCase().includes(fs));
  target.innerHTML=
    '<div class="section-line"><h2 class="section-title">전세계 전체 시장·자산 카테고리</h2>'+
    '<span class="pill">'+classes.length+'개 자산 유형</span></div>'+
    '<p class="toolbar-note">기존 14개 시장 스캐너는 연결된 일부 데이터 엔진일 뿐입니다. 아래 분류는 원본의 전체 심볼 유형과 국가·공급원 목록을 별도로 표시합니다.</p>'+
    '<div id="worldAssetTabs" class="world-asset-tabs">'+classes.map(x=>
     '<button class="world-asset'+(x.id===active?.id?' active':'')+
     '" data-world-asset="'+escapeHTML(x.id)+'"><strong>'+escapeHTML(x.name)+
     '</strong><small>'+escapeHTML(x.source_symbol_type)+'</small>'+
     '<span class="pill '+(rows(x.scanner_routes).length?'green':'warn')+'">'+
     (rows(x.scanner_routes).length?'연결됨':'미연결')+'</span></button>').join("")+'</div>'+
    (active?'<h3 class="mini-title">'+escapeHTML(active.name)+' 전체 하위 상품</h3>'+
    '<div class="world-tags">'+rows(active.subcategories).map(s=>
    '<span class="world-tag">'+escapeHTML(s)+'</span>').join("")+'</div>'+
    '<div class="source-capability">기존 연결 스캐너: '+(rows(active.scanner_routes).length?
    rows(active.scanner_routes).map(escapeHTML).join(" · "):
    '연결 대기. 데이터 미연결이라는 이유로 자산군을 삭제하지 않습니다.')+'</div>':'')+
    '<h3 class="mini-title">여러 자산군에 걸치는 추가 카테고리</h3>'+
    rows(data.additional_cross_asset_facets).map(f=>
    '<details class="world-facet"><summary>'+escapeHTML(f.name)+'</summary><div class="world-tags">'+
    rows(f.subcategories).map(s=>'<span class="world-tag">'+escapeHTML(s)+'</span>').join("")+
    '</div></details>').join("")+
    '<div class="section-line"><h3 class="section-title">전 세계 전체 국가 · ISO 원장</h3>'+
    '<span class="pill">'+countryRows.length+'/'+rows(data.countries).length+'개</span></div>'+
    '<input id="worldCountrySearch" class="field" placeholder="국가명·ISO 코드 필터" value="'+escapeHTML(state.countrySearch)+'">'+
    '<p class="toolbar-note">전체 ISO 국가 목록이며 해당 국가에 TradingView 거래소가 있다는 뜻이 아닙니다. 미확인 국가도 전부 보존됩니다.</p>'+
    '<div id="worldCountryList" class="world-country-list">'+countryRows.map(c=>
    '<button class="world-country" data-world-country="'+escapeHTML(c.name)+'">'+
    '<b>'+escapeHTML(c.iso2)+'</b><span>'+escapeHTML(c.name)+'</span>'+
    '<small>지원 미확인</small></button>').join("")+'</div>'+
    '<div class="section-line"><h3 class="section-title">전체 거래소·데이터 공급원 원본 행</h3>'+
    '<span class="pill">'+feedRows.length+'/'+(data.source_row_count||0)+'개</span></div>'+
    '<div class="source-capability"><a href="https://www.tradingview.com/data-coverage/" target="_blank" rel="noopener">'+
    'TradingView 공개 Data Coverage</a> · 수동 조회 시각: '+escapeHTML(data.source_snapshot_at||'미조회')+
    ' · 데이터 완전성: 미검증</div>'+
    '<div class="input-wrap"><input id="worldFeedSearch" class="field" placeholder="거래소·공급원·국가명 검색" value="'+escapeHTML(state.feedSearch)+'">'+
    '<button class="btn primary" data-world-action="refresh"'+(state.busy?' disabled':'')+'>'+
    (state.busy?'확인 중':'원본 공급원 목록 수동 갱신')+'</button></div>'+
    '<div class="world-feed-list" id="worldFeedList">'+(feedRows.length?feedRows.map(f=>
    '<details class="world-feed"><summary><b>#'+escapeHTML(f.source_row)+'</b> '+escapeHTML(f.display)+'</summary>'+
    '<div class="world-feed-detail">'+rows(f.all_cells).map((s,i)=>
    '<p><b>원본 필드 '+(i+1)+'</b> '+escapeHTML(s)+'</p>').join("")+
    '<small>추정 자산 유형: '+rows(f.asset_type_candidate_ids).map(escapeHTML).join(', ')+
    ' · 정확한 지원 범위/5년 일봉 보유: 미검증</small></div></details>').join(""):
    '<p class="notice-block">'+(data.source_row_count===0?
      '수동 갱신을 누르면 거래소·공급원 원본 목록을 가져옵니다. 현재 실제 수집 기록 없음.':
      '검색 결과 없음. 필터를 해제하면 보존된 모든 행을 확인할 수 있습니다.')+'</p>')+'</div>'+
    '<p class="toolbar-note">원본 표의 행을 잘라내지 않습니다. 메뉴 원장, 실제 수집 종목 목록, 5년 일봉 저장 상태는 각각 독립적으로 검증합니다.</p>';
 }
 async function load(el){
  try{
   const r=await fetch('/api/taxonomy',{cache:'no-store'});
   if(!r.ok)throw Error('HTTP '+r.status);
   state.data=await r.json();
   state.error='';
  }catch(err){state.error=String(err.message||err);}
  if(el.isConnected)html(el);
 }
 window.loadGlobalMarketsPanel=async function(){
  const root=document.getElementById('fullGlobalMarketCatalog');
  if(!root)return;
  root.addEventListener('click',async event=>{
   const button=event.target.closest('[data-world-asset],[data-world-country],[data-world-action]');
   if(!button)return;
   if(button.dataset.worldAsset){
    state.asset=button.dataset.worldAsset;html(root);
   }else if(button.dataset.worldCountry){
    state.feedSearch=button.dataset.worldCountry;html(root);
    root.querySelector('#worldFeedSearch')?.focus();
   }else if(button.dataset.worldAction==='retry'){
    await load(root);
   }else if(button.dataset.worldAction==='refresh'){
    if(state.busy)return;
    state.busy=true;html(root);
    try{
     const r=await fetch('/api/taxonomy/refresh',{method:'POST'});
     const result=await r.json();
     if(!r.ok)throw Error(typeof result.detail==='string'?result.detail:
        result.detail?.code||'SOURCE_REFRESH_FAILED');
     await load(root);
    }catch(err){state.error=String(err.message||err);alert('목록 갱신 실패: '+state.error);}
    finally{state.busy=false;if(root.isConnected)html(root);}
   }
  });
  root.addEventListener('input',event=>{
   const id=event.target.id;
   if(id==='worldCountrySearch')state.countrySearch=event.target.value;
   else if(id==='worldFeedSearch')state.feedSearch=event.target.value;
   else return;
   const selection=event.target.selectionStart;
   html(root);
   const node=root.querySelector('#'+id);
   if(node){node.focus();node.setSelectionRange(selection,selection);}
  });
  await load(root);
 };
})();
