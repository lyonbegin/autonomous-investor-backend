/* Source-derived widget routing from the user-provided 2026-11-05
 * TradingView Markets HTML. One HTML snapshot cannot prove all site symbols.
 * No historical price values are embedded or claimed current.
 */
"use strict";
(() => {
 const raw = [
 "indices|indices-market-summary|지수 시황|/markets/indices/quotes-all/|KRX-KOSPI,KRX-KOSPI50,KRX-KOSPI200,KRX-KOSPI2,KRX-KOSPI3,KRX-KOSPI4,KRX-KOSDAQ,KRX-KOSDAQ150,KRX-KRXSECTOR4,KRX-KRXSECTOR6,KRX-KRXSECTOR3",
 "indices|indices-major-world|전세계 인덱스|/markets/indices/quotes-major/|SPX,NASDAQ-NDX,DJ-DJI,TVC-NI225,FTSE-UKX,XETR-DAX,EURONEXT-PX1,TVC-FTMIB,BME-IBC,SSE-000001,HSI-HSI,NSE-NIFTY",
 "stocks|stocks-market-summary|한국 주식 시황|/markets/stocks-korea/market-movers-all-stocks/|KRX-005930,KRX-000660,KRX-005380,KRX-051910,KRX-207940,KRX-017670,KRX-005490,KRX-000270,KRX-035420,KRX-012330,KRX-066570",
 "stocks|stocks-community-trends|커뮤니티 트렌드||KRX-005930,KRX-035720,KRX-035420,KRX-009150,KRX-042700,KRX-068270,KRX-005380,KRX-326030,KRX-000660,KRX-079550",
 "stocks|stocks-volume-leaders|거래량이 가장 많은 주식|/markets/stocks-korea/market-movers-active/|KRX-008830,KRX-0013Y0,KRX-282720,KRX-495910,KRX-109610,KRX-199820",
 "stocks|market-movers-volatile-volume|가장 변동성이 높은 주식|/markets/stocks-korea/market-movers-most-volatile/|KRX-420610,KRX-0147B0,KRX-142760,KRX-495910,KRX-270520,KRX-390110",
 "stocks|stocks-gainers|상승 주식|/markets/stocks-korea/market-movers-gainers/|KRX-0013Y0,KRX-335870,KRX-004540,KRX-020400,KRX-354200,KRX-128540",
 "stocks|stocks-losers|하락 주식|/markets/stocks-korea/market-movers-losers/|KRX-495910,KRX-179530,KRX-192410,KRX-129920,KRX-004710,KRX-270520",
 "stocks|stocks-upcoming-earnings|실적 캘린더||KRX-018290,KRX-079550,KRX-082740,KRX-089600,KRX-092870,KRX-094170",
 "stocks|stocks-ipo-calendar|IPO 캘린더||KRX-359410,KRX-0147B0,KRX-471800,KRX-495910,KRX-0162D0,KRX-952366",
 "world-stocks|world-stocks-market-summary|세계 주식 시황||NASDAQ-MSFT,TADAWUL-2222,TWSE-2330,EURONEXT-MC,HKEX-700,KRX-005930",
 "world-stocks|world-stocks-biggest-companies|세계 최대 기업|/markets/world-stocks/worlds-largest-companies/|NASDAQ-AAPL,NASDAQ-NVDA,NASDAQ-MSFT,NASDAQ-GOOGL,NASDAQ-AMZN,TWSE-2330",
 "world-stocks|world-stocks-largest-employers|세계 최대 고용주|/markets/world-stocks/worlds-largest-employers/|NASDAQ-WMT,NASDAQ-AMZN,SZSE-002594,NYSE-ACN,NASDAQ-JD,HKEX-2618",
 "world-stocks|world-stocks-upcoming-earnings|실적 캘린더||TSE-3034,TSE-4452,TSE-6941,TSE-6976,TSE-9001,TSE-9722",
 "world-stocks|world-stocks-ipo-calendar|IPO 캘린더||TSE-656A,BSE-AJWA,BSE-CRL,BSE-MKJEWELS,TSE-655A,TSE-658A",
 "crypto|crypto-market-summary|크립토 시황||BTCUSD,ETHUSD,USDTUSD,BNBUSD,USDCUSD,XRPUSD",
 "crypto|crypto-community-trends|커뮤니티 트렌드||ELSAUSDT.P,JCTUSDT.P,INJUSDT,TRUMPUSDT,BCHUSDT,AKEUSDT.P,CLANKERUSDT.P,DOTUSDT,XAUUSDT.P,BTC.D",
 "crypto|hotlist-coin-market-cap-rank|암호화폐 시가총액 랭킹|/markets/cryptocurrencies/prices-all/|BTCUSD,ETHUSD,USDTUSD,BNBUSD,XRPUSD,USDCUSD",
 "crypto|hotlist-coin-defi|TVL 랭킹|/markets/cryptocurrencies/prices-highest-total-value-locked/|AAVEUSD,LDOUSD,ENAUSD,UNIUSD,BABYLUSD,MONADUSD",
 "crypto|hotlist-coin-gainers|크립토 승자|/markets/cryptocurrencies/prices-gainers/|CAP7USD,FLUID3USD,PIEVERSEUSD,INJUSD,BEAM2USD,XAUTUSD",
 "crypto|hotlist-coin-losers|크립토 패자|/markets/cryptocurrencies/prices-losers/|TRUMPOFUSD,GRASS2USD,CASHCATUSD,PONS2USD,ETHFIUSD,VVVUSD",
 "futures|futures-market-summary|선물 시황|/markets/futures/quotes-all/|KRX-KGD1!",
 "futures|futures-energy|에너지 선물|/markets/futures/quotes-energy/|NYMEX-CL1!,NYMEX-NG1!,ICEEUR-BRN1!,NYMEX-RB1!,NYMEX-HO1!,NYMEX-AEZ1!",
 "futures|futures-agricultural|농산물 선물|/markets/futures/quotes-agricultural/|ICEUS-KC1!,ICEUS-CT1!,CBOT-ZS1!,CBOT-ZW1!,ICEUS-SB1!,CBOT-ZC1!",
 "futures|futures-metals|금속 선물|/markets/futures/quotes-metals/|COMEX-GC1!,COMEX-SI1!,NYMEX-PL1!,COMEX-HG1!,NYMEX-PA1!,KRX-KGD1!",
 "futures|futures-index|지수 선물|/markets/futures/quotes-world-indices/|KRX-K2I1!,KRX-KQI1!,KRX-MKI1!,KRX-VKI1!,KRX-QGI1!,KRX-XI31!",
 "forex|forex-market-summary|외환 시황||USDKRW,EURKRW,JPYKRW,GBPKRW,CHFKRW,AUDKRW",
 "forex|hotlist-forex-majors|주요 외환쌍|/markets/currencies/rates-major/|EURUSD,USDJPY,GBPUSD,AUDUSD,USDCAD,USDCHF",
 "forex|hotlist-forex-indices|통화 지수|/markets/currencies/indices-all/|TVC-DXY,TVC-EXY,TVC-JXY,TVC-BXY,TVC-SXY,TVC-CXY",
 "bonds|yield-curve|수익률 곡선|/markets/bonds/yield-curve-all/|",
 "bonds|bonds-kr|대한민국 채권|/markets/bonds/prices-asia/|TVC-KR01Y,TVC-KR02Y,TVC-KR03Y,TVC-KR05Y,TVC-KR10Y,TVC-KR30Y",
 "bonds|major-test|주요 10년물 채권|/markets/bonds/prices-major/|TVC-KR10Y,TVC-US10Y,TVC-EU10Y,TVC-GB10Y,TVC-DE10Y,TVC-FR10Y",
 "corporate-bonds|trend-bonds-symbols|회사채 트렌드|/markets/corporate-bonds/rates-highest-yield/|SWB-US71654QDD16,FINRA-PEMX5055132,FINRA-GUGG5923941,SWB-US71654QCC42,SWB-PXTH,DUS-US71654QBR2,FWB-USU7010QAY8,FWB-USU7010QAX0,MUN-US71654QBX9,FINRA-ORCL5902732,FINRA-ORCL6186140",
 "corporate-bonds|short-term|단기|/markets/corporate-bonds/rates-short-term/|FINRA-TM6075399,FINRA-DTE6070263,FINRA-RABO6081066,FINRA-C6083617,BONDSCOM-US90327QD974,FINRA-HBLM6369868",
 "corporate-bonds|long-term|장기|/markets/corporate-bonds/rates-long-term/|DUS-US655844CJ5,SWB-NFSE,DUS-US13645RAX2,DUS-ELEN,FINRA-CMI3671567,FINRA-C3715810",
 "corporate-bonds|floating-rate|변동금리|/markets/corporate-bonds/rates-floating-rate/|FINRA-MET.IS,FINRA-CS5501682,FWB-US225401BB3,FINRA-BNS5491221,SWB-US29250NBT19,FWB-XS285296650",
 "corporate-bonds|fixed-rate|고정 금리|/markets/corporate-bonds/rates-fixed-coupon/|FINRA-VLO.IF,FINRA-MO.HH,FINRA-PEMX5666477,FINRA-F.GU,FINRA-MO.HA,FINRA-ACE.GD",
 "etfs|etfs-market-summary|ETF 시황||AMEX-SPY,NASDAQ-IBIT,AMEX-VTI,NASDAQ-QQQ,TSE-1306,TSE-1305",
 "etfs|trend-symbols|커뮤니티 트렌드||NASDAQ-SOXX,NASDAQ-SMH,NASDAQ-APPX,AMEX-GDX,AMEX-SOXS,AMEX-SOXL,AMEX-KWEB,CBOE-DRAM,AMEX-XLF,CBOE-BRZD",
 "etfs|most-traded|가장 많이 거래된|/markets/etfs/funds-most-traded/|AMEX-SPY,NASDAQ-QQQ,AMEX-SOXL,AMEX-SOXS,AMEX-IWM,NASDAQ-SOXX",
 "etfs|highest-aum-growth|가장 높은 AUM 성장률|/markets/etfs/funds-highest-aum-growth/|AMEX-RINK,ASX-VBND,ASX-VAF,ASX-VACF,ASX-VIF,ASX-VGB",
 "etfs|highest-return|최고 수익률|/markets/etfs/funds-highest-returns/|NASDAQ-MUU,HKEX-7747,KRX-395270,KRX-139260,AMEX-USO,TWSE-00685L",
 "etfs|highest-dividends|가장 높은 배당 수익률|/markets/etfs/funds-highest-yield/|AMEX-MSTY,AMEX-SMCY,AMEX-CONY,AMEX-HOOY,CBOE-HOOW,AMEX-GDXY",
 "economy|world-economy-market-summary|경제 지표 시황||ECONOMICS-KRGDP,ECONOMICS-KRFYGDPG,ECONOMICS-KRGDPCP,ECONOMICS-KRINTR,ECONOMICS-KRIRYY,ECONOMICS-KRUR",
 "economy|economic-indicators-heatmap|경제 지표 히트맵|/markets/world-economy/indicators-heatmap/|",
 "economy|global-inflation-map|글로벌 인플레이션 맵|/markets/world-economy/charts-global-trends/|",
 "economy|economic-calendar|경제 캘린더||"
 ];
 const layout=[
 ["indices","지수","대표 지수와 전세계 인덱스","indices","/markets/indices/"],
 ["stocks","한국 주식","거래량, 변동성, 상승·하락, 실적·IPO","korea","/markets/stocks-korea/"],
 ["world-stocks","세계 주식","글로벌 대형 기업과 기업 일정","global-stocks","/markets/world-stocks/"],
 ["crypto","크립토","시가총액, DeFi, 상승·하락","crypto-coins","/markets/cryptocurrencies/"],
 ["futures","선물 및 원자재","에너지, 농산물, 금속, 지수","futures","/markets/futures/"],
 ["forex","외환 및 통화","환율, 통화 지수","forex","/markets/currencies/"],
 ["bonds","국채","국채 수익률 곡선, 만기별 채권","bonds","/markets/bonds/"],
 ["corporate-bonds","회사채","단기, 장기, 변동·고정금리","corporate-bonds","/markets/corporate-bonds/"],
 ["etfs","ETFs","거래량, AUM, 수익률, 배당","etf","/markets/etfs/"],
 ["economy","경제","지표, 히트맵, 인플레이션, 캘린더",null,"/markets/world-economy/"]
 ];
 const groups=layout.map(([id,title,subtitle,scanner,href])=>({
  id,title,subtitle,scanner,href,widgets:raw.filter(s=>s.startsWith(id+"|")).map(x=>{
   const [section,key,title,href,codes]=x.split("|");
   return {id:key,section,title,href,
    symbols:codes?codes.split(","):[],
    kind:/summary/.test(key)?"summary":/calendar/.test(key)?"calendar":
         /heatmap/.test(key)?"heatmap":/inflation-map/.test(key)?"map":
         key==="yield-curve"?"curve":"ranking"};
  })
 }));
 const symbolNames={
  "KRX-KOSPI":"KOSPI","KRX-KOSPI200":"KOSPI 200","KRX-KOSDAQ":"KOSDAQ",
  "KRX-005930":"삼성전자","KRX-000660":"SK하이닉스",
  "KRX-005380":"현대자동차","KRX-035420":"NAVER",
  "NASDAQ-AAPL":"Apple","NASDAQ-NVDA":"NVIDIA","NASDAQ-MSFT":"Microsoft",
  "NASDAQ-AMZN":"Amazon","NASDAQ-GOOGL":"Alphabet",
  "TWSE-2330":"TSMC","HKEX-700":"Tencent",
  "BTCUSD":"Bitcoin","ETHUSD":"Ethereum","USDTUSD":"Tether",
  "BNBUSD":"BNB","XRPUSD":"XRP",
  "NYMEX-CL1!":"WTI 원유","NYMEX-NG1!":"천연가스",
  "COMEX-GC1!":"금","COMEX-SI1!":"은",
  "USDKRW":"USD/KRW","EURKRW":"EUR/KRW",
  "TVC-KR10Y":"한국 10년물 국채","TVC-US10Y":"미국 10년물 국채",
  "AMEX-SPY":"SPY ETF","NASDAQ-QQQ":"QQQ ETF",
  "ECONOMICS-KRGDP":"한국 GDP","ECONOMICS-KRINTR":"한국 금리",
  "ECONOMICS-KRIRYY":"한국 물가상승률","ECONOMICS-KRUR":"한국 실업률"
 };
 // Exchange suffixes are taken from actual ?exchange= query parameters
 // of the user's original TradingView HTML links; NOT guessed providers.
 const rawExchanges={
  SP:["SPX"],
  CRYPTO:["BTCUSD","ETHUSD","USDTUSD","BNBUSD","USDCUSD","XRPUSD",
   "AAVEUSD","LDOUSD","ENAUSD","UNIUSD","BABYLUSD","MONADUSD",
   "CAP7USD","FLUID3USD","PIEVERSEUSD","INJUSD","BEAM2USD","XAUTUSD",
   "TRUMPOFUSD","GRASS2USD","CASHCATUSD","PONS2USD","ETHFIUSD","VVVUSD"],
  BINANCE:["ELSAUSDT.P","JCTUSDT.P","INJUSDT","TRUMPUSDT","BCHUSDT",
   "AKEUSDT.P","CLANKERUSDT.P","DOTUSDT","XAUUSDT.P"],
  CRYPTOCAP:["BTC.D"],
  FX_IDC:["USDKRW","EURKRW","JPYKRW","GBPKRW","CHFKRW","AUDKRW",
   "EURUSD","USDJPY","GBPUSD","AUDUSD","USDCAD","USDCHF"]
 };
 const actualExchange=new Map(Object.entries(rawExchanges).flatMap(([ex,list])=>
  list.map(symbol=>[symbol,ex])));
 window.TVMarketSource={groups,symbolNames,referenceDate:"2026-11-05",
  counts:{markets:groups.length,widgets:groups.reduce((a,g)=>a+g.widgets.length,0)},
  symbol(code){return code.includes("-")?code.replace("-",":"):
   actualExchange.has(code)?actualExchange.get(code)+":"+code:null;},
  name(code){return window.TVSourceNames?.[code]||symbolNames[code]||code.split("-").slice(1).join("-")||code;}
 };
})();
