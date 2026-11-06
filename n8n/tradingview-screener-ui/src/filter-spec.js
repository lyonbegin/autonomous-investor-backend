// Executable screener filter definitions. IDs are scanner field IDs, not translated labels.
// Multiselect values come from TradingView's enum/ordered response. Never substitute display labels.
// Each of these exact scanner IDs was checked against the real provider for
// stock, ETF, coin, CEX, and DEX on 2026-11-06: HTTP 200 (9 fields x 5 markets).
// Numeric threshold is supported; original multi-parameter dialogs are not claimed.
export const TECHNICAL_FILTERS={
 '상대강도지수':['RSI','number'],
 '모멘텀':['Mom','number'],
 '오썸 오실레이터':['AO','number'],
 '커모디티 채널 인덱스':['CCI20','number'],
 '스토캐스틱':['Stoch.K','number'],
 '이동평균 수렴 발산':['MACD.macd','number'],
 '평균방향성지수':['ADX','number'],
 '평균 트루레인지':['ATR','number'],
 '단순 이동 평균':['SMA50','number']
};
export const FILTER_DEFS={
 stock:{
 ...TECHNICAL_FILTERS,
 '지수':['index','enum','index'],'가격':['close','number'],'체인지 %':['change','number'],
 '시가총액':['market_cap_basic','number'],'P/E':['price_earnings_ttm','number'],
 'EPS 희석 성장':['earnings_per_share_diluted_yoy_growth_ttm','number'],
 '배당 수익 %':['dividends_yield_current','number'],'섹터':['sector','enum','sector'],
 '애널리스트 평점':['AnalystRating','enum','analyst_rating'],
 '퍼포먼스 %':['Perf.YTD','number'],'매출 성장률':['total_revenue_yoy_growth_ttm','number'],
 'PEG':['price_earnings_growth_ttm','number'],'ROE':['return_on_equity_fq','number'],
 '베타':['beta_1_year','number'],
 '최근 실적 발표날짜':['earnings_release_date','date'],
 '다가올 실적 발표날짜':['earnings_release_next_date','date']
 },
 etf:{
 ...TECHNICAL_FILTERS,
 '자산 클래스':['asset_class','enum','asset_class'],'포커스':['focus','enum','focus'],
 '틈새 시장':['niche','enum','niche'],'홀딩스 지역':['holdings_region','enum','holdings_region'],
 '브랜드':['brand','enum','brand'],'퍼포먼스 %':['Perf.YTD','number'],
 'NAV 총 수익률':['nav_total_return.3Y','number'],'AUM':['aum','number'],
 '운용 스타일':['actively_managed','enum','actively_managed'],
 '전략':['strategy','enum','strategy'],
 '배당 혜택':['dividend_treatment','enum','dividend_treatment'],
 '배당 수익률 % (표시됨)':['dividends_yield','number'],
 '배당 빈도':['dividends_frequency','enum','dividends_frequency'],
 '레버리지 활용':['leveraged_flag','enum','leveraged_flag'],
 '지출 비율':['expense_ratio','number'],
 'UCITS 컴포넌트':['ucits_compliant_flag','enum','ucits_compliant_flag']
 },
 bond:{
 '발급자 유형':['bond_issuer_type','enum','bond_issuer_type'],
 '발행자':['bond_issuer','enum','bond_issuer'],
 '채권 최저 수익률 %':['yield_to_worst','number'],'쿠폰 %':['current_coupon','number'],
 '쿠폰 타입':['coupon_type_current','enum','coupon_type_current'],
 '쿠폰 빈도':['coupon_frequency','enum','coupon_frequency'],
 '머튜어리티 데이트':['maturity_date','date'],'가격 %':['close_pct','number'],
 '미결제 금액':['outstanding_amount','number'],
 '발행 통화':['fundamental_currency_code','enum','fundamental_currency_code'],
 '쿠폰 통화':['coupon_currency','enum','coupon_currency'],
 '소스':['exchange','enum','exchange']
 },
 coin:{
 ...TECHNICAL_FILTERS,
 '랭크':['crypto_total_rank','number'],'시가총액':['market_cap_calc','number'],
 'FD 시가 총액':['fully_diluted_value','number'],'볼륨 / 시가총액':['24h_vol_to_market_cap','number'],
 '잔고 주소':['addresses_count','number'],'달러 표시 거래량':['24h_vol_cmc','number'],
 '볼륨 변화 %':['24h_vol_change|5','number'],
 '거래량 (USD)':['24h_vol_cmc','number'],'체인지 %':['24h_close_change|5','number'],
 '퍼포먼스 %':['Perf.1M','number'],'카테고리':['crypto_common_categories','enum','crypto_common_categories']
 },
 cex:{
 ...TECHNICAL_FILTERS,
 '거래소':['exchange','enum','exchange'],'심볼 타입':['type','enum','type'],
 '베이스 통화':['base_currency','enum','currency_id'],'쿼트 커런시':['currency','enum','currency_id'],
 '체인지 %':['24h_close_change|5','number'],'퍼포먼스 %':['Perf.1M','number'],
 '달러 표시 거래량':['24h_vol|5','number'],'볼륨 변화 %':['24h_vol_change|5','number']
 },
 dex:{
 ...TECHNICAL_FILTERS,
 '블록체인':['blockchain-id','enum','blockchain-id'],'거래소':['exchange','enum','exchange'],
 '체인지 %':['24h_close_change|5','number'],'거래':['dex_txs_count_24h','number'],
 '거래량':['dex_trading_volume_24h','number'],'유동성':['dex_total_liquidity','number'],
 'FDV':['fully_diluted_value','number'],'트레이더':['dex_txs_count_uniq_24h','number'],
 '고유 매수자':['dex_buyers_uniq_24h','number'],
 '고유 매도자':['dex_sellers_uniq_24h','number'],'퍼포먼스 %':['Perf.1M','number']
 }
};
// Verified by live scanner on 2026-11-06: spot=21005, swap=18729, futures=394.
// Upstream /enum/ordered?id=type returns {}, so these are explicit verified
// fallback values. They are not an arbitrary substitute for other enum fields.
export const VERIFIED_CEX_TYPES=[
 {id:'spot',name:'현물 (Spot)'},{id:'swap',name:'무기한 선물 (Swap)'},
 {id:'futures',name:'선물 (Futures)'}
];
export const PERIOD_CHOICES=[
 {field:'Perf.YTD',label:'올해 초부터 현재까지'},
 {field:'change',label:'1일'},{field:'Perf.W',label:'1주'},{field:'Perf.1M',label:'1달'},
 {field:'Perf.3M',label:'3달'},{field:'Perf.6M',label:'6달'},
 {field:'Perf.Y',label:'1년'},{field:'Perf.5Y',label:'5년'}];
