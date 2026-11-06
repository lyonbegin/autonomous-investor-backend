import {useCallback,useEffect,useMemo,useRef,useState} from 'react';
import './screener.css';

type Kind='stock'|'etf'|'bond'|'coin'|'cex'|'dex';
type Column={key:string;title:string;numeric?:boolean};
type Entry={s:string;d:unknown[]};
type NetworkResult={totalCount:number;data:Entry[]};
type Filter={id:string;label:string;type:'range'|'choice'|'date';values?:string[];value?:string};
const MARKETS=[
['america','미국'],['korea','한국'],['japan','일본'],['china','중국'],['hongkong','홍콩'],['india','인도'],['uk','영국'],['germany','독일'],['france','프랑스'],['canada','캐나다'],
['australia','호주'],['taiwan','대만'],['brazil','브라질'],['singapore','싱가포르'],['vietnam','베트남'],['thailand','태국'],['austria','오스트리아'],['bahrain','바레인'],['bangladesh','방글라데시'],['belgium','벨기에'],['bulgaria','불가리아'],['chile','칠레'],['colombia','콜롬비아'],['croatia','크로아티아'],['cyprus','키프로스'],['czech','체코'],['denmark','덴마크'],['egypt','이집트'],['estonia','에스토니아'],['finland','핀란드'],['greece','그리스'],['hungary','헝가리'],['iceland','아이슬란드'],['indonesia','인도네시아'],['ireland','아일랜드'],['israel','이스라엘'],['italy','이탈리아'],['kenya','케냐'],['kuwait','쿠웨이트'],['latvia','라트비아'],['lithuania','리투아니아'],['luxembourg','룩셈부르크'],['malaysia','말레이시아'],['mexico','멕시코'],['morocco','모로코'],['netherlands','네덜란드'],['newzealand','뉴질랜드'],['nigeria','나이지리아'],['norway','노르웨이'],['pakistan','파키스탄'],['peru','페루'],['philippines','필리핀'],['poland','폴란드'],['portugal','포르투갈'],['qatar','카타르'],['romania','루마니아'],['russia','러시아'],['ksa','사우디아라비아'],['serbia','세르비아'],['slovakia','슬로바키아'],['slovenia','슬로베니아'],['rsa','남아공'],['spain','스페인'],['srilanka','스리랑카'],['sweden','스웨덴'],['switzerland','스위스'],['tunisia','튀니지'],['turkey','튀르키예'],['uae','아랍에미리트'],['venezuela','베네수엘라']
] as const;
const CONFIG:Record<Kind,{name:string;group:string;market:string;columns:Column[];tabs:string[];filters:Filter[]}> = {
 stock:{name:'주식 스크리너',group:'주식',market:'korea',tabs:['오버뷰','밸류에이션','배당','수익성','손익계산서','대차대조표','현금흐름','기술 지표','실적','더보기'],
 columns:[{key:'name',title:'심볼'},{key:'description',title:'종목 이름'},{key:'close',title:'가격',numeric:true},{key:'change',title:'변동 %',numeric:true},{key:'volume',title:'거래량',numeric:true},{key:'market_cap_basic',title:'시가총액',numeric:true},{key:'price_earnings_ttm',title:'주가수익비율 (TTM)',numeric:true},{key:'earnings_per_share_diluted_ttm',title:'주당순이익 (TTM)',numeric:true},{key:'sector',title:'섹터'},{key:'exchange',title:'거래소'}],
 filters:[{id:'exchange',label:'거래소',type:'choice'},{id:'sector',label:'섹터',type:'choice',values:['Technology Services','Finance','Electronic Technology','Health Technology','Consumer Non-Durables']},{id:'market_cap_basic',label:'시가총액',type:'range'},{id:'close',label:'가격',type:'range'},{id:'change',label:'변동 %',type:'range'},{id:'volume',label:'거래량',type:'range'},{id:'price_earnings_ttm',label:'주가수익비율',type:'range'}]},
 etf:{name:'ETF 스크리너',group:'ETF',market:'america',tabs:['오버뷰','퍼포먼스','자금 흐름','NAV','보유 종목','리스크','기술 지표','더보기'],
 columns:[{key:'name',title:'심볼'},{key:'description',title:'이름'},{key:'close',title:'가격',numeric:true},{key:'change',title:'변동 %',numeric:true},{key:'volume',title:'거래량',numeric:true},{key:'total_assets_under_management',title:'운용자산',numeric:true},{key:'expense_ratio',title:'운용보수',numeric:true},{key:'exchange',title:'거래소'}],
 filters:[{id:'exchange',label:'거래소',type:'choice'},{id:'fund_type',label:'펀드 타입',type:'choice'},{id:'close',label:'가격',type:'range'},{id:'change',label:'변동 %',type:'range'},{id:'total_assets_under_management',label:'운용자산',type:'range'},{id:'expense_ratio',label:'운용보수',type:'range'}]},
 bond:{name:'본드 스크리너',group:'채권',market:'bond',tabs:['오버뷰','보안 정보','금리 위험','스프레드','금액','채권 용어','쿠폰','발행자','등급','더보기'],
 columns:[{key:'TickerUniversal',title:'심볼'},{key:'Isin',title:'ISIN'},{key:'YieldToWorst',title:'채권 최저 수익률 %',numeric:true},{key:'BondClose',title:'가격 %',numeric:true},{key:'BondCloseNet',title:'가격',numeric:true},{key:'CurrentCoupon',title:'쿠폰 %',numeric:true},{key:'MaturityDate',title:'머튜어리티 데이트'},{key:'Redemption',title:'콜/풋'},{key:'BondIssuerType',title:'발급자 유형'},{key:'SnpRatingLongTerm',title:'S&P 등급'},{key:'FitchRatingLongTerm',title:'피치 등급'},{key:'MoodysRatingLongTerm',title:'무디스 신용등급'},{key:'Source',title:'소스'}],
 filters:[{id:'BondIssuerType',label:'발급자 유형',type:'choice',values:['Corporate','Sovereign','Agency','Supranational']},{id:'BondIssuer',label:'발행자',type:'choice'},{id:'YieldToWorst',label:'채권 최저 수익률 %',type:'range'},{id:'CurrentCoupon',label:'쿠폰 %',type:'range'},{id:'CouponType',label:'쿠폰 타입',type:'choice'},{id:'CouponFrequency',label:'쿠폰 빈도',type:'choice'},{id:'MaturityDate',label:'머튜어리티 데이트',type:'date'},{id:'BondClose',label:'가격 %',type:'range'},{id:'OutstandingAmount',label:'미결제 금액',type:'range'},{id:'IssueCurrency',label:'발행 통화',type:'choice'},{id:'CouponCurrency',label:'쿠폰 통화',type:'choice'},{id:'Source',label:'소스',type:'choice',values:['BONDSCOM']}]},
 coin:{name:'크립토 코인 스크리너',group:'코인',market:'coin',tabs:['오버뷰','퍼포먼스','밸류에이션','기술 지표'],
 columns:[{key:'name',title:'심볼'},{key:'description',title:'이름'},{key:'close',title:'가격',numeric:true},{key:'change',title:'변동 %',numeric:true},{key:'volume',title:'거래량',numeric:true}],filters:[{id:'close',label:'가격',type:'range'},{id:'change',label:'변동 %',type:'range'}]},
 cex:{name:'CEX 스크리너',group:'CEX',market:'crypto',tabs:['오버뷰','퍼포먼스','기술 지표'],
 columns:[{key:'name',title:'심볼'},{key:'description',title:'이름'},{key:'close',title:'가격',numeric:true},{key:'change',title:'변동 %',numeric:true},{key:'volume',title:'거래량',numeric:true}],filters:[{id:'exchange',label:'거래소',type:'choice'},{id:'change',label:'변동 %',type:'range'}]},
 dex:{name:'DEX 스크리너',group:'DEX',market:'crypto',tabs:['오버뷰','퍼포먼스','기술 지표'],
 columns:[{key:'name',title:'심볼'},{key:'description',title:'이름'},{key:'close',title:'가격',numeric:true},{key:'change',title:'변동 %',numeric:true},{key:'volume',title:'거래량',numeric:true}],filters:[{id:'exchange',label:'거래소',type:'choice'},{id:'change',label:'변동 %',type:'range'}]}
};
const LIVE_COLUMNS:Record<'stock'|'etf'|'bond',string[]> = {
 stock:['ticker-view','close','type','typespecs','pricescale','minmov','fractional','minmove2','currency','change','volume','relative_volume_10d_calc','market_cap_basic','fundamental_currency_code','price_earnings_ttm','earnings_per_share_diluted_ttm','earnings_per_share_diluted_yoy_growth_ttm','dividends_yield_current','sector.tr','market','sector','AnalystRating','AnalystRating.tr'],
 etf:['ticker-view','close','type','typespecs','pricescale','minmov','fractional','minmove2','currency','change','Value.Traded','fundamental_currency_code','relative_volume_10d_calc','aum','nav_total_return.3Y','etf_holdings_count','expense_ratio','asset_class.tr','focus.tr'],
 bond:['ticker-view','isin-displayed','yield_to_worst','close_pct','close_net','type','typespecs','fundamental_currency_code','current_coupon','maturity_date','redemption_type.tr','bond_issuer_type.tr','bond_snp_rating_lt.tr','bond_snp_rating_lt','bond_fitch_rating_lt.tr','bond_fitch_rating_lt','bond_moodys_rating_lt.tr','bond_moodys_rating_lt','exchange.tr','source-logoid']
};
const API_FIELD_MAP:Record<string,string>={name:'ticker-view',description:'ticker-view',
 TickerUniversal:'ticker-view',Isin:'isin-displayed',YieldToWorst:'yield_to_worst',BondClose:'close_pct',
 BondCloseNet:'close_net',CurrentCoupon:'current_coupon',MaturityDate:'maturity_date',
 Redemption:'redemption_type.tr',BondIssuerType:'bond_issuer_type.tr',
 SnpRatingLongTerm:'bond_snp_rating_lt',FitchRatingLongTerm:'bond_fitch_rating_lt.tr',
 MoodysRatingLongTerm:'bond_moodys_rating_lt.tr',Source:'source-logoid',
 total_assets_under_management:'aum',volume:'volume',sector:'sector.tr',exchange:'market'};
