/* Untruncated world market taxonomy UI: asset classes, ISO countries and
   every public TradingView data-coverage row. No automatic source updates. */
"use strict";
(() => {
 const escapeHTML=v=>String(v??"").replace(/[&<>"']/g,c=>({
  "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
 }[c]));
 const rows=v=>Array.isArray(v)?v:[];
 const state={data:null,asset:"stocks",countrySearch:"",feedSearch:"",busy:false,error:"",graph:null,graphOffset:0,graphQuery:"",graphBusy:false};
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
    '연결 대기. 데이터 미연결이라는 이유로 자산군을 삭제하지 않습니다.')+'</div>'+
    '<div class="source-capability">TradingView 원본 Markets 화면 경로: '+
    (rows(active.verified_markets_navigation_paths).length?
      rows(active.verified_markets_navigation_paths)
        .filter(p=>typeof p==='string' && p.startsWith('/markets/'))
        .map(p=>'<a href="https://kr.tradingview.com'+escapeHTML(p)+
          '" target="_blank" rel="noopener">'+escapeHTML(p)+'</a>').join(' · '):
      'Markets 자체 루트 미확인 · 별도 심볼 검색/옵션 체인에서 다루는 상품')+
    '</div>':'')+
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
    '<div class="section-line"><h3 class="section-title">TradingView 실제 시장 하위 메뉴 · 전체 원본 링크 탐색</h3>'+
    '<span class="pill">'+(state.graph?.summary?.discovered_pages||0)+'개 발견 · '+(state.graph?.summary?.pending_pages||0)+'개 미처리</span></div>'+
    '<p class="toolbar-note">원본 /markets/ 하위 링크를 방문 순서로 발견해 누적 보존합니다. 작업량을 줄이기 위해 국가나 하위 카테고리를 삭제하지 않습니다. 사용자 클릭 시에만 다음 페이지들을 탐색합니다.</p>'+
    '<div class="input-wrap"><input class="field" id="worldGraphQuery" placeholder="원본 시장 메뉴 경로·이름 검색" value="'+escapeHTML(state.graphQuery)+'">'+
    '<button class="btn primary" data-world-action="discover"'+(state.graphBusy?' disabled':'')+'>'+(state.graphBusy?'원본 페이지 확인 중':'다음 원본 메뉴 12페이지 분석')+'</button></div>'+
    '<div class="source-capability">실제 접근 완료: '+(state.graph?.summary?.fetched_pages||0)+
    ' · 접근 실패: '+(state.graph?.summary?.failed_pages||0)+
    ' · 원본 링크 연결: '+(state.graph?.summary?.source_edges||0)+
    ' · 발견 완료 여부: '+(state.graph?.summary?.public_link_graph_exhausted?'현재 대기 페이지 없음':'아직 하위 페이지 남음')+
    ' · 전체 시장·거래소 확정: 미검증</div>'+
    '<div class="world-feed-list" id="worldGraphList">'+
    (state.graph?rows(state.graph.items).map(x=>
      '<div class="world-graph-node"><a href="https://kr.tradingview.com'+escapeHTML(x.path)+
      '" target="_blank" rel="noopener">'+escapeHTML(x.label||x.path)+'</a>'+
      '<span class="pill '+(x.status==='fetched'?'green':x.status==='failed'?'red':'warn')+'">'+escapeHTML(x.status)+'</span>'+
      '<small>'+escapeHTML(x.path)+'</small></div>').join(""):
      '<p class="notice-block">원본 메뉴 탐색 데이터가 로드되지 않았습니다.</p>')+'</div>'+
    '<div class="split-actions" style="margin:8px 0 20px"><button class="btn small" data-world-action="graph-prev"'+
    (state.graphOffset<=0?' disabled':'')+'>이전 메뉴 페이지</button>'+
    '<span class="pill">'+(state.graphOffset+1)+' ~ '+(state.graphOffset+rows(state.graph?.items).length)+
    ' / '+(state.graph?.total_count||0)+'</span>'+
    '<button class="btn small" data-world-action="graph-next"'+
    (!(state.graph?.has_more)?' disabled':'')+'>다음 메뉴 페이지</button>'+
    '<button class="btn small" data-world-action="graph-retry">실패 페이지 재등록</button></div>'+
    '<div class="section-line"><h3 class="section-title">전체 거래소·데이터 공급원 원본 행</h3>'+
    '<span class="pill">'+feedRows.length+'/'+(data.source_row_count||0)+'개</span></div>'+
    '<div class="source-capability"><a href="https://www.tradingview.com/data-coverage/" target="_blank" rel="noopener">'+
    'TradingView 공개 Data Coverage</a> · 수동 조회 시각: '+escapeHTML(data.source_snapshot_at||'미조회')+
    ' · 이번 원본 표시 행: '+Number(data.source_latest_visible_rows||0)+
    ' · 전체 보기 클릭: '+(data.source_ui_expansion?.show_all_clicked?'수행':'확인 안 됨')+
    ' · 이전 자료 보존 행: '+Number(data.historical_rows_preserved||0)+
    ' · 거래소 완전성: 미검증</div>'+
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
 async function loadGraph(root){
  try{
    const url='/api/taxonomy/pages?limit=200&offset='+state.graphOffset+'&q='+encodeURIComponent(state.graphQuery);
    const response=await fetch(url,{cache:'no-store'});
    if(!response.ok)throw Error('GRAPH_HTTP_'+response.status);
    state.graph=await response.json();
  }catch(error){state.graph=null;state.error=String(error.message||error);}
  if(root.isConnected)html(root);
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
   }else if(button.dataset.worldAction==='discover'){
    if(state.graphBusy)return;
    state.graphBusy=true;html(root);
    try{
      const response=await fetch('/api/taxonomy/pages/refresh?pages=12',{method:'POST'});
      const result=await response.json();
      if(!response.ok)throw Error(typeof result.detail==='string'?result.detail:
          result.detail?.code||'MARKET_NAV_REFRESH_FAILED');
      state.graphOffset=0;
      await loadGraph(root);
    }catch(error){alert('원본 메뉴 확인 실패: '+String(error.message||error));}
    finally{state.graphBusy=false;if(root.isConnected)html(root);}
   }else if(button.dataset.worldAction==='graph-retry'){
    await fetch('/api/taxonomy/pages/retry-failed',{method:'POST'});
    await loadGraph(root);
   }else if(button.dataset.worldAction==='graph-next'){
    state.graphOffset+=200;
    await loadGraph(root);
   }else if(button.dataset.worldAction==='graph-prev'){
    state.graphOffset=Math.max(0,state.graphOffset-200);
    await loadGraph(root);
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
   else if(id==='worldGraphQuery'){
     state.graphQuery=event.target.value;state.graphOffset=0;
     clearTimeout(state.graphTimer);
     state.graphTimer=setTimeout(()=>loadGraph(root),350);
     return;
   }else return;
   const selection=event.target.selectionStart;
   html(root);
   const node=root.querySelector('#'+id);
   if(node){node.focus();node.setSelectionRange(selection,selection);}
  });
  await load(root);
  await loadGraph(root);
 };
})();
