/* Incremental, server-side paginated world markets UI.
 * Never download entire country/provider/navigation inventories into browser.
 * Each table loads exactly 10 records per page with numbered page jump.
 */
"use strict";
(() => {
  const esc = v => String(v ?? "").replace(/[&<>"']/g,c => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[c]));
  const fmt = n => Number(n||0).toLocaleString("ko-KR");
  const listIds = ["countries","sources","pages"];
  const rows = v => Array.isArray(v) ? v : [];
  const pageSize = 10;
  const stores = {};
  let token = 0;
  let data = null;
  let asset = "stocks";
  let busy = false;
  let msg = "";
  let root = null;
  let filterTimer = null;

  const makeState = () => ({page:1,q:"",result:null,loading:false,error:"",generation:0});
  for(const key of listIds)stores[key] = makeState();

  function totalFor(key){
    const r=stores[key].result;
    return key==="sources" ? Number(r?.total_matches||0) : Number(r?.total_count||0);
  }
  function pagination(key){
    const st=stores[key], total=totalFor(key);
    const max=Math.max(1,Math.ceil(total/pageSize)),p=st.page;
    const start=Math.max(1,Math.min(p-2,max-4));
    const end=Math.min(max,start+4);
    const parts=[];
    if(start>1){
      parts.push(pageButton(key,1,p));
      if(start>2)parts.push('<span class="world-ellipsis">…</span>');
    }
    for(let i=start;i<=end;i++)parts.push(pageButton(key,i,p));
    if(end<max){
      if(end<max-1)parts.push('<span class="world-ellipsis">…</span>');
      parts.push(pageButton(key,max,p));
    }
    return '<nav class="world-pager" aria-label="'+key+' 페이지 이동">'+
      '<button type="button" data-world-list="'+key+'" data-world-page="'+(p-1)+
      '" class="btn small"'+(p<=1?' disabled':'')+'>이전</button>'+
      parts.join("")+
      '<button type="button" data-world-list="'+key+'" data-world-page="'+(p+1)+
      '" class="btn small"'+(p>=max?' disabled':'')+'>다음</button>'+
      '<form data-world-jump="'+key+'" class="world-jump-form">'+
      '<label>페이지 직접 이동 <input aria-label="'+key+' 이동 페이지" type="number" min="1" max="'+max+
      '" class="field world-page-number" name="page" value="'+p+'"></label>'+
      '<button class="btn small" type="submit">이동</button></form>'+
      '<span class="world-page-status">'+fmt(p)+' / '+fmt(max)+'페이지 · 전체 '+fmt(total)+'개</span></nav>';
  }
  function pageButton(key,n,current){
    return '<button type="button" class="btn small world-page-btn'+(n===current?' active':'')+
      '" data-world-list="'+key+'" data-world-page="'+n+'" aria-label="'+key+' '+n+'페이지"'+
      (n===current?' aria-current="page"':'')+'>'+n+'</button>';
  }
  function banner(){
    const all=data||{};
    return '<div class="section-line"><h2 class="section-title">전 세계 자산군 및 시장 메뉴</h2>'+
      '<span class="pill">공식 유형 '+rows(all.categories).length+'개</span></div>'+
      '<p class="toolbar-note">이 페이지는 전체 목록을 내려받지 않습니다. 국가·거래소·시장 메뉴는 각각 10개씩 서버에서 조회합니다. 각 목록에서 2·3·4페이지 또는 원하는 번호로 이동하세요.</p>'+
      '<div id="worldAssetTabs" class="world-asset-tabs">'+rows(all.categories).map(x=>
      '<button class="world-asset'+(x.id===asset?' active':'')+
      '" data-world-asset="'+esc(x.id)+'"><strong>'+esc(x.name)+
      '</strong><small>'+esc(x.source_symbol_type)+'</small><span class="pill '+
      (rows(x.scanner_routes).length?'green':'warn')+'">'+
      (rows(x.scanner_routes).length?'연결됨':'미연결')+'</span></button>').join("")+'</div>'+
      '<div id="worldAssetDetail"></div>'+
      '<h3 class="mini-title">자산군 간 공통 분류</h3>'+
      rows(all.additional_cross_asset_facets).map(f=>
      '<details class="world-facet"><summary>'+esc(f.name)+'</summary><div class="world-tags">'+
      rows(f.subcategories).map(x=>'<span class="world-tag">'+esc(x)+'</span>').join("")+
      '</div></details>').join("")+
      '<section class="world-list-section"><div class="section-line"><h3 class="section-title">국가 · ISO 전 세계 목록</h3>'+
      '<span class="pill">'+fmt(all.country_total)+'개</span></div>'+
      '<input class="field" id="worldCountrySearch" placeholder="국가명 또는 ISO 코드" autocomplete="off" value="'+esc(stores.countries.q)+'">'+
      '<p class="toolbar-note">국가 전체는 서버에 보관합니다. TradingView 실시간 지원 여부는 미확인입니다.</p>'+
      '<div id="worldCountriesPanel"></div></section>'+
      '<section class="world-list-section"><div class="section-line"><h3 class="section-title">TradingView 시장 하위 메뉴</h3>'+
      '<span class="pill">원본 링크 · 미탐색 항목 보존</span></div>'+
      '<div class="input-wrap"><input class="field" id="worldGraphQuery" placeholder="시장 메뉴 경로·이름" autocomplete="off" value="'+esc(stores.pages.q)+'">'+
      '<button class="btn primary" data-world-action="discover">원본 메뉴 12개 추가 탐색</button></div>'+
      '<div id="worldPagesPanel"></div></section>'+
      '<section class="world-list-section"><div class="section-line"><h3 class="section-title">거래소·데이터 공급원</h3>'+
      '<span class="pill">'+fmt(all.source_row_count)+'개 보존</span></div>'+
      '<div class="source-capability"><a href="https://www.tradingview.com/data-coverage/" target="_blank" rel="noopener">'+
      'TradingView 원본 공급원 표</a> · 갱신: '+esc(all.source_snapshot_at||'미실행')+
      ' · 모든 거래소 종목 확보 여부: 미검증</div>'+
      '<div class="input-wrap"><input class="field" id="worldFeedSearch" placeholder="거래소·공급원 이름" autocomplete="off" value="'+esc(stores.sources.q)+'">'+
      '<button class="btn primary" data-world-action="refresh">원본 공급원 목록 수동 갱신</button></div>'+
      '<div id="worldSourcesPanel"></div></section>'+
      '<p class="toolbar-note">각 목록은 독립 페이지입니다. 다음 페이지를 누르기 전에는 해당 10개 항목만 내려받으며, 가격·5년 일봉 다운로드는 실행하지 않습니다.</p>';
  }
  function showAsset(){
    const x=rows(data?.categories).find(v=>v.id===asset);
    const out=root?.querySelector("#worldAssetDetail");
    if(!out||!x)return;
    out.innerHTML='<h3 class="mini-title">'+esc(x.name)+' 세부 상품 분류</h3>'+
    '<div class="world-tags">'+rows(x.subcategories).map(v=>
      '<span class="world-tag">'+esc(v)+'</span>').join("")+'</div>'+
    '<div class="source-capability">현재 연결 스캐너: '+
      (rows(x.scanner_routes).length?rows(x.scanner_routes).map(esc).join(' · '):
       '미연결. 메뉴에서 제외하지 않았습니다.')+'</div>';
    root.querySelectorAll("[data-world-asset]").forEach(button=>
      button.classList.toggle("active",button.dataset.worldAsset===asset));
  }
  function renderRows(key){
    const host=root?.querySelector("#world"+(key==="countries"?"Countries":key==="pages"?"Pages":"Sources")+"Panel");
    if(!host)return;
    const st=stores[key],result=st.result;
    if(st.loading && !result){
      host.innerHTML='<p class="notice-block">현재 페이지 10개 조회 중…</p>';
      return;
    }
    if(st.error && !result){
      host.innerHTML='<div class="notice-block">조회 실패: '+esc(st.error)+
        ' <button class="btn small" data-world-retry="'+key+'">재시도</button></div>';
      return;
    }
    const items=rows(result?.items);
    if(key==="countries"){
      host.innerHTML='<div class="world-country-list" id="worldCountryList">'+items.map(c=>
       '<button class="world-country" data-world-country="'+esc(c.name)+'">'+
       '<b>'+esc(c.iso2)+'</b><span>'+esc(c.name)+'</span>'+
       '<small>지원 미확인</small></button>').join("")+
       (items.length?'':'<p class="notice-block">해당 국가 없음</p>')+'</div>'+pagination(key);
    }else if(key==="pages"){
      host.innerHTML='<div class="source-capability">방문 완료 '+fmt(result?.summary?.fetched_pages)+
       ' · 대기 '+fmt(result?.summary?.pending_pages)+
       ' · 실패 '+fmt(result?.summary?.failed_pages)+
       ' · 시장 링크 연결 '+fmt(result?.summary?.source_edges)+'</div>'+
       '<div class="world-feed-list" id="worldGraphList">'+items.map(x=>
       '<div class="world-graph-node"><a href="https://kr.tradingview.com'+esc(x.path)+
       '" target="_blank" rel="noopener">'+esc(x.label||x.path)+'</a>'+
       '<span class="pill '+(x.status==='fetched'?'green':x.status==='failed'?'red':'warn')+'">'+
       esc(x.status)+'</span><small>'+esc(x.path)+'</small></div>').join("")+
       (items.length?'':'<p class="notice-block">원본 메뉴 없음</p>')+'</div>'+pagination(key)+
       '<button class="btn small" data-world-action="retry-graph">실패 페이지 재등록</button>';
    }else{
      host.innerHTML='<div class="source-capability">검색 일치 '+fmt(result?.total_matches)+
        ' · 원본 보존 '+fmt(result?.total_source_rows)+
        ' · 미분류 '+fmt(result?.unclassified_row_count)+
        ' · 전체 분류 지원 검증 미완료</div>'+
        '<div class="world-feed-list" id="worldFeedList">'+items.map(f=>
        '<details class="world-feed"><summary><b>#'+esc(f.source_row)+
        '</b> '+esc(f.display)+'</summary><div class="world-feed-detail">'+
        rows(f.all_cells).map((v,i)=>'<p><b>원본 필드 '+(i+1)+'</b> '+esc(v)+'</p>').join("")+
        '<small>분류 추정: '+rows(f.asset_type_candidate_ids).map(esc).join(", ")+
        ' · 실제 공급/가격 저장 여부 미확인</small></div></details>').join("")+
        (items.length?'':'<p class="notice-block">공급원 목록이 없거나 검색 결과가 없습니다.</p>')+
        '</div>'+pagination(key);
    }
    if(st.loading)host.setAttribute("aria-busy","true");
    else host.removeAttribute("aria-busy");
  }
  async function fetchList(key){
    const st=stores[key], generation=++st.generation;
    st.loading=true;st.error="";
    renderRows(key);
    let url;
    const q=encodeURIComponent(st.q.trim());
    if(key==="countries")url="/api/taxonomy/countries?page="+st.page+"&q="+q;
    if(key==="sources")url="/api/taxonomy/sources?limit=10&page="+st.page+"&q="+q;
    if(key==="pages")url="/api/taxonomy/pages?limit=10&page="+st.page+"&q="+q;
    try{
      const response=await fetch(url,{cache:"no-store",headers:{"Accept":"application/json"}});
      if(!response.ok)throw Error("HTTP "+response.status);
      const result=await response.json();
      if(generation!==st.generation||!root?.isConnected)return;
      if(!Array.isArray(result.items)||result.items.length>pageSize)
        throw Error("서버가 요청한 10개보다 많은 항목을 반환했습니다.");
      st.result=result;
      st.error="";
    }catch(error){
      if(generation!==st.generation)return;
      st.error=String(error.message||error);
      st.result=null;
    }finally{
      if(generation===st.generation){st.loading=false;renderRows(key);}
    }
  }
  function changePage(key,num){
    const st=stores[key],max=Math.max(1,Math.ceil(totalFor(key)/pageSize));
    if(!Number.isSafeInteger(num)||num<1){return;}
    if(num>max){
      alert('이 목록은 '+max+'페이지까지 있습니다.');
      return;
    }
    if(num===st.page)return;
    st.page=num;
    fetchList(key);
  }
  async function refreshOverview(){
    const response=await fetch("/api/taxonomy/overview",{cache:"no-store"});
    if(!response.ok)throw Error("전체 시장 분류 응답 실패 (HTTP "+response.status+")");
    data=await response.json();
    if(rows(data.categories).length!==9)throw Error("9개 자산 분류 응답 누락");
    if(root?.isConnected){root.innerHTML=banner();showAsset();}
  }
  async function manualRefresh(action){
    if(busy)return;
    busy=true;
    try{
      const url=action==="discover"?"/api/taxonomy/pages/refresh?pages=12":
          action==="retry-graph"?"/api/taxonomy/pages/retry-failed":
          "/api/taxonomy/refresh";
      const response=await fetch(url,{method:"POST"});
      const result=await response.json();
      if(!response.ok)throw Error(typeof result.detail==="string"?result.detail:
        result.detail?.code||"HTTP "+response.status);
      if(action==="refresh"){
        await refreshOverview();
        stores.sources.page=1;
        await fetchList("sources");
      }else{
        stores.pages.page=1;
        await fetchList("pages");
      }
    }catch(error){
      alert("수동 갱신 실패: "+String(error.message||error));
    }finally{busy=false;}
  }
  window.loadGlobalMarketsPanel=async function(){
    const current=++token;
    root=document.getElementById("fullGlobalMarketCatalog");
    if(!root)return;
    for(const id of listIds){stores[id]=makeState();}
    data=null;
    root.innerHTML='<p class="notice-block">전 세계 자산 분류를 불러오는 중입니다…</p>';
    root.addEventListener("click",event=>{
      const assetBtn=event.target.closest("[data-world-asset]");
      if(assetBtn){asset=assetBtn.dataset.worldAsset;showAsset();return;}
      const countryBtn=event.target.closest("[data-world-country]");
      if(countryBtn){stores.sources.q=countryBtn.dataset.worldCountry;stores.sources.page=1;
        const field=root.querySelector("#worldFeedSearch");
        if(field)field.value=stores.sources.q;
        fetchList("sources");
        return;
      }
      const pageBtn=event.target.closest("[data-world-list][data-world-page]");
      if(pageBtn){changePage(pageBtn.dataset.worldList,Number(pageBtn.dataset.worldPage));return;}
      const retry=event.target.closest("[data-world-retry]");
      if(retry){fetchList(retry.dataset.worldRetry);return;}
      const manual=event.target.closest("[data-world-action]");
      if(manual)manualRefresh(manual.dataset.worldAction);
    });
    root.addEventListener("submit",event=>{
      const form=event.target.closest("[data-world-jump]");
      if(!form)return;
      event.preventDefault();
      const wanted=Number(form.querySelector('input[name="page"]')?.value);
      changePage(form.dataset.worldJump,wanted);
    });
    root.addEventListener("input",event=>{
      const mapping={worldCountrySearch:"countries",
                     worldGraphQuery:"pages",worldFeedSearch:"sources"};
      const key=mapping[event.target.id];
      if(!key)return;
      const value=event.target.value;
      stores[key].q=value;stores[key].page=1;
      clearTimeout(filterTimer);
      filterTimer=setTimeout(()=>fetchList(key),230);
    });
    try{
      await refreshOverview();
    }catch(error){
      if(current===token && root?.isConnected)
        root.innerHTML='<p class="notice-block">전체 분류 연결 실패: '+esc(error.message)+
          '</p><button class="btn" data-world-action="retry-overview">재시도</button>';
      return;
    }
    await Promise.all(listIds.map(fetchList));
  };
})();
