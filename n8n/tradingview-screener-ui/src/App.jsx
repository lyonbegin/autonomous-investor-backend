import React,{useCallback,useEffect,useMemo,useRef,useState} from 'react';
import {Search,ChevronDown,Plus,MoreHorizontal,RotateCw,Maximize2,Minimize2,
  Settings2,Undo2,Redo2,SlidersHorizontal,Columns3,Grid2X2,Table2,
  Globe2,UserRound,Star,Save,Check,X,ArrowDown,ArrowUp,Filter,
  Copy,Download,ListFilter,Lock,Bookmark,AlertCircle,Menu,ExternalLink} from 'lucide-react';

const MARKETS='america argentina australia austria bahrain bangladesh belgium bulgaria brazil canada chile china colombia croatia cyprus czech denmark egypt estonia finland france germany greece hongkong hungary iceland india indonesia ireland israel italy japan kenya kuwait latvia lithuania luxembourg malaysia mexico morocco netherlands newzealand nigeria norway pakistan peru philippines poland portugal qatar romania russia ksa serbia singapore slovakia slovenia rsa korea spain srilanka sweden switzerland taiwan thailand tunisia turkey uae uk venezuela vietnam'.split(' ');
const COUNTRY_NAMES={america:'미국',korea:'대한민국',japan:'일본',china:'중국',hongkong:'홍콩',india:'인도',canada:'캐나다',uk:'영국',germany:'독일',france:'프랑스',australia:'호주',taiwan:'대만',singapore:'싱가포르',brazil:'브라질',vietnam:'베트남',thailand:'태국',switzerland:'스위스',spain:'스페인',italy:'이탈리아',netherlands:'네덜란드',mexico:'멕시코',sweden:'스웨덴',turkey:'튀르키예',russia:'러시아',ksa:'사우디아라비아',uae:'아랍에미리트',rsa:'남아프리카',newzealand:'뉴질랜드'};
const FLAG={america:'🇺🇸',korea:'🇰🇷',japan:'🇯🇵',china:'🇨🇳',hongkong:'🇭🇰',india:'🇮🇳',canada:'🇨🇦',uk:'🇬🇧',germany:'🇩🇪',france:'🇫🇷',australia:'🇦🇺',taiwan:'🇹🇼',brazil:'🇧🇷',singapore:'🇸🇬',vietnam:'🇻🇳'};
const STOCK_PILLS=['왓치리스트','지수','가격','체인지 %','시가총액','P/E','EPS 희석 성장','배당 수익 %','섹터','애널리스트 평점','퍼포먼스 %','매출 성장률','PEG','ROE','베타','최근 실적 발표날짜','다가올 실적 발표날짜'];
const ETF_PILLS=['왓치리스트','자산 클래스','포커스','틈새 시장','홀딩스 지역','브랜드','퍼포먼스 %','NAV 총 수익률','AUM','운용 스타일','전략','배당 혜택','배당 수익률 % (표시됨)','배당 빈도','레버리지 활용','지출 비율','UCITS 컴플리트'];
const BOND_PILLS=['왓치리스트','발급자 유형','발행자','채권 최저 수익률 %','쿠폰 %','쿠폰 타입','쿠폰 빈도','머튜어리티 데이트','가격 %','미결제 금액','발행 통화','쿠폰 통화','소스'];
const COL={
  'ticker-view':'심볼','crypto_total_rank':'랭크','24h_close_change|5':'체인지 % 24시','24h_vol|5':'달러 표시 거래량 24시','24h_vol_change|5':'볼륨 변화 % 24시','24h_vol_cmc':'달러 표시 거래량 24시','24h_vol_to_market_cap':'볼륨 / 시가총액','socialdominance':'소셜 점유 %','crypto_common_categories.tr':'카테고리','TechRating_1D.tr':'기술 등급','blockchain-id.tr':'블록체인','dex_txs_count_24h':'거래 24시','dex_trading_volume_24h':'거래량 24시','dex_txs_count_uniq_24h':'트레이더 24시','dex_total_liquidity':'유동성','fully_diluted_value':'FDV','close':'가격','change':'체인지 %','volume':'볼륨','relative_volume_10d_calc':'상대 볼륨','market_cap_basic':'시가총액','price_earnings_ttm':'P/E',
  'earnings_per_share_diluted_ttm':'EPS 희석 순마진','earnings_per_share_diluted_yoy_growth_ttm':'EPS 희석 성장 TTM YoY','dividends_yield_current':'배당 수익 %',
  'sector.tr':'섹터','AnalystRating.tr':'애널리스트 평점','Value.Traded':'가격 × 볼륨','aum':'AUM','nav_total_return.3Y':'NAV 총 수익률 3해',
  'etf_holdings_count':'홀딩스','expense_ratio':'지출 비율','asset_class.tr':'자산 클래스','focus.tr':'포커스',
  'isin-displayed':'ISIN','yield_to_worst':'채권 최저 수익률 %','close_pct':'가격 %','close_net':'가격','current_coupon':'쿠폰 %','maturity_date':'머튜어리티 데이트',
  'redemption_type.tr':'콜/풋','bond_issuer_type.tr':'발급자 유형','bond_snp_rating_lt.tr':'S&P 등급','bond_fitch_rating_lt.tr':'피치 등급',
  'bond_moodys_rating_lt.tr':'무디스 신용등급','exchange.tr':'거래소','source-logoid':'소스',
  'Perf.W':'1주','Perf.1M':'1달','Perf.3M':'3달','Perf.6M':'6달','Perf.YTD':'연초 대비','Perf.Y':'1년','Perf.5Y':'5년',
  'Perf.10Y':'10년','Perf.All':'전체','Volatility.W':'주 변동성','Volatility.M':'월 변동성',
  'TechRating_1D.tr':'테크니컬 등급','MARating_1D.tr':'이동 평균 등급','OsRating_1D.tr':'오실레이터 등급',
  'RSI':'RSI','Mom':'모멘텀','AO':'AO','CCI20':'CCI20','Stoch.K':'스토캐스틱 K','Stoch.D':'스토캐스틱 D',
  'modified_duration':'수정 듀레이션','convexity':'볼록성','dv_01':'DV01','bond_issuer.tr':'발행자',
  'issue_date':'발행일','issue_amount':'발행 금액','outstanding_amount':'미결제 금액',
  'coupon_frequency.tr':'쿠폰 빈도','coupon_type_current.tr':'쿠폰 타입',
  'nav':'NAV','nav_discount_premium':'NAV 프리미엄','fund_flows.1M':'1달 자금 흐름','fund_flows.3M':'3달 자금 흐름','fund_flows.1Y':'1년 자금 흐름',
  'weight_top_10':'상위 10 종목 비중','beta_1_year':'1년 베타','beta_3_year':'3년 베타'};