export const NUMBER_OPERATORS=[
 {id:'in_range',label:'범위 (최소 ~ 최대)'},{id:'egreater',label:'이상 (≥)'},
 {id:'greater',label:'초과 (>)'},{id:'eless',label:'이하 (≤)'},
 {id:'less',label:'미만 (<)'},{id:'equal',label:'같음 (=)'},
 {id:'nequal',label:'같지 않음 (≠)'},{id:'not_in_range',label:'범위 밖'}];
export const ENUM_OPERATORS=[{id:'in_range',label:'포함'},{id:'not_in_range',label:'제외'}];
export const DATE_OPERATORS=NUMBER_OPERATORS;
export function specFor(product,label,extra={}){
 if(label==='왓치리스트')return {field:null,type:'watchlist',label};
 const def=FILTER_DEFS[product]?.[label];
 if(def)return {field:def[0],type:def[1],enum:def[2],label,stringSet:product==='coin'&&label==='카테고리'};
 if(extra[label]&&typeof extra[label]==='string')return {field:extra[label],type:'number',label};
 return null;
}
export function getEnumOptions(enums,category){
 const raw=enums?.[category];
 const list=Array.isArray(raw)?raw:Array.isArray(raw?.values)?raw.values:Array.isArray(raw?.items)?raw.items:[];
 return list.map(item=>typeof item==='string'?{id:item,name:item}:
  {id:String(item?.id??item?.value??''),name:String(item?.name??item?.label??item?.id??'')})
  .filter(item=>item.id!=='');
}
export function initialPending(spec,applied){
 const standard=spec?.type==='enum'?{type:'choices',operator:'in_range',choices:[]}:
  spec?.type==='date'?{type:'date',operator:'egreater',min:'',max:''}:
  {type:'range',operator:'egreater',min:'',max:''};
 return {...standard,...(applied||{}),field:applied?.field||spec?.field||''};
}
export function validatePending(spec,item){
 if(!spec||!spec.field)return '이 필터는 지원되는 데이터 필드가 확인되지 않았습니다.';
 if(spec.type==='enum')return item.choices?.length?'':'하나 이상의 선택값을 선택하세요.';
 const op=item.operator||'in_range';
 if(op==='in_range'||op==='not_in_range'){
  if(item.min===''||item.max===''||item.min===undefined||item.max===undefined)return '최소값과 최대값을 모두 입력하세요.';
  if(spec.type==='number'&&Number(item.min)>Number(item.max))return '최소값은 최대값보다 작아야 합니다.';
  if(spec.type==='date'&&item.min>item.max)return '시작일은 종료일보다 빨라야 합니다.';
  return '';
 }
 return item.min===''||item.min===undefined?'조건값을 입력하세요.':'';
}
function typedValue(spec,value){
 if(spec.type==='date')return Math.floor(new Date(value+'T00:00:00Z').getTime()/1000);
 return Number(value);
}
export function makeExpressions(product,pills,extra={}){
 const conditions=[],invalid=[];
 for(const [label,item] of Object.entries(pills||{})){
  if(!item||item.enabled===false)continue;
  const spec=specFor(product,label,extra);
  if(spec?.type==='watchlist')continue;
  const err=validatePending(spec,item);
  if(err){invalid.push({label,error:err});continue;}
  const field=item.field||spec.field,op=item.operator||'in_range';
  if(spec.type==='enum'){
   conditions.push({left:field,operation:spec.stringSet?(op==='not_in_range'?'has_none_of':'has'):op,right:item.choices});
  }else if(op==='in_range'||op==='not_in_range'){
   conditions.push({left:field,operation:op,right:[typedValue(spec,item.min),typedValue(spec,item.max)]});
  }else{
   conditions.push({left:field,operation:op,right:typedValue(spec,item.min)});
  }
 }
 return {conditions,invalid};
}
export function summaryFor(spec,item){
 if(!item||!spec||spec.type==='watchlist')return '';
 if(spec.type==='enum')return (item.choices||[]).slice(0,2).join(', ')+((item.choices||[]).length>2?' 외 '+(item.choices.length-2):'');
 if(item.operator==='in_range'||item.operator==='not_in_range')return item.min+' ~ '+item.max;
 const sign=NUMBER_OPERATORS.find(x=>x.id===item.operator)?.label||'';
 return sign+ ' '+item.min;
}