const STOCK_TYPE_FILTER={operator:'and',operands:[{operation:{operator:'or',operands:[
 {expression:{left:'type',operation:'equal',right:'stock'}},
 {expression:{left:'type',operation:'equal',right:'dr'}},
 {expression:{left:'type',operation:'equal',right:'fund'}}
 ]}},{expression:{left:'typespecs',operation:'has_none_of',right:['pre-ipo']}}]};
const ETF_TYPE_FILTER={operator:'and',operands:[{operation:{operator:'or',operands:[
 {expression:{left:'typespecs',operation:'has',right:['etf']}},
 {expression:{left:'type',operation:'equal',right:'structured'}}
 ]}}]};

const KINDS:Kind[]=['stock','etf','bond','coin','cex','dex'];
const numberFmt=(v:unknown)=>{if(v===null||v===undefined||v==='')return '—';if(typeof v==='number'){if(Math.abs(v)>=1e12)return (v/1e12).toFixed(2)+'T';if(Math.abs(v)>=1e9)return (v/1e9).toFixed(2)+'B';if(Math.abs(v)>=1e6)return (v/1e6).toFixed(2)+'M';return v.toLocaleString('en-US',{maximumFractionDigits:3})}return String(v)};
function safeState<T>(key:string,fallback:T):T{try{const saved=localStorage.getItem(key);return saved?JSON.parse(saved) as T:fallback}catch{return fallback}}
function Icon({name}: {name:string}) {return <span aria-hidden="true" className="sc-icon">{name}</span>}
export default function ScreenerClone(){
 const initialKind=KINDS.includes(new URLSearchParams(location.search).get('screener') as Kind)?new URLSearchParams(location.search).get('screener') as Kind:'stock';
 const[kind,setKind]=useState<Kind>(initialKind);
 const[market,setMarket]=useState(CONFIG[initialKind].market);
 const[tab,setTab]=useState('오버뷰');
 const[filters,setFilters]=useState<Filter[]>(CONFIG[initialKind].filters);
 const[criteria,setCriteria]=useState<Record<string,{from:string;to:string;choice:string}>>({});
 const[activePopup,setActivePopup]=useState<string|null>(null);
 const[search,setSearch]=useState('');
 const[marketSearch,setMarketSearch]=useState('');
 const[extraSearch,setExtraSearch]=useState('');
 const[rows,setRows]=useState<Entry[]>([]);
 const[total,setTotal]=useState<number|null>(null);
 const[loading,setLoading]=useState(false);
 const[error,setError]=useState('');
 const[page,setPage]=useState(0);
 const[sort,setSort]=useState<{key:string;desc:boolean}|null>(null);
 const[columns,setColumns]=useState<Column[]>(CONFIG[initialKind].columns);
 const[fullscreen,setFullscreen]=useState(false);
 const[settingsOpen,setSettingsOpen]=useState(false);
 const[compact,setCompact]=useState(true);
 const[screenName,setScreenName]=useState('전체 '+CONFIG[initialKind].group);
 const[history,setHistory]=useState<Array<Record<string,{from:string;to:string;choice:string}>>>([]);
 const[future,setFuture]=useState<Array<Record<string,{from:string;to:string;choice:string}>>>([]);
 const[watchlist,setWatchlist]=useState<string[]>(()=>safeState('tv-clone-watchlist',[]));
 const[onlyWatch,setOnlyWatch]=useState(false);
 const[updated,setUpdated]=useState('');
 const [columnDrawer,setColumnDrawer]=useState(false);
 const timeoutRef=useRef<ReturnType<typeof setTimeout>|undefined>(undefined);
 const config=CONFIG[kind];
 const selectKind=(k:Kind)=>{setKind(k);setMarket(CONFIG[k].market);setTab('오버뷰');setColumns(CONFIG[k].columns);setFilters(CONFIG[k].filters);setCriteria({});setSort(null);setPage(0);setScreenName('전체 '+CONFIG[k].group);setRows([]);setTotal(null);setError('');setActivePopup(null);historyReplace(k)};
 function historyReplace(k:Kind){const u=new URL(location.href);u.searchParams.set('screener',k);window.history.replaceState({},'',u);}
 const updateCriteria=(id:string,part:Partial<{from:string;to:string;choice:string}>)=>{
   setHistory(h=>[...h.slice(-19),criteria]);setFuture([]);
   setCriteria(c=>({...c,[id]:{from:c[id]?.from||'',to:c[id]?.to||'',choice:c[id]?.choice||'',...part}}));setPage(0);
 };
 const reset=()=>{setHistory(h=>[...h.slice(-19),criteria]);setCriteria({});setPage(0);setActivePopup(null)};
 const undo=()=>{if(!history.length)return;setFuture(f=>[criteria,...f]);setCriteria(history[history.length-1]);setHistory(h=>h.slice(0,-1))};
 const redo=()=>{if(!future.length)return;setHistory(h=>[...h,criteria]);setCriteria(future[0]);setFuture(f=>f.slice(1))};
 const activeFilters=useMemo(()=>Object.entries(criteria).flatMap(([key,c])=>{const out:Array<{left:string;operation:string;right:unknown}>=[];
 if(c.choice)out.push({left:key,operation:'equal',right:c.choice});
 else if(c.from!==''&&c.to!=='')out.push({left:key,operation:'in_range',right:[Number(c.from),Number(c.to)]});
 else if(c.from!=='')out.push({left:key,operation:'egreater',right:Number(c.from)});
 else if(c.to!=='')out.push({left:key,operation:'eless',right:Number(c.to)});
 return out;
 }),[criteria]);
 const query=useCallback(async()=>{
   const known=(kind==='stock'||kind==='etf'||kind==='bond');
   const requestColumns=known?LIVE_COLUMNS[kind]:['ticker-view','close','change','volume','currency'];
   const sortBy=sort?(API_FIELD_MAP[sort.key]||sort.key):(kind==='stock'?'market_cap_basic':kind==='etf'?'aum':kind==='bond'?'bond_snp_rating_lt':'volume');
   const body:Record<string,unknown>={
     columns:requestColumns,
     filter:kind==='stock'?[{left:'is_primary',operation:'equal',right:true},...activeFilters]:activeFilters,
     ignore_unknown_fields:false,options:{lang:'ko'},range:[page*50,page*50+50],
     sort:{sortBy,sortOrder:sort?(sort.desc?'desc':'asc'):'desc'},
     markets:[market]
   };
   if(kind==='stock')body.filter2=STOCK_TYPE_FILTER;
   if(kind==='etf')body.filter2=ETF_TYPE_FILTER;
   setLoading(true);setError('');
   try{
     const ctl=new AbortController();const timer=setTimeout(()=>ctl.abort(),20000);
     const res=await fetch('/screener-data/'+encodeURIComponent(market)+'/scan?label-product=screener-'+kind,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:ctl.signal});
     clearTimeout(timer);
     const payload:NetworkResult=await res.json();
     if(!res.ok)throw new Error('HTTP '+res.status+' '+JSON.stringify(payload).slice(0,220));
     if(!Array.isArray(payload.data)||typeof payload.totalCount!=='number')throw new Error('스크리너 응답 구조가 일치하지 않습니다');
     setRows(payload.data);setTotal(payload.totalCount);setUpdated(new Date().toLocaleTimeString('ko-KR'));
   }catch(e){setRows([]);setTotal(null);setError('실제 시장 데이터 조회 실패 · '+String(e))}
   finally{setLoading(false)}
 },[kind,market,page,sort,activeFilters]);
 useEffect(()=>{clearTimeout(timeoutRef.current);timeoutRef.current=setTimeout(()=>void query(),160);return()=>clearTimeout(timeoutRef.current)},[query]);
 useEffect(()=>{localStorage.setItem('tv-clone-watchlist',JSON.stringify(watchlist))},[watchlist]);
 const filteredRows=useMemo(()=>rows.filter(r=>(!search||(r.s+' '+r.d.join(' ')).toLowerCase().includes(search.toLowerCase()))&&(!onlyWatch||watchlist.includes(r.s))),[rows,search,onlyWatch,watchlist]);
 const colIndex=(id:string)=>{const fields=(kind==='stock'||kind==='etf'||kind==='bond')?LIVE_COLUMNS[kind]:['ticker-view','close','change','volume','currency'];return fields.indexOf(API_FIELD_MAP[id]||id)};
 const cell=(row:Entry,col:Column)=>{const v=row.d[colIndex(col.key)];if(col.key==='name'||col.key==='TickerUniversal')return (v&&typeof v==='object'&&!Array.isArray(v)&&'name' in v)?String(v.name):row.s;if(col.key==='description')return v&&typeof v==='object'&&!Array.isArray(v)&&'description' in v?String(v.description):'—';if(col.key==='volume'&&kind==='etf')return row.d[10];return v};
 const addFilter=(id:string)=>{const found=config.filters.find(f=>f.id===id);if(found&&!filters.find(f=>f.id===id))setFilters(p=>[...p,found]);setActivePopup(id)};
 const download=()=>{const lines=[columns.map(c=>c.title),...filteredRows.map(r=>columns.map(c=>String(cell(r,c)??'')))];const csv=lines.map(line=>line.map(v=>'"'+v.replaceAll('"','""')+'"').join(',')).join('\r\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8'}));a.download='screener-'+kind+'-'+market+'.csv';a.click();URL.revokeObjectURL(a.href)};
 const chooseTab=(name:string)=>{setTab(name);setPage(0);if(name==='오버뷰'){setColumns(config.columns);return}const extras:Record<string,string[]>={'등급':['SnpRatingLongTerm','FitchRatingLongTerm','MoodysRatingLongTerm'],'쿠폰':['CurrentCoupon','CouponType','CouponFrequency'],'금리 위험':['YieldToWorst','ModifiedDuration'],'발행자':['BondIssuerType','BondIssuer'],'밸류에이션':['price_earnings_ttm','price_book_fq'],'배당':['dividends_yield_current','dividends_per_share_fq'],'기술 지표':['RSI','Mom','Recommend.All']};
 const available=extras[name];if(available){setColumns([config.columns[0],...available.map(key=>config.columns.find(c=>c.key===key)||{key,title:key})])}
 };
 return <div className={'sc-app'+(fullscreen?' sc-fullscreen':'')} data-testid="screener-app">
 <header className="sc-global"><div className="sc-brand">▥ <b>Markets</b></div><nav aria-label="스크리너 종류">{KINDS.map(k=><button key={k} className={'sc-global-link '+(kind===k?'on':'')} onClick={()=>selectKind(k)}>{CONFIG[k].group}</button>)}</nav><div className="sc-global-end">시장 스크리너 <Icon name="⌄"/></div></header>
 <main className="sc-main">
 <div className="sc-topline"><div className="sc-type-switch"><button aria-label="스크리너 종류 선택" data-testid="screener-type-selector" onClick={()=>setActivePopup(activePopup==='types'?null:'types')}><h1>{config.name}</h1><Icon name="⌄"/></button>
 {activePopup==='types'&&<div className="sc-pop sc-type-pop">{KINDS.map(k=><button key={k} onClick={()=>selectKind(k)}>{CONFIG[k].name}</button>)}</div>}</div></div>
 <div className="sc-toolbar"><div className="sc-menu-wrap"><button className="sc-screenname" onClick={()=>setActivePopup(activePopup==='screens'?null:'screens')} data-testid="screen-title"><b>{screenName}</b> ⌄</button>{activePopup==='screens'&&<div className="sc-pop sc-type-pop"><button onClick={()=>{setScreenName('전체 '+config.group);reset();setActivePopup(null)}}>전체 {config.group}</button><button onClick={()=>{setScreenName('내 왓치리스트');setOnlyWatch(true);setActivePopup(null)}}>내 왓치리스트</button></div>}</div><span className="sc-unsaved">저장</span><div className="sc-spacer"/><button title="실행 취소" onClick={undo} disabled={!history.length}>↶</button><button title="다시 실행" onClick={redo} disabled={!future.length}>↷</button><button title="스크리너 세팅" onClick={()=>setSettingsOpen(!settingsOpen)} data-testid="screener-settings">⚙</button></div>
 {settingsOpen&&<div className="sc-settings"><b>스크리너 세팅</b><label><input type="checkbox" checked={compact} onChange={e=>setCompact(e.target.checked)}/> 컴팩트 행</label><label><input type="checkbox" checked={onlyWatch} onChange={e=>setOnlyWatch(e.target.checked)}/> 왓치리스트만 표시</label><button onClick={()=>setSettingsOpen(false)}>닫기</button></div>}
 <section className="sc-filters" aria-label="스크리너 필터">
 <div className="sc-filter-first sc-relative"><button className="sc-pill" onClick={()=>setActivePopup(activePopup==='watch'?null:'watch')} data-testid="watchlist-filter">왓치리스트 <Icon name="⌄"/></button>{activePopup==='watch'&&<div className="sc-pop"><label><input type="checkbox" checked={onlyWatch} onChange={e=>setOnlyWatch(e.target.checked)}/> 내 왓치리스트만</label><div className="sc-muted">현재 {watchlist.length}개 저장</div></div>}</div>
 {isAsset&&<div className="sc-relative"><button className={'sc-pill'+(market!==config.market?' activated':'')} onClick={()=>setActivePopup(activePopup==='market'?null:'market')} data-testid="market-filter">{MARKETS.find(m=>m[0]===market)?.[1]||market} <Icon name="⌄"/></button>{activePopup==='market'&&<div className="sc-pop sc-market-pop"><div className="sc-pop-heading">시장 선택</div><input aria-label="시장 검색" placeholder="시장 검색" value={marketSearch} onChange={e=>setMarketSearch(e.target.value)}/><div className="sc-market-list">{MARKETS.filter(m=>m[1].includes(marketSearch)||m[0].includes(marketSearch.toLowerCase())).map(([code,label])=><button data-testid={'market-'+code} key={code} className={market===code?'chosen':''} onClick={()=>{setMarket(code);setPage(0);setRows([]);setMarketSearch('');setActivePopup(null)}}>{market===code?'✓ ':'　'}{label} <small>{code}</small></button>)}</div></div>}</div>}
 {filters.map(f=><div className="sc-relative" key={f.id}><button data-testid={'filter-'+f.id} className={'sc-pill'+((criteria[f.id]?.from||criteria[f.id]?.to||criteria[f.id]?.choice)?' activated':'')} onClick={()=>setActivePopup(activePopup===f.id?null:f.id)}>{f.label}{criteria[f.id]?.choice?' · '+criteria[f.id].choice:''} <Icon name="⌄"/></button>{activePopup===f.id&&<div className="sc-pop sc-filter-pop"><div className="sc-pop-heading">{f.label}</div>{f.type==='choice'?<><input placeholder="값 입력 또는 선택" value={criteria[f.id]?.choice||''} onChange={e=>updateCriteria(f.id,{choice:e.target.value})}/>{(f.values||[]).map(v=><button key={v} className="sc-choice" onClick={()=>{updateCriteria(f.id,{choice:v});setActivePopup(null)}}>{v}</button>)}</>:<div className="sc-range"><label>최소<input aria-label={f.label+' 최소'} type={f.type==='date'?'date':'number'} value={criteria[f.id]?.from||''} onChange={e=>updateCriteria(f.id,{from:e.target.value})}/></label><label>최대<input aria-label={f.label+' 최대'} type={f.type==='date'?'date':'number'} value={criteria[f.id]?.to||''} onChange={e=>updateCriteria(f.id,{to:e.target.value})}/></label></div>}<div className="sc-filter-actions"><button onClick={()=>{updateCriteria(f.id,{from:'',to:'',choice:''});setActivePopup(null)}}>초기화</button><button onClick={()=>setActivePopup(null)}>적용</button></div></div>}</div>)}
 <div className="sc-relative"><button title="새 필터 넣기" data-testid="add-filter" className="sc-square" onClick={()=>setActivePopup(activePopup==='add'?null:'add')}>＋</button>{activePopup==='add'&&<div className="sc-pop sc-market-pop"><div className="sc-pop-heading">필터 추가</div><input placeholder="필터 검색" value={extraSearch} onChange={e=>setExtraSearch(e.target.value)}/><div className="sc-market-list">{config.filters.filter(f=>!filters.find(ff=>ff.id===f.id)&&f.label.includes(extraSearch)).map(f=><button key={f.id} onClick={()=>addFilter(f.id)}>{f.label}</button>)}</div></div>}</div><button title="필터 초기화" className="sc-square" data-testid="reset-filters" onClick={reset}>•••</button></section>
 <div className="sc-tabs"><div role="tablist" className="sc-tabs-scroll">{config.tabs.map(t=><button key={t} role="tab" aria-selected={tab===t} className={tab===t?'sc-selected':''} onClick={()=>chooseTab(t)}>{t}</button>)}</div><div className="sc-tabs-actions"><button title="리프레쉬" data-testid="refresh-screener" onClick={()=>void query()}>↻</button><button title="최대화" onClick={()=>setFullscreen(!fullscreen)}>{fullscreen?'⤢':'⤡'}</button><button title="CSV 내보내기" onClick={download}>↓</button></div></div>
 <div className="sc-table-top"><div className="sc-count">{total===null?'조회 대기':total.toLocaleString('ko-KR')+' 매칭'} <span>{loading?'조회 중…':updated?'업데이트 '+updated:''}</span></div><div className="sc-spacer"/><label className="sc-table-search">⌕ <input placeholder="현재 페이지 검색" aria-label="심볼 검색" value={search} onChange={e=>setSearch(e.target.value)}/></label><button className="sc-colbtn" onClick={()=>setColumnDrawer(!columnDrawer)} data-testid="columns-setup">＋ 컬럼</button></div>
 {columnDrawer&&<div className="sc-column-panel"><b>컬럼 셋업</b><button onClick={()=>setColumnDrawer(false)}>✕</button><div>{config.columns.map(c=><label key={c.key}><input type="checkbox" checked={columns.some(x=>x.key===c.key)} disabled={c.key===config.columns[0].key} onChange={e=>setColumns(cs=>e.target.checked?[...cs,c]:cs.filter(x=>x.key!==c.key))}/>{c.title}</label>)}</div></div>}
 {error&&<div role="alert" className="sc-error">{error} <button onClick={()=>void query()}>다시 조회</button></div>}
 <section className="sc-table-scroll" aria-label="검색 결과"><table className={'sc-table '+(compact?'compact':'')}><thead><tr>{columns.map((c,i)=><th key={c.key} className={(i===0?'sc-sticky ':'')+(c.numeric?'sc-right':'')}><button onClick={()=>{setSort(s=>s?.key===c.key?{key:c.key,desc:!s.desc}:{key:c.key,desc:true});setPage(0)}} title={c.title+' 정렬'}>{c.title} <small>{sort?.key===c.key?(sort.desc?'↓':'↑'):''}</small></button></th>)}</tr></thead><tbody>{filteredRows.map((r,i)=><tr key={r.s+'-'+i}>{columns.map((c,j)=>{const v=cell(r,c);return <td key={c.key} className={(j===0?'sc-sticky ':'')+(c.numeric?'sc-right':'')}>{j===0?<div className="sc-ticker"><button className={'sc-star '+(watchlist.includes(r.s)?'saved':'')} title="왓치리스트 저장" onClick={()=>setWatchlist(w=>w.includes(r.s)?w.filter(x=>x!==r.s):[...w,r.s])}>{watchlist.includes(r.s)?'★':'☆'}</button><a target="_blank" rel="noreferrer" href={'https://kr.tradingview.com/symbols/'+encodeURIComponent(r.s.replace(':','-'))+'/'}>{String(v||r.s)}</a></div>:<span className={c.key==='change'&&typeof v==='number'?(v>0?'sc-up':v<0?'sc-down':''):''}>{numberFmt(v)}</span>}</td>})}</tr>)}{!loading&&!error&&filteredRows.length===0&&<tr><td colSpan={columns.length} className="sc-empty">조회 결과가 없습니다. 시장·필터를 변경해 보세요.</td></tr>}</tbody></table></section>
 <footer className="sc-footer"><div>{total===null?'—':(page*50+1).toLocaleString()+'–'+Math.min(total,(page+1)*50).toLocaleString()+' / '+total.toLocaleString() } <span>· 응답에서 확인된 종목만 표시</span></div><div><button data-testid="prev-page" disabled={page===0||loading} onClick={()=>setPage(p=>Math.max(0,p-1))}>‹</button><span>{page+1} 페이지</span><button data-testid="next-page" disabled={loading||total===null||(page+1)*50>=total} onClick={()=>setPage(p=>p+1)}>›</button></div></footer>
 </main></div>;
}