const HIDDEN=new Set(['type','typespecs','pricescale','minmov','fractional','minmove2','currency','fundamental_currency_code','market','sector','AnalystRating','bond_snp_rating_lt','bond_fitch_rating_lt','bond_moodys_rating_lt','source-logoid','blockchain-id','TechRating_1D']);
const CONFIG={
stock:{name:'스탁 스크리너',title:'올 스탁',kind:'stock',market:'korea',url:'/screener/',tabs:'오버뷰 성과 테크니컬즈 확장_시간 전망 평가 배당 수익성 손익_계산서 대차_대조표 현금_흐름 주당'.split(' ').map(x=>x.replaceAll('_',' ')),pills:STOCK_PILLS,sort:'market_cap_basic',cols:['ticker-view','close','change','volume','relative_volume_10d_calc','market_cap_basic','price_earnings_ttm','earnings_per_share_diluted_ttm','earnings_per_share_diluted_yoy_growth_ttm','dividends_yield_current','sector.tr','AnalystRating.tr']},
etf:{name:'ETF 스크리너',title:'ETF 보관함',kind:'etf',market:'america',url:'/etf-screener/',tabs:['오버뷰','성과','테크니컬즈','확장 시간','자금 흐름','배당','NAV 실적','홀딩스','리스크'],pills:ETF_PILLS,sort:'aum',cols:['ticker-view','close','change','Value.Traded','relative_volume_10d_calc','aum','nav_total_return.3Y','etf_holdings_count','expense_ratio','asset_class.tr','focus.tr']},
bond:{name:'본드 스크리너',title:'전체 채권',kind:'bond',market:'bond',url:'/bond-screener/',tabs:['오버뷰','보안 정보','금리 위험','스프레드','금액','채권 용어','쿠폰','발행자','등급'],pills:BOND_PILLS,sort:'bond_snp_rating_lt',cols:['ticker-view','isin-displayed','yield_to_worst','close_pct','close_net','current_coupon','maturity_date','redemption_type.tr','bond_issuer_type.tr','bond_snp_rating_lt.tr','bond_fitch_rating_lt.tr','bond_moodys_rating_lt.tr','exchange.tr']},
coin:{name:'암호화폐 스크리너',title:'크립토 전체 시장',kind:'coin',market:'coin',url:'/crypto-coins-screener/',tabs:['오버뷰','성과','테크니컬즈','평가','파생상품','주소','거래','센티멘트'],pills:['왓치리스트','랭크','시가총액','FD 시가 총액','볼륨 / 시가총액','잔고 주소','달러 표시 거래량','볼륨 변화 %','거래량 (USD)','체인지 %','퍼포먼스 %','카테고리'],cols:['ticker-view','crypto_total_rank','close','type','typespecs','pricescale','minmov','fractional','minmove2','currency','24h_close_change|5','market_cap_calc','fundamental_currency_code','24h_vol_cmc','circulating_supply','24h_vol_to_market_cap','socialdominance','crypto_common_categories.tr','TechRating_1D','TechRating_1D.tr'],sort:'crypto_total_rank'},
cex:{name:'CEX 스크리너',title:'전체 페어',kind:'crypto',market:'crypto',url:'/cex-screener/',tabs:['오버뷰','성과','테크니컬즈'],pills:['왓치리스트','거래소','심볼 타입','베이스 통화','쿼트 커런시','체인지 %','퍼포먼스 %','달러 표시 거래량','볼륨 변화 %'],cols:['ticker-view','exchange.tr','source-logoid','close','type','typespecs','pricescale','minmov','fractional','minmove2','currency','24h_close_change|5','24h_vol|5','24h_vol_change|5','TechRating_1D','TechRating_1D.tr'],sort:'24h_vol|5'},
dex:{name:'DEX 스크리너',title:'전체 페어',kind:'crypto',market:'crypto',url:'/dex-screener/',tabs:['오버뷰','성과','테크니컬즈','거래','거래량','트레이더'],pills:['왓치리스트','블록체인','거래소','체인지 %','거래','거래량','유동성','FDV','트레이더','고유 매수자','고유 매도자','퍼포먼스 %'],cols:['ticker-view','blockchain-id.tr','blockchain-id','exchange.tr','source-logoid','close','type','typespecs','pricescale','minmov','fractional','minmove2','currency','24h_close_change|5','dex_txs_count_24h','dex_trading_volume_24h','dex_txs_count_uniq_24h','dex_total_liquidity','fully_diluted_value','TechRating_1D','TechRating_1D.tr'],sort:'dex_txs_count_24h'},
pine:{name:'Pine 스크리너',title:'내 Pine 스크립트',kind:'pine',market:'',url:'/pine-screener/',tabs:[],pills:['스크립트','심볼','타임프레임'],cols:[],sort:''}
};
const PATH_PRODUCT=Object.fromEntries(Object.entries(CONFIG).map(([k,v])=>[v.url,k]));
function getProduct(){return PATH_PRODUCT[location.pathname]||PATH_PRODUCT[location.pathname+'/']||'stock';}
function fmtCompact(n){if(typeof n!=='number')return String(n??'—');const a=Math.abs(n);const unit=a>=1e12?1e12:a>=1e9?1e9:a>=1e6?1e6:a>=1e3?1e3:1;const suffix=unit===1e12?' T':unit===1e9?' B':unit===1e6?' M':unit===1e3?' K':'';return (n/unit).toLocaleString('en-US',{maximumFractionDigits:2})+suffix;}
const PERCENT_FIELDS=/change|Perf\.|Volatility|yield|ratio|margin|growth|expense|coupon|pct|discount_premium|weight_top_|nav_total_return|socialdominance|24h_close/i;
const COLOR_FIELDS=/^change$|^Perf\.|nav_total_return|_growth|^TechRating|^AnalystRating|24h_close_change|24h_vol_change/i;
const DATE_FIELDS=/date|maturity|fiscal_period_end/i;
function formatValue(v,key,currency,locale='ko'){if(v===undefined||v===null||v==='')return '—';if(typeof v==='object')return v.name||v.description||'—';if(typeof v==='boolean')return v?'예':'아니요';if(typeof v==='string')return v;if(DATE_FIELDS.test(key)){if(v>1e8)return new Date(v*1000).toISOString().slice(0,10);return String(v);}if(PERCENT_FIELDS.test(key))return (v>0&&COLOR_FIELDS.test(key)?'+':'')+v.toFixed(2)+'%';if(key==='relative_volume_10d_calc'||key==='RSI')return v.toFixed(2);
 if(key==='etf_holdings_count'||key==='rank'||key==='crypto_total_rank'||key==='dex_txs_count_uniq_24h')return String(Math.round(v));
 if(key==='current_coupon')return v.toFixed(3)+'%';if(key==='close'||key==='close_net'||key==='nav')return v.toLocaleString('en-US',{maximumFractionDigits:currency==='KRW'?0:2,minimumFractionDigits:currency==='KRW'?0:2})+(currency?' '+currency:'');if(key==='market_cap_basic'||key==='market_cap_calc'||key==='aum'||key==='Value.Traded'||key==='issue_amount'||key==='outstanding_amount'||key==='24h_vol|5'||key==='24h_vol_cmc'||key==='dex_trading_volume_24h'||key==='dex_total_liquidity'||key==='fully_diluted_value')return fmtCompact(v)+(currency?' '+currency:'');return fmtCompact(v);}
function colname(key,product){if(key==='exchange.tr'&&product==='bond')return '소스';return COL[key]||key.replaceAll('.tr','').replaceAll('_',' ');}
function pillField(label,kind){const stock={'가격':'close','체인지 %':'change','시가총액':'market_cap_basic','P/E':'price_earnings_ttm','EPS 희석 성장':'earnings_per_share_diluted_yoy_growth_ttm','배당 수익 %':'dividends_yield_current','ROE':'return_on_equity_fq','베타':'beta_1_year','퍼포먼스 %':'Perf.1M'};
const etf={'AUM':'aum','지출 비율':'expense_ratio','NAV 총 수익률':'nav_total_return.3Y','배당 수익률 % (표시됨)':'dividends_yield','퍼포먼스 %':'Perf.1M'};
const bond={'채권 최저 수익률 %':'yield_to_worst','쿠폰 %':'current_coupon','가격 %':'close_pct','미결제 금액':'outstanding_amount','발급자 유형':'bond_issuer_type','발행자':'bond_issuer','쿠폰 타입':'coupon_type_current','쿠폰 빈도':'coupon_frequency','발행 통화':'fundamental_currency_code','쿠폰 통화':'coupon_currency','소스':'source'};
return (kind==='stock'?stock:kind==='etf'?etf:bond)[label]||null;}
function basePayload(product,market,columns,sortField,pageIndex=0,pageSize=100){
 const props={columns,ignore_unknown_fields:false,options:{lang:'ko'},range:[pageIndex*pageSize,(pageIndex+1)*pageSize],sort:{sortBy:sortField,sortOrder:product==='coin'?'asc':'desc'},markets:[market]};
 if(product==='stock'){props.filter=[{left:'is_primary',operation:'equal',right:true}];props.filter2={operator:'and',operands:[
 {operation:{operator:'or',operands:[
 {operation:{operator:'and',operands:[{expression:{left:'type',operation:'equal',right:'stock'}},{expression:{left:'typespecs',operation:'has',right:['common']}}]}},
 {operation:{operator:'and',operands:[{expression:{left:'type',operation:'equal',right:'stock'}},{expression:{left:'typespecs',operation:'has',right:['preferred']}}]}},
 {operation:{operator:'and',operands:[{expression:{left:'type',operation:'equal',right:'dr'}}]}},
 {operation:{operator:'and',operands:[{expression:{left:'type',operation:'equal',right:'fund'}},{expression:{left:'typespecs',operation:'has_none_of',right:['etf','mutual']}}]}}
 ]}},{expression:{left:'typespecs',operation:'has_none_of',right:['pre-ipo']}}]};}
 if(product==='cex')props.filter2={operator:'and',operands:[{expression:{left:'centralization',operation:'equal',right:'cex'}}]};
 if(product==='dex')props.filter2={operator:'and',operands:[{operation:{operator:'and',operands:[{expression:{left:'centralization',operation:'equal',right:'dex'}},{expression:{left:'currency_id',operation:'equal',right:'USD'}}]}},{operation:{operator:'or',operands:[{operation:{operator:'and',operands:[{expression:{left:'type',operation:'equal',right:'spot'}}]}}]}}]};
 if(product==='etf')props.filter2={operator:'and',operands:[{operation:{operator:'or',operands:[{operation:{operator:'and',operands:[{expression:{left:'typespecs',operation:'has',right:['etf']}}]}},{operation:{operator:'and',operands:[{expression:{left:'type',operation:'equal',right:'structured'}}]}}]}}]};
 return props;
}
function usableColumns(cols){return cols.filter((c,i)=>i===0||!HIDDEN.has(c));}
function BadgeLogo({name,code,logo}){const [failed,setFailed]=useState(false);let chr=String(name||code||'?').trim().charAt(0).toUpperCase();const id=typeof logo?.logoid==='string'?logo.logoid:null;return id&&!failed?<img className="symbol-logo external-logo" src={'https://s3-symbol-logo.tradingview.com/'+encodeURIComponent(id)+'.svg'} onError={()=>setFailed(true)} alt=""/>:<span className={'symbol-logo symbol-logo-'+(chr.charCodeAt(0)%6)}>{chr}</span>}
function IconButton({title,children,onClick,disabled=false,qa}){return <button type="button" title={title} aria-label={title} data-qa-id={qa} className="icon-btn" disabled={disabled} onClick={onClick}>{children}</button>;}
function getFlag(m){return FLAG[m]||'🌐';}
function App(){
 const [product,setProduct]=useState(getProduct),cfg=CONFIG[product];
 const [market,setMarket]=useState(cfg.market),[tab,setTab]=useState(0),[filterLabels,setFilterLabels]=useState(cfg.pills);
 const [pills,setPills]=useState({}),[popup,setPopup]=useState(''),[search,setSearch]=useState(''),
 [marketQuery,setMarketQuery]=useState(''),[filterQuery,setFilterQuery]=useState(''),[pending,setPending]=useState({min:'',max:'',choices:[]}),
 [page,setPage]=useState(0),[pageSize,setPageSize]=useState(100),[data,setData]=useState(null),
 [source,setSource]=useState(''),[loading,setLoading]=useState(false),[error,setError]=useState(''),
 [refData,setRefData]=useState(null),[customCols,setCustomCols]=useState(null),
 [sort,setSort]=useState({by:cfg.sort,dir:product==='coin'?'asc':'desc'}),[settings,setSettings]=useState({compact:false,showLogos:true,hideEmpty:false,freezeTicker:true,showRestrictedColumns:false}),
 [undo,setUndo]=useState([]),[redo,setRedo]=useState([]),[showAllFilters,setShowAllFilters]=useState(false),
 [saved,setSaved]=useState([]),[fullscreen,setFullscreen]=useState(false),[selectedRows,setSelectedRows]=useState([]),
 [columnSearch,setColumnSearch]=useState(''),[refresh,setRefresh]=useState(0),[toast,setToast]=useState('');
 const tableRef=useRef(null),popoverRef=useRef(null),searchRef=useRef(null);
 useEffect(()=>{fetch('/reference.json').then(r=>r.ok?r.json():null).then(setRefData).catch(()=>{});try{setSaved(JSON.parse(localStorage.getItem('tv-screener-saves')||'[]'));}catch{}},[]);
 useEffect(()=>{const click=e=>{if(popoverRef.current&&!popoverRef.current.contains(e.target)&&!e.target.closest('[data-pop]'))setPopup('')};document.addEventListener('mousedown',click);return()=>document.removeEventListener('mousedown',click)},[]);
 useEffect(()=>{const handle=e=>{
  if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z'){e.preventDefault();undoAction();}
  if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='y'){e.preventDefault();redoAction();}
  if(e.shiftKey&&e.key.toLowerCase()==='f'){e.preventDefault();setPopup('add-filter');}
  if(e.shiftKey&&e.key.toLowerCase()==='c'){e.preventDefault();setPopup('columns');}
  if(e.shiftKey&&e.key.toLowerCase()==='m'){e.preventDefault();setFullscreen(v=>!v);}
  if(e.key==='Escape')setPopup('');
 };window.addEventListener('keydown',handle);return()=>window.removeEventListener('keydown',handle)},[undo,redo,market,filterLabels,pills,tab,sort]);
 function snapshot(){return {market,filterLabels:[...filterLabels],pills:{...pills},tab,sort:{...sort},customCols:customCols?[...customCols]:null};}
 function changeState(fn){setUndo(v=>[...v.slice(-19),snapshot()]);setRedo([]);fn();}
 function applySnapshot(s){setMarket(s.market);setFilterLabels(s.filterLabels);setPills(s.pills);setTab(s.tab);setSort(s.sort);setCustomCols(s.customCols);setPage(0);setRefresh(v=>v+1);}
 function undoAction(){if(!undo.length)return;setRedo(v=>[...v,snapshot()]);applySnapshot(undo.at(-1));setUndo(v=>v.slice(0,-1));}
 function redoAction(){if(!redo.length)return;setUndo(v=>[...v,snapshot()]);applySnapshot(redo.at(-1));setRedo(v=>v.slice(0,-1));}
 function switchProduct(id){if(!CONFIG[id])return;setProduct(id);history.pushState(null,'',CONFIG[id].url);setMarket(CONFIG[id].market);setTab(0);setFilterLabels(CONFIG[id].pills);setPills({});setPopup('');setSort({by:CONFIG[id].sort,dir:id==='coin'?'asc':'desc'});setCustomCols(null);setPage(0);setError('');setData(null);setSource('');setSearch('');setUndo([]);setRedo([]);}
 useEffect(()=>{const back=()=>switchProduct(getProduct());window.addEventListener('popstate',back);return()=>window.removeEventListener('popstate',back)},[]);
 const fixture=refData?.products?.[product]?.tabs?.[String(tab)]||refData?.products?.[product]?.tabs?.['0'];
 const currentCols=useMemo(()=>customCols||fixture?.columns||cfg.cols,[customCols,fixture,cfg.cols]);
 const defaultRequest=refData?.products?.[product]?.tabs?.['0']?.request;
 const makePayload=useCallback(()=>{
   const cols=currentCols.length?currentCols:cfg.cols;
   const template=defaultRequest?structuredClone(defaultRequest):basePayload(product,market,cols,sort.by,page,pageSize);
   template.columns=cols;template.markets=[market];template.range=[page*pageSize,(page+1)*pageSize];
   template.sort={sortBy:sort.by||cfg.sort,sortOrder:sort.dir};
   template.options={...template.options,lang:'ko'};
   const conditions=[];
   Object.entries(pills).forEach(([label,item])=>{
     const field=pillField(label,product);
     if(!field||!item||item.enabled===false)return;
     if(item.type==='range'){
       if(item.min!==''&&!Number.isNaN(Number(item.min)))conditions.push({left:field,operation:'egreater',right:Number(item.min)});
       if(item.max!==''&&!Number.isNaN(Number(item.max)))conditions.push({left:field,operation:'eless',right:Number(item.max)});
     }else if(item.type==='choices'&&item.choices?.length)conditions.push({left:field,operation:'in_range',right:item.choices});
   });
   if(conditions.length)template.filter=[...(template.filter||[]),...conditions];
   return template;
 },[product,market,currentCols,sort,page,pageSize,pills,defaultRequest,cfg.sort]);
 useEffect(()=>{
  if(product==='pine'){setData({totalCount:0,data:[]});setSource('pine');return;}
  let cancelled=false;
  setLoading(true);setError('');
  const payload=makePayload();
  const productKind=cfg.kind;
  fetch('/api/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:productKind,product,market,payload})})
   .then(async r=>{let j;try{j=await r.json()}catch{throw Error('응답 JSON 오류 (HTTP '+r.status+')')};if(!r.ok||!Array.isArray(j.data))throw Error(j.error||'HTTP '+r.status);return j;})
   .then(d=>{if(cancelled)return;setData(d);setSource('live');setLoading(false);})
   .catch(err=>{if(cancelled)return;setError(String(err.message||err));
       if(fixture?.response&&market===cfg.market&&page===0&&!Object.keys(pills).length){setData(fixture.response);setSource('captured');}
       else{setData({totalCount:0,data:[]});setSource('error');}
       setLoading(false);
   });
  return()=>{cancelled=true};
 },[product,market,tab,sort,page,pageSize,refresh,pills,customCols,refData]);
 const visibleCols=useMemo(()=>usableColumns(currentCols),[currentCols]);
 const normalizedRows=useMemo(()=>{
  const rows=(data?.data||[]).map(row=>{const map={};currentCols.forEach((key,i)=>map[key]=row.d?.[i]);return {id:row.s,values:map};});
  if(!search.trim())return rows;
  const q=search.toLowerCase();return rows.filter(x=>(x.id+' '+(x.values['ticker-view']?.description||'')).toLowerCase().includes(q));
 },[data,currentCols,search]);
 function showToast(str){setToast(str);window.setTimeout(()=>setToast(''),2700);}
 function applyFilter(label,pendingData){changeState(()=>{setPills(v=>({...v,[label]:pendingData}));setPage(0)});setPopup('');}
 function onFilterClick(label){setPending(pills[label]||{min:'',max:'',choices:[],type:'range'});setFilterQuery('');setPopup('filter:'+label);}
 function selectMarket(code){changeState(()=>{setMarket(code);setPage(0);setData(null)});setPopup('');setMarketQuery('');}
 function saveScreen(){const name=window.prompt('스크린 다음 이름으로 저장…',cfg.title+' - '+(COUNTRY_NAMES[market]||market));if(!name)return;const value={id:Date.now(),name,product,view:snapshot()};const arr=[...saved,value];setSaved(arr);localStorage.setItem('tv-screener-saves',JSON.stringify(arr));showToast('스크린을 저장했습니다.');}
 function exportCSV(){const quote=x=>'"'+String(x??'').replaceAll('"','""')+'"';const lines=[visibleCols.map(colname).map(quote).join(',')];normalizedRows.forEach(row=>lines.push(visibleCols.map(c=>quote(c==='ticker-view'?row.values[c]?.description||row.id:row.values[c])).join(',')));const a=document.createElement('a');a.href=URL.createObjectURL(new Blob(['\ufeff'+lines.join('\n')],{type:'text/csv;charset=utf-8'}));a.download='screener_'+product+'_'+market+'.csv';a.click();URL.revokeObjectURL(a.href);}
 const availableAdd=useMemo(()=>[...new Set([...cfg.pills,...Object.values(COL)])].filter(x=>!filterLabels.includes(x)),[cfg,filterLabels]);
 const onColumnSort=key=>{changeState(()=>setSort(v=>({by:key,dir:v.by===key&&v.dir==='desc'?'asc':'desc'})));setPage(0);};
 const colsToOffer=Array.from(new Set([...cfg.cols,...(refData?.products?.[product]?Object.values(refData.products[product].tabs).flatMap(t=>t.columns):[])]));
 const tableDataLength=normalizedRows.length;
 return <div className={'site '+(fullscreen?'is-fullscreen ':'')+(settings.compact?'compact ':'')+(['cex','dex'].includes(product)?'short-filters ':'')} data-product={product} data-source={source} data-testid="screener-app">
   {!fullscreen&&<header className="site-header">
     <button className="tv-logo" onClick={()=>switchProduct('stock')} aria-label="홈"><span className="tv-mark">◢◤</span>TradingView</button>
     <div className="top-links"><button className="global-search"><Search size={20}/>찾기 (Ctrl+K)</button><span className="active">프로덕트</span><span>커뮤니티</span><span>마켓</span><span>브로커</span><span>더보기</span></div>
     <div className="header-right"><button><Globe2 size={20}/> KO</button><button title="프로필"><UserRound size={20}/></button><button className="get-started" onClick={()=>setPopup('account')}>지금 시작</button></div>
   </header>}
   <main id="tv-content" className="screener-main">
     <section className="page-heading">
       <div className="screener-switch-container">
         <button data-pop className="category-switch" onClick={()=>setPopup(v=>v==='products'?'':'products')}>{cfg.name}<ChevronDown size={14}/></button>
       </div>
       <div className="heading-line">
         <button className="screen-name" data-pop data-qa-id="screen-title" onClick={()=>setPopup(v=>v==='screens'?'':'screens')}>{cfg.title}<ChevronDown size={19}/></button>
         <div className="right-tools"><IconButton title="되돌리기" qa="screener-undo-button" disabled={!undo.length} onClick={undoAction}><Undo2 size={18}/></IconButton><IconButton title="다시 실행" qa="screener-redo-button" disabled={!redo.length} onClick={redoAction}><Redo2 size={18}/></IconButton><IconButton title="스크린 저장" onClick={saveScreen}><Save size={18}/></IconButton><IconButton title="스크리너 세팅" qa="screener-topbar-settings" onClick={()=>setPopup('settings')}><Settings2 size={21}/></IconButton></div>
       </div>
     </section>
     <section className="pills-panel">{product==='stock'&&<button data-pop className="filter-pill ai-pill" onClick={()=>setPopup('add-filter')}>✦ AI</button>}
       {(product==='stock'||product==='etf')&&<button data-pop className="filter-pill market-pill" data-testid="market-filter" onClick={()=>{setPopup('market');setMarketQuery('')}}><span>{getFlag(market)}</span>{market==='korea'?'KR':market==='america'?'US':(COUNTRY_NAMES[market]||market)} <ChevronDown size={14}/></button>}
       <div className="pills-scroller" data-testid="filter-pills">
         {filterLabels.map((label,index)=><React.Fragment key={label}>
           {index===0&&product!=='bond'&&product!=='pine'?<span className="pill-divider"/>:null}
           <button data-pop draggable onDragStart={e=>e.dataTransfer.setData('text/plain',label)}
             onDragOver={e=>e.preventDefault()} onDrop={e=>{const from=e.dataTransfer.getData('text/plain');if(from!==label)changeState(()=>setFilterLabels(a=>{const b=a.filter(x=>x!==from);b.splice(b.indexOf(label),0,from);return b;}))}}
             title={label} className={'filter-pill '+(pills[label]?'filter-applied':'')} data-testid={'filter-'+label}
             onClick={()=>onFilterClick(label)}>{pills[label]?.choices?.length?label+': '+pills[label].choices.join(','):label}
              <ChevronDown size={13}/>{pills[label]&&<span className="active-dot"/>}
           </button>
         </React.Fragment>)}
         <IconButton title="새 필터 넣기" qa="screener-add-new-filter" onClick={()=>{setPopup('add-filter');setFilterQuery('')}}><Plus size={20}/></IconButton>
         <IconButton title="필터 옵션" qa="reset-options-button" onClick={()=>setPopup('filter-options')}><MoreHorizontal size={19}/></IconButton>
       </div>
     </section>
     <section className="tabs-panel">
       {product!=='bond'&&product!=='pine'&&<button className="view-switch" data-pop onClick={()=>setPopup('view')}><Table2 size={20}/>테이블<ChevronDown size={14}/></button>}
       <div className="tab-list" role="tablist" aria-label="컬럼 프리셋">
         {cfg.tabs.map((t,i)=><button key={t} className={'tab-btn '+(tab===i?'selected':'')} role="tab" aria-selected={tab===i} data-testid={'tab-'+i} onClick={()=>{changeState(()=>{setTab(i);setCustomCols(null)});setPage(0)}}>{t}</button>)}
         {cfg.tabs.length>9&&<button className="tab-more" data-pop onClick={()=>setPopup('more-tabs')}>더보기 <ChevronDown size={13}/></button>}
       </div>
       <div className="tab-tools">
         <IconButton title="리프레쉬" qa="screener-refresh-button" onClick={()=>setRefresh(x=>x+1)}><RotateCw size={18} className={loading?'spin':''}/></IconButton>
         <IconButton title={fullscreen?'전체화면 종료':'최대화'} qa="screener-enter-fullscreen" onClick={()=>setFullscreen(x=>!x)}>{fullscreen?<Minimize2 size={18}/>:<Maximize2 size={18}/>}</IconButton>
         <IconButton title="데이터 내보내기" onClick={exportCSV}><Download size={18}/></IconButton>
       </div>
     </section>
     {product==='pine'&&<><div className="pine-banner">파인 스크리너 <span>BETA</span></div><div className="pine-empty"><div className="pine-art"><span>◇</span><span>△</span></div><div className="pine-title">로그인하여 Pine Screener를 사용하세요</div><p>지표별로 왓치리스트를 스캔하고 커스텀 설정을 적용하세요. 주식, 암호화폐, 외환 등 거래<br/>하는 모든 자산에 적용됩니다.</p><button className="pine-login" onClick={()=>setPopup('account')}>로그인</button></div></>}
     {product!=='pine'&&<>
       <section className="table-viewport" ref={tableRef} data-testid="screener-table-viewport">
         <table className="screener-table" data-testid="screener-table">
           <thead><tr>
             {visibleCols.map((column,i)=><th key={column} className={(i===0?'sticky-col ':'')+(column==='ticker-view'?'symbol-head ':'')+(!['ticker-view','isin-displayed'].includes(column)?'align-right':'')} onClick={()=>onColumnSort(column)} title={colname(column)} data-field={column} draggable
               onDragStart={e=>e.dataTransfer.setData('text/plain',column)} onDragOver={e=>e.preventDefault()}
               onDrop={e=>{const dragging=e.dataTransfer.getData('text/plain');changeState(()=>setCustomCols(old=>{const b=[...(old||currentCols)];const idx=b.indexOf(dragging);const dest=b.indexOf(column);if(idx>=0&&dest>=0){b.splice(idx,1);b.splice(dest,0,dragging)}return b;}))}}>
               {i===0?<div className="symbol-header-content"><IconButton title="심볼 찾기" onClick={e=>setPopup('symbol-search')}><Search size={20}/></IconButton><span>심볼 <small data-testid="total-count">{data?.totalCount?.toLocaleString('en-US')||'0'}</small></span></div>:<span>{colname(column,product)}{sort.by===column&&(sort.dir==='desc'?<ArrowDown size={14}/>:<ArrowUp size={14}/>)}</span>}
             </th>)}
             <th className="add-column-head"><IconButton title="컬럼 셋업" qa="screener-add-column-button" onClick={()=>{setPopup('columns');setColumnSearch('')}}><Plus size={22}/></IconButton></th>
           </tr></thead>
           <tbody>{normalizedRows.map((row,index)=>{
             const identity=row.values['ticker-view']||{}, code=identity.name||row.id?.split(':').pop(), desc=identity.description||row.id;
             const currency=row.values.currency||row.values.fundamental_currency_code||(market==='korea'?'KRW':market==='america'?'USD':'');
             return <tr key={row.id||index} data-rowkey={row.id} className={selectedRows.includes(row.id)?'is-selected':''} onClick={()=>setSelectedRows(s=>s.includes(row.id)?s.filter(x=>x!==row.id):[...s,row.id])}>
               {visibleCols.map((column,i)=>{
                const val=row.values[column];const percent=COLOR_FIELDS.test(column)&&typeof val==='number';const numeric=typeof val==='number';
                return <td key={column} className={(i===0?'sticky-col ':'')+(numeric?'align-right ':'')+(percent?(val<0?'negative':val>0?'positive':''):'')}>
                  {column==='ticker-view'?<div className="ticker-value">
                     {settings.showLogos&&<BadgeLogo name={desc} code={code} logo={identity.logo}/>}
                     {product!=='bond'&&<span className="ticker-code">{code}</span>}
                     <a href={'https://kr.tradingview.com/symbols/'+encodeURIComponent(row.id?.replace(':','-'))+'/'} title={desc} target="_blank" rel="noopener noreferrer">{desc}</a>
                   </div>:
                   column==='isin-displayed'&&product==='bond'&&!settings.showRestrictedColumns?<Lock size={14} className="locked-cell"/>:column==='isin-displayed'?<div className="isin-value">{typeof val==='string'?val:'—'}{val&&<button title="ISIN 카피" onClick={e=>{e.stopPropagation();navigator.clipboard?.writeText(val);showToast('ISIN 복사됨')}}><Copy size={12}/></button>}</div>:
                   (product==='bond'&&index>8&&index<15)?<span className="paywall-blur">{formatValue(val,column,currency)}</span>:
                   (product==='bond'&&/(redemption_type|bond_snp_rating|bond_fitch_rating|bond_moodys_rating)/.test(column)&&!settings.showRestrictedColumns)?<Lock size={14} className="locked-cell"/>:(/(Rating|rating)/.test(column)&&typeof val==='string'&&/^(AAA|AA|Aaa|BBB)/.test(val))?<span className="rating">{val}</span>:
                   formatValue(val,column,currency)}
                 </td>
               })}
               <td className="row-tail"></td>
             </tr>
           })}
           {!loading&&!normalizedRows.length&&<tr><td className="no-results" colSpan={visibleCols.length+1}>조회 결과가 없습니다.{error&&<span> · 데이터 요청 오류: {error}</span>}</td></tr>}
           </tbody>
         </table>
         {product==='bond'&&<div className="bond-registration"><h3>Bond Screener의 모든 기능을 이용하세요</h3><p>Ultimate 버전으로 업그레이드하여 제한 없이 채권 시장을 탐색해 보세요. 전체 결과를 확인하고,<br/> 필요한 필터를 적용하여 분석을 더욱 심층적으로 진행할 수 있습니다.</p><button onClick={()=>showToast('이 화면은 공개 스크리너의 UI 비교용입니다.')}>Ultimate으로 업그레이드</button></div>}
       </section>
       <footer className="table-footer">
         <span className="source-hint" title={error||''}>{loading?'조회 중…':source==='live'?'스캐너 응답 · 실시간 조회':source==='captured'?'2026-11-06 캡처 데이터 (오프라인 대체)':'스캐너 조회 실패'}</span>
         <span className="pagination">{page*pageSize+1}–{Math.min((page+1)*pageSize,data?.totalCount||0)} / {(data?.totalCount||0).toLocaleString('en-US')}</span>
         <button onClick={()=>setPage(v=>Math.max(0,v-1))} disabled={page===0}>〈</button>
         <span>{page+1}</span><button onClick={()=>setPage(v=>v+1)} disabled={(page+1)*pageSize>=(data?.totalCount||0)}>〉</button>
         <select aria-label="페이지당 행 수" value={pageSize} onChange={e=>{setPageSize(Number(e.target.value));setPage(0)}}><option value="50">50</option><option value="100">100</option><option value="200">200</option></select>
       </footer>
     </>}
   </main>
   {popup&&<div className={'popover popover-'+popup.split(':')[0]} ref={popoverRef} data-testid="active-popover">
     <div className="pop-header"><strong>{popup==='products'?'스크리너 선택':popup==='market'?'마켓 선택':popup==='screens'?'스크린':popup==='columns'?'컬럼 셋업':popup==='add-filter'?'새 필터 넣기':popup==='settings'?'스크리너 세팅':popup==='view'?'보기':popup==='filter-options'?'필터 옵션':popup==='more-tabs'?'컬럼 프리셋':popup==='symbol-search'?'심볼 찾기':popup.startsWith('filter:')?popup.slice(7):'메뉴'}</strong><button onClick={()=>setPopup('')}><X size={18}/></button></div>
     {popup==='products'&&<div className="option-list">{Object.entries(CONFIG).map(([id,v])=><button key={id} onClick={()=>switchProduct(id)}><span>{v.name}</span>{id===product&&<Check size={16}/>}</button>)}</div>}
     {popup==='market'&&<><input autoFocus className="popup-search" placeholder="국가 및 시장 찾기" value={marketQuery} onChange={e=>setMarketQuery(e.target.value)}/><div className="option-list long-list">{MARKETS.filter(m=>(COUNTRY_NAMES[m]||m).toLowerCase().includes(marketQuery.toLowerCase())||m.includes(marketQuery.toLowerCase())).map(m=><button key={m} onClick={()=>selectMarket(m)}><span>{getFlag(m)}　{COUNTRY_NAMES[m]||m} <small>{m}</small></span>{m===market&&<Check size={16}/>}</button>)}</div></>}
     {popup==='screens'&&<div className="option-list"><button onClick={()=>setPopup('')}>{cfg.title}<Check size={16}/></button>{saved.filter(s=>s.product===product).map(s=><button key={s.id} onClick={()=>{applySnapshot(s.view);setPopup('')}}>{s.name}</button>)}<button onClick={saveScreen}><Plus size={16}/>새 스크린 저장</button></div>}
     {popup==='view'&&<div className="option-list"><button onClick={()=>setPopup('')}><Table2 size={16}/>테이블 <Check size={16}/></button><button onClick={()=>{setSettings(v=>({...v,compact:!v.compact}));setPopup('')}}><Grid2X2 size={16}/>컴팩트 테이블</button></div>}
     {popup==='settings'&&<div className="settings-list">{[['compact','행 높이 줄이기'],['showLogos','심볼 로고 표시'],['freezeTicker','첫 열 고정'],['hideEmpty','빈 셀 숨기기'],['showRestrictedColumns','채권 제한 데이터 보기']].map(([key,label])=><label key={key}><input type="checkbox" checked={settings[key]} onChange={e=>setSettings(v=>({...v,[key]:e.target.checked}))}/>{label}</label>)}<button className="apply-btn" onClick={()=>setPopup('')}>확인</button></div>}
     {popup==='filter-options'&&<div className="option-list"><button onClick={()=>{changeState(()=>setPills({}));setPopup('')}}><RotateCw size={16}/>모든 필터 초기화</button><button onClick={()=>{setShowAllFilters(v=>!v);setPopup('add-filter')}}><Plus size={16}/>필터 추가</button><button onClick={saveScreen}><Save size={16}/>화면 저장</button></div>}
     {popup==='more-tabs'&&<div className="option-list">{cfg.tabs.map((label,i)=><button key={i} onClick={()=>{changeState(()=>setTab(i));setPopup('')}}>{label}{tab===i&&<Check size={16}/>}</button>)}</div>}
     {popup==='symbol-search'&&<><input autoFocus placeholder="심볼 또는 기업명 찾기" value={search} onChange={e=>setSearch(e.target.value)} className="popup-search"/><div className="popup-subtitle">현재 페이지에서 검색 · 전체 시장 종목 검색과 구분</div><div className="option-list">{normalizedRows.slice(0,10).map(row=><button key={row.id} onClick={()=>setPopup('')}>{row.id}</button>)}</div></>}
     {popup==='columns'&&<><input autoFocus className="popup-search" placeholder="컬럼 검색" value={columnSearch} onChange={e=>setColumnSearch(e.target.value)}/><div className="popup-subtitle">선택된 컬럼 · 클릭하여 추가 또는 제거</div><div className="option-list long-list">{colsToOffer.filter(c=>(colname(c)+' '+c).toLowerCase().includes(columnSearch.toLowerCase())).map(c=><button key={c} onClick={()=>{changeState(()=>setCustomCols(v=>{const old=v||currentCols;return old.includes(c)?old.filter(x=>x!==c):[...old,c]}))}}><span>{colname(c)} <small>{c}</small></span>{currentCols.includes(c)&&<Check size={16}/>}</button>)}</div></>}
     {popup==='add-filter'&&<><input className="popup-search" autoFocus placeholder="필터 찾기" value={filterQuery} onChange={e=>setFilterQuery(e.target.value)}/><div className="option-list long-list">{availableAdd.filter(x=>x.toLowerCase().includes(filterQuery.toLowerCase())).map(label=><button key={label} onClick={()=>{changeState(()=>setFilterLabels(v=>[...v,label]));setPopup('');}}><Plus size={15}/>{label}</button>)}</div></>}
     {popup.startsWith('filter:')&&<div className="filter-edit"><div className="filter-field-name">{pillField(popup.slice(7),product)||popup.slice(7)}</div>
       {popup.slice(7)==='왓치리스트'?<div className="filter-note">왓치리스트에 등록된 종목을 관리합니다. 서버에서 사용자 로그인 목록은 제공되지 않습니다.</div>:
       ['섹터','자산 클래스','발급자 유형','발행자','쿠폰 타입','쿠폰 빈도','발행 통화','쿠폰 통화','소스','포커스','애널리스트 평점','브랜드','홀딩스 지역'].includes(popup.slice(7))?
       <><input className="popup-search" placeholder="값 검색" value={filterQuery} onChange={e=>setFilterQuery(e.target.value)}/>
       <div className="option-list filter-values">{(popup.includes('섹터')?['전자 기술','금융','의료 기술','소비자 내구재','생산자 제조','산업 서비스']:popup.includes('발급자')?['기업','에이전시','소브린','수프라내셔널']:popup.includes('자산 클래스')?['주식','채권','상품','통화','대체']:popup.includes('평점')?['강력 매수','매수','중립','매도','강력 매도']:popup.includes('통화')?['USD','EUR','KRW','JPY','CNY']:['전체','고정','변동','기타']).filter(x=>x.includes(filterQuery)).map(opt=><label key={opt}><input type="checkbox" checked={(pending.choices||[]).includes(opt)} onChange={e=>setPending(v=>({...v,type:'choices',choices:e.target.checked?[...(v.choices||[]),opt]:(v.choices||[]).filter(x=>x!==opt)}))}/>{opt}</label>)}</div></>:
       <><div className="range-label">수치 범위</div><div className="range-inputs"><input type="number" placeholder="최소값" value={pending.min||''} onChange={e=>setPending(v=>({...v,min:e.target.value,type:'range'}))}/><span>—</span><input type="number" placeholder="최대값" value={pending.max||''} onChange={e=>setPending(v=>({...v,max:e.target.value,type:'range'}))}/></div></>}
       <div className="filter-edit-actions"><button onClick={()=>{changeState(()=>setPills(v=>{const n={...v};delete n[popup.slice(7)];return n}));setPopup('')}}>리셋</button><button className="apply-btn" onClick={()=>applyFilter(popup.slice(7),pending)}>적용</button></div>
     </div>}
     {popup==='account'&&<div className="filter-note">공식 TradingView 서비스가 아닌 내부 프로젝트용 UI입니다.</div>}
   </div>}
   {toast&&<div role="status" className="toast">{toast}</div>}
 </div>;
}
export default App;
