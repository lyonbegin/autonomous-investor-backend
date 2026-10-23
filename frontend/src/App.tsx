import { useMemo, useState } from 'react';

type Tone = 'green' | 'red' | 'amber' | 'cyan' | 'purple' | 'muted';
type PageKey =
  | 'command' | 'domains' | 'investors' | 'capital' | 'portfolio' | 'risk'
  | 'trading' | 'tvstrategies' | 'factory' | 'research' | 'lab' | 'strategies' | 'performance'
  | 'memory' | 'audit' | 'system' | 'settings';

const nav: { key: PageKey; label: string; short: string }[] = [
  { key: 'command', label: '통합 관제', short: '관제' },
  { key: 'domains', label: '투자 영역', short: '영역' },
  { key: 'investors', label: '투자 에이전트', short: '에이전트' },
  { key: 'capital', label: '자본 배분', short: '자본' },
  { key: 'portfolio', label: '포트폴리오', short: '포트' },
  { key: 'risk', label: '위험 관리', short: '위험' },
  { key: 'trading', label: '실전 매매', short: '매매' },
  { key: 'tvstrategies', label: '트레이딩뷰 전략', short: 'TV' },
  { key: 'factory', label: '전략 공장', short: '전략' },
  { key: 'research', label: '시장 연구', short: '연구' },
  { key: 'lab', label: '퀀트 연구소', short: '퀀트' },
  { key: 'strategies', label: '운용 전략', short: '운용' },
  { key: 'performance', label: '성과 분석', short: '성과' },
  { key: 'memory', label: '기억 / 진화', short: '기억' },
  { key: 'audit', label: '의사결정 추적', short: '감사' },
  { key: 'system', label: '시스템 상태', short: '상태' },
  { key: 'settings', label: '설정', short: '설정' },
];

const domains = [
  ['평가자산 Growth', 14, '15.0%', '+12.4%', 'Return', '1.84'],
  ['Defensive Value', 11, '10.0%', '+7.3%', 'Defensive', '1.39'],
  ['Market Neutral', 13, '14.0%', '+8.1%', 'Hedge Beta', '2.01'],
  ['CTA / Futures', 15, '15.0%', '+10.8%', 'Trend', '1.73'],
  ['FX Macro', 12, '10.0%', '+5.8%', 'Macro', '1.22'],
  ['Rates', 10, '9.0%', '+4.2%', 'Risk-Off', '1.17'],
  ['Commodities', 11, '8.0%', '+6.9%', 'Inflation', '1.51'],
  ['Volatility', 10, '7.0%', '+3.8%', 'Convexity', '1.04'],
  ['Crisis Hedge', 10, '7.0%', '-1.2%', 'Tail Hedge', '0.22'],
  ['Relative Value', 12, '5.0%', '+4.1%', 'Diversifier', '1.11'],
];

const investors = [
  ['A-043', '평가자산 Growth', '₩105M', '+21.4%', '2.14', '-4.1%', '7', 'SCALE'],
  ['A-017', 'Market Neutral', '₩82M', '+18.8%', '1.92', '-3.8%', '5', 'LIVE'],
  ['A-102', 'CTA / Futures', '₩63M', '+14.7%', '1.81', '-5.2%', '9', 'LIVE'],
  ['A-055', '평가자산 Growth', '₩48M', '+11.2%', '1.62', '-4.7%', '6', 'LIVE'],
  ['A-071', 'FX Macro', '₩10M', '-6.2%', '-0.20', '-11.4%', '4', 'CUT'],
];

const strategies = [
  ['L-101', 'TV-021', '10m', 'v1.4', 'A-043', '18%', '+18.2%', 'LIVE'],
  ['L-102', 'AI-112', '4h', 'v2.1', 'A-043', '25%', '+14.1%', 'LIVE'],
  ['L-110', '모의운용-012', '3d', 'v1.2', 'A-043', '15%', '+8.4%', '모의운용'],
  ['L-208', 'TV-044', '1d', 'v1.7', 'A-017', '20%', '+9.3%', 'SHADOW'],
  ['L-318', 'GH-018', '30m', 'v1.1', 'A-055', '12%', '-1.3%', 'PAUSED'],
];

const sources = [
  ['TV-021', 'TradingView', 'RSI Mean Reversion', 'Open Source', 'VERIFIED', '10m · 30m · 1h'],
  ['TV-044', 'TradingView', 'Supertrend Regime', 'Own/Public Pine', 'VERIFIED', '1h · 1d'],
  ['GH-018', 'GitHub', 'Breakout Engine', 'Licensed', 'TESTING', '30m · 4h'],
  ['모의운용-012', 'Paper', 'Revision Momentum', 'Described', 'READY', '1d · 3d'],
  ['AI-112', 'Internal AI', 'Liquidity Regime Alpha', 'Internal', 'ACTIVE', '10m · 4h'],
];

function toneClass(value: string): Tone {
  if (/^-|CUT|PAUS|RETIRED|CRITICAL/.test(value)) return 'red';
  if (/\+|LIVE|SCALE|PASS|VERIFIED|ACTIVE|READY|NORMAL/.test(value)) return 'green';
  if (/모의운용|SHADOW|TEST|REVIEW/.test(value)) return 'cyan';
  return 'muted';
}

function Badge({ children, tone = 'muted' }: { children: string; tone?: Tone }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

function Metric({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: Tone }) {
  return <div className="metric panel"><span>{label}</span><strong className={tone ? `txt-${tone}` : ''}>{value}</strong>{sub && <small>{sub}</small>}</div>;
}

function Sparkline({ down = false }: { down?: boolean }) {
  return <svg viewBox="0 0 400 90" className={`spark ${down ? 'down' : ''}`} aria-label="equity curve">
    <path d="M0 70 C28 68,36 35,62 43 S108 63,134 42 S180 19,205 29 S245 55,275 38 S322 22,350 27 S382 15,400 13" fill="none" stroke="currentColor" strokeWidth="3" />
    <path d="M0 71 H400" stroke="currentColor" opacity=".12" />
  </svg>;
}

function DataTable({ headers, rows }: { headers: string[]; rows: (string | number)[][] }) {
  return <div className="table-wrap"><table><thead><tr>{headers.map(h => <th key={h}>{h}</th>)}</tr></thead><tbody>{rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}>{j > 1 && typeof c === 'string' ? <span className={`cell-value ${toneClass(c)}`}>{c}</span> : c}</td>)}</tr>)}</tbody></table></div>;
}

function SectionHeader({ title, eyebrow, actions }: { title: string; eyebrow?: string; actions?: string[] }) {
  return <div className="section-head"><div><small>{eyebrow}</small><h2>{title}</h2></div>{actions && <div className="actions">{actions.map(a => <button key={a} className={a.includes('STOP') ? 'danger' : ''}>{a}</button>)}</div>}</div>;
}

function CommandCenter({ setPage }: { setPage: (p: PageKey) => void }) {
  return <>
    <SectionHeader title="Command Center" eyebrow="자본 → 에이전트 → 매매 → 수익" actions={['신규 주문 일시정지', '긴급 전체정지']} />
    <div className="metrics four"><Metric label="총 운용자본" value="₩1.000B" sub="deployed + reserve" /><Metric label="총 평가자산" value="₩1.083B" sub="+8.35% all-time" tone="green" /><Metric label="오늘 순손익" value="+₩4.2M" sub="after costs" tone="green" /><Metric label="낙폭" value="-1.12%" sub="limit -10.0%" tone="amber" /></div>
    <div className="grid two wide-left"><div className="panel chart-panel"><div className="panel-title"><b>자산 곡선</b><span>비용 반영 · 증권사 대조 완료</span></div><Sparkline /></div><div className="panel"><div className="panel-title"><b>전체 위험</b><Badge tone="green">NORMAL</Badge></div><div className="risk-bars"><RiskBar label="Gross" value={68} text="118%"/><RiskBar label="Net" value={54} text="54%"/><RiskBar label="VaR" value={34} text="1.8%"/><RiskBar label="Tech Cluster" value={72} text="23%"/></div></div></div>
    <div className="grid two"><div className="panel clickable" onClick={() => setPage('domains')}><div className="panel-title"><b>영역별 자본배분</b><span>10개 분산·헤지 영역</span></div>{domains.slice(0,6).map(d => <div className="row-line" key={String(d[0])}><span>{d[0]}</span><b>{d[2]}</b></div>)}</div><div className="panel clickable" onClick={() => setPage('investors')}><div className="panel-title"><b>투자 에이전트 순위</b><span>상위 실전 에이전트</span></div>{investors.slice(0,4).map((a,i) => <div className="row-line" key={a[0]}><span>#{i+1} <b>{a[0]}</b> · {a[1]}</span><b className={String(a[3]).startsWith('+')?'txt-green':'txt-red'}>{a[3]}</b></div>)}</div></div>
    <div className="grid three"><MiniStat title="에이전트 분포" lines={['RESEARCH 46', '모의운용 21', 'SHADOW 17', 'SMALL LIVE 9', 'LIVE 31']} /><MiniStat title="전략 공장" lines={['신규 원천 18', '시간축 후보 32', '신규 전략 계보 7', '도전자 버전 11']} /><MiniStat title="실행 상태" lines={['Nautilus HEALTHY', 'Broker CONNECTED', 'Market Data LIVE', 'Pending Predictions 128']} /></div>
    <div className="panel"><div className="panel-title"><b>실시간 이벤트</b><span>변경 불가 추적 기록</span></div><EventLine time="10:31:04" tag="SOURCE" text="TradingView source TV-221 registered"/><EventLine time="10:31:08" tag="STRATEGY" text="Lineage L-812 / 1h created and assigned to A-043"/><EventLine time="10:31:11" tag="PRED" text="P-8122 matured → actual outcome stored"/><EventLine time="10:31:15" tag="TRADE" text="A-043 · L-101 · NVDA BUY 100 → Nautilus FILLED"/></div>
  </>;
}

function RiskBar({label,value,text}:{label:string;value:number;text:string}) { return <div className="risk-row"><span>{label}</span><div className="bar"><i style={{width:`${value}%`}} /></div><b>{text}</b></div>; }
function MiniStat({title,lines}:{title:string;lines:string[]}) { return <div className="panel"><div className="panel-title"><b>{title}</b></div>{lines.map(l=><div className="mono-line" key={l}>{l}</div>)}</div>; }
function EventLine({time,tag,text}:{time:string;tag:string;text:string}) { return <div className="event"><time>{time}</time><Badge tone={tag==='TRADE'?'green':tag==='PRED'?'purple':'cyan'}>{tag}</Badge><span>{text}</span></div>; }

function Domains() { return <><SectionHeader title="투자 / 헤지 영역" eyebrow="에이전트 경쟁보다 먼저 영역 분산을 강제" actions={['새 영역', '위험군']} /><div className="callout"><b>에이전트 최소 수 규칙</b><span>각 영역마다 연구 가능한 투자 에이전트를 최소 10개 유지합니다. 최소 수를 맞추기 위해 실전 자본을 강제로 배정하지는 않습니다.</span></div><div className="panel"><DataTable headers={['DOMAIN','INVESTORS','CAPITAL','RETURN','MANDATE','SHARPE']} rows={domains}/></div><div className="grid two"><div className="panel"><div className="panel-title"><b>Domain Constitution · Crisis Hedge</b><Badge tone="purple">TAIL PROTECTION</Badge></div><dl className="kv"><dt>용도</dt><dd>Offset systemic Risk-On drawdowns</dd><dt>Normal market</dt><dd>Low / slightly negative return allowed</dd><dt>Minimum capital</dt><dd>5%</dd><dt>Maximum capital</dt><dd>15%</dd><dt>Evaluation</dt><dd>Tail contribution + downside protection</dd></dl></div><div className="panel"><div className="panel-title"><b>Dynamic Risk Clusters</b><span>measured, not named</span></div><RiskBar label="Tech / Risk-On" value={78} text="23%"/><RiskBar label="Trend" value={58} text="17%"/><RiskBar label="USD / Rates" value={46} text="14%"/><RiskBar label="Crisis Protection" value={30} text="8%"/></div></div></> }

function Investors() { const [selected,setSelected]=useState('A-043'); const inv=investors.find(x=>x[0]===selected) ?? investors[0]; return <><SectionHeader title="Autonomous 투자 에이전트 순위" eyebrow="분산·헤지 영역 안에서 독립 투자 에이전트들이 경쟁" actions={['에이전트 생성','에이전트 수 관리']} /><div className="panel"><DataTable headers={['INVESTOR','DOMAIN','CAPITAL','NET RETURN','SHARPE','MDD','STRATEGIES','STATE']} rows={investors}/></div><div className="chips">{investors.map(a=><button className={selected===a[0]?'active':''} onClick={()=>setSelected(String(a[0]))} key={a[0]}>{a[0]}</button>)}</div><div className="grid two wide-left"><div className="panel"><div className="panel-title"><b>{inv[0]} 전략 묶음</b><span>{inv[1]} · {inv[2]}</span></div><DataTable headers={['LINEAGE','SOURCE','HORIZON','VERSION','INVESTOR','ALLOCATION','NET PNL','STATE']} rows={strategies.filter(s=>s[4]===inv[0])}/></div><div className="panel"><div className="panel-title"><b>에이전트 판단</b><Badge tone="green">AUTONOMOUS</Badge></div><dl className="kv"><dt>Market regime</dt><dd>Risk-On / medium volatility</dd><dt>Current thesis</dt><dd>AI infrastructure revision remains positive</dd><dt>Capital usage</dt><dd>71%</dd><dt>시장 연구 queue</dt><dd>8 hypotheses · 3 experiments</dd></dl></div></div></>; }

function Capital() { return <><SectionHeader title="3단계 자본 배분" eyebrow="총자본 → 영역 → 투자 에이전트 → 전략" actions={['시뮬레이션','승인 모드','자동 실행']} /><div className="metrics three"><Metric label="배정 자본" value="₩925M"/><Metric label="현금" value="₩108M"/><Metric label="예비자금" value="₩50M"/></div><div className="grid three"><Allocation title="1 · DOMAIN" rows={[['평가자산 Growth','15%'],['CTA','15%'],['Neutral','14%'],['FX','10%'],['Crisis Hedge','7%']]} /><Allocation title="2 · INVESTOR" rows={[['A-043','28%'],['A-017','22%'],['A-102','18%'],['A-055','14%'],['Other','18%']]} /><Allocation title="3 · STRATEGY" rows={[['L-101','18%'],['L-102','25%'],['L-110','15%'],['L-208','20%'],['Cash','22%']]} /></div><div className="panel"><div className="panel-title"><b>다음 자본 재배분 후보</b><span>verified net PnL + risk + correlation + capacity + cost</span></div><EventLine time="NEXT" tag="CAP" text="A-043 +₩20M · sustained risk-adjusted return"/><EventLine time="NEXT" tag="CAP" text="A-071 -₩15M · drawdown and negative alpha"/><EventLine time="NEXT" tag="RISK" text="Crisis Hedge +2% · Risk-On cluster concentration"/></div></>; }
function Allocation({title,rows}:{title:string;rows:string[][]}) { return <div className="panel"><div className="panel-title"><b>{title}</b></div>{rows.map(r=><div className="row-line" key={r[0]}><span>{r[0]}</span><b>{r[1]}</b></div>)}</div>; }

function Portfolio() { return <><SectionHeader title="전체 포트폴리오" eyebrow="Actual broker positions mapped back to Domains, Investors and 전략 묶음s" actions={['리밸런싱']} /><div className="tabs"><Badge tone="cyan">ASSET</Badge><Badge>DOMAIN</Badge><Badge>INVESTOR</Badge><Badge>STRATEGY</Badge><Badge>RISK CLUSTER</Badge></div><div className="grid three"><Allocation title="ASSET CLASS" rows={[['평가자산','42%'],['Futures','21%'],['FX','12%'],['Bonds','9%'],['Commodity','8%'],['Cash','8%']]} /><Allocation title="DOMAIN" rows={[['Growth','15%'],['Neutral','14%'],['CTA','15%'],['FX','10%'],['Hedge','7%']]} /><Allocation title="RISK CLUSTER" rows={[['Tech Risk-On','23%'],['Trend','17%'],['USD/Rates','14%'],['Crisis','8%']]} /></div><div className="panel"><DataTable headers={['ASSET','ACTUAL','TARGET','DELTA','PROPOSED ORDER','ATTRIBUTION']} rows={[["NVDA","8.0%","11.0%","+3.0%","BUY 100","A-043 / L-101"],["MSFT","9.0%","7.0%","-2.0%","SELL 51","A-017 / L-208"],["GOLD","3.0%","5.0%","+2.0%","BUY","Crisis Hedge"]]}/></div></>; }

function Risk() { return <><SectionHeader title="전체 위험" eyebrow="위험 통제가 모든 에이전트보다 우선" actions={['스트레스 테스트','위험자산 일시정지']} /><div className="metrics five"><Metric label="GROSS" value="118%"/><Metric label="NET" value="54%"/><Metric label="LEVERAGE" value="1.18x"/><Metric label="VaR" value="1.8%"/><Metric label="CVaR" value="2.7%"/></div><div className="grid two"><div className="panel"><div className="panel-title"><b>집중도</b><Badge tone="green">NORMAL</Badge></div><RiskBar label="Domain · Growth" value={52} text="15%"/><RiskBar label="Investor · A-043" value={41} text="10%"/><RiskBar label="Source Family · TV-RSI" value={30} text="7%"/><RiskBar label="Horizon · 10m" value={48} text="14%"/><RiskBar label="Instrument · NVDA" value={26} text="8%"/></div><div className="panel"><div className="panel-title"><b>계층형 중지 스위치</b><span>scoped controls</span></div>{['GLOBAL · 전체정지','DOMAIN · STOP DOMAIN','INVESTOR · PAUSE INVESTOR','STRATEGY · PAUSE STRATEGY','INSTRUMENT · BLOCK SYMBOL','BROKER / VENUE · DISCONNECT'].map((x,i)=><button className={i===0?'kill':''} key={x}>{x}</button>)}</div></div></>; }

function Trading() { return <><SectionHeader title="Nautilus 실전 매매" eyebrow="주문·체결의 최종 기준" actions={['LIVE ●','미체결 주문 취소','전체정지']} /><div className="grid two wide-left"><div className="panel chart-panel"><div className="panel-title"><b>NVDA · 143.21</b><span>Live Market</span></div><Sparkline /></div><div className="panel"><div className="panel-title"><b>계좌</b><Badge tone="green">BROKER 대조완료</Badge></div><dl className="kv"><dt>평가자산</dt><dd>₩1.083B</dd><dt>Cash</dt><dd>₩108M</dd><dt>Margin</dt><dd>₩71M</dd><dt>Buying power</dt><dd>₩240M</dd></dl></div></div><div className="panel"><div className="panel-title"><b>주문 / 체결</b><span>Agent + Strategy + Prediction lineage retained</span></div><DataTable headers={['ID','INVESTOR','LINEAGE','TICKET','ASSET','SIDE','QTY','STATE']} rows={[["1882","A-043","L-101","P-8821","NVDA","BUY","100","FILLED"],["1883","A-017","L-208","P-8824","NVDA","SELL","40","FILLED"],["1884","A-102","L-445","P-8830","ES","BUY","3","OPEN"]]}/></div><VirtualLedger /></>; }
function VirtualLedger(){return <div className="panel"><div className="panel-title"><b>가상 에이전트 원장 · NVDA</b><Badge tone="green">대조완료</Badge></div><DataTable headers={['ATTRIBUTION','VIRTUAL POSITION','NET PNL','BROKER NET']} rows={[["A-043 / L-101","+100","+₩842K",""],["A-017 / L-208","-40","-₩112K",""],["A-055 / L-318","+20","+₩93K",""],["TOTAL","+80","+₩823K","+80 ✓"]]}/></div>}


type TvStrategy = {
  id: string;
  name: string;
  category: string;
  domain: string;
  logic: string;
  horizons: string;
  source: string;
  score: number;
  best: string;
  agents: number;
  status: string;
};

const tvStrategies: TvStrategy[] = [
  { id:'TV-021', name:'RSI 평균회귀', category:'평균회귀', domain:'시장 중립', logic:'과매수·과매도 복귀', horizons:'10분 · 30분 · 1시간', source:'공개 Pine', score:92, best:'미국 NASDAQ 대형주', agents:6, status:'검증완료' },
  { id:'TV-044', name:'Supertrend 추세추종', category:'추세추종', domain:'CTA / 선물', logic:'ATR 기반 추세 전환', horizons:'1시간 · 4시간 · 1일', source:'직접 등록', score:89, best:'미국 지수선물', agents:8, status:'운용중' },
  { id:'TV-057', name:'Donchian 돌파', category:'돌파', domain:'주식 성장', logic:'고점·저점 채널 돌파', horizons:'30분 · 1시간 · 4시간', source:'공개 Pine', score:87, best:'한국 KOSDAQ 모멘텀주', agents:4, status:'검증완료' },
  { id:'TV-063', name:'VWAP 회귀', category:'평균회귀', domain:'시장 중립', logic:'장중 VWAP 괴리 복귀', horizons:'5분 · 10분 · 30분', source:'직접 등록', score:84, best:'미국 고유동성 대형주', agents:5, status:'검증중' },
  { id:'TV-071', name:'MACD 모멘텀', category:'모멘텀', domain:'주식 성장', logic:'추세 강도 + 교차', horizons:'30분 · 1시간 · 4시간', source:'공개 Pine', score:83, best:'일본 Nikkei 대형주', agents:3, status:'후보' },
  { id:'TV-088', name:'볼린저 변동성 수축', category:'변동성', domain:'변동성', logic:'밴드 수축 후 확장', horizons:'10분 · 1시간 · 1일', source:'공개 Pine', score:81, best:'미국 성장주 / ETF', agents:4, status:'후보' },
  { id:'TV-102', name:'ADX + EMA 추세필터', category:'추세추종', domain:'FX 매크로', logic:'방향성 강도 + 이동평균', horizons:'1시간 · 4시간 · 1일', source:'공개 Pine', score:79, best:'EURUSD · USDJPY', agents:2, status:'검증중' },
  { id:'TV-118', name:'Opening Range Breakout', category:'돌파', domain:'주식 성장', logic:'장초 범위 돌파', horizons:'5분 · 10분 · 30분', source:'직접 등록', score:78, best:'미국 NASDAQ 장초 거래', agents:4, status:'후보' },
  { id:'TV-126', name:'Pairs Z-Score', category:'페어 / 차익', domain:'상대가치', logic:'상관쌍 스프레드 정상화', horizons:'1시간 · 4시간 · 1일', source:'공개 Pine', score:76, best:'한국 동일업종 대형주', agents:3, status:'후보' },
  { id:'TV-131', name:'Crypto Trend Grid', category:'크립토', domain:'CTA / 선물', logic:'추세필터 + 분할진입', horizons:'10분 · 1시간 · 4시간', source:'공개 Pine', score:74, best:'BTC · ETH 현물/선물', agents:2, status:'연구중' },
];

const tvMatches: Record<string, [string,string,string,string,string][]> = {
  'TV-021': [
    ['미국','NASDAQ','NVDA · AMD · MSFT','10분 / 30분','96점'],
    ['한국','KOSPI','삼성전자 · SK하이닉스','30분 / 1시간','88점'],
    ['일본','TSE Prime','도요타 · 소니','1시간','81점'],
    ['ETF','미국','QQQ · SMH','30분 / 1시간','90점'],
  ],
  'TV-044': [
    ['미국','CME 지수선물','ES · NQ','1시간 / 4시간','95점'],
    ['원자재','CME/COMEX','GC · CL','4시간 / 1일','90점'],
    ['FX','글로벌','EURUSD · USDJPY','4시간 / 1일','87점'],
    ['한국','KOSPI200 선물','KOSPI200','1시간 / 4시간','82점'],
  ],
  'TV-057': [
    ['한국','KOSDAQ','거래대금 상위 모멘텀주','30분 / 1시간','94점'],
    ['미국','NASDAQ','중대형 성장주','30분 / 1시간','91점'],
    ['일본','TSE Growth','고유동성 성장주','1시간 / 4시간','80점'],
    ['ETF','미국','ARKK · IWM','1시간 / 4시간','78점'],
  ],
};

function scoreTone(score:number):Tone {
  if(score>=88) return 'green';
  if(score>=80) return 'cyan';
  if(score>=75) return 'amber';
  return 'muted';
}

function TradingViewStrategies(){
  const [category,setCategory]=useState('전체');
  const [selected,setSelected]=useState('TV-021');
  const [created,setCreated]=useState<string[]>([]);
  const categories=['전체','추세추종','평균회귀','돌파','모멘텀','변동성','페어 / 차익','크립토'];
  const filtered=category==='전체'?tvStrategies:tvStrategies.filter(x=>x.category===category);
  const current=tvStrategies.find(x=>x.id===selected) ?? tvStrategies[0];
  const matches=tvMatches[current.id] ?? [
    ['미국','NASDAQ / NYSE','고유동성 종목','1시간 / 4시간','84점'],
    ['한국','KOSPI / KOSDAQ','거래대금 상위 종목','30분 / 1시간','80점'],
    ['일본','TSE Prime','대형주','1시간 / 4시간','76점'],
    ['FX','글로벌','주요 통화쌍','4시간 / 1일','74점'],
  ];
  const makeAgents=()=>{
    const labels=matches.slice(0,3).map((m,i)=>`${current.id}-A${String(i+1).padStart(2,'0')} · ${m[0]} ${m[1]} · ${m[3]}`);
    setCreated(labels);
  };
  return <>
    <SectionHeader title="트레이딩뷰 전략 전체 관리" eyebrow="계속 유입되는 전략을 수집·분류·평가하고 시장별 에이전트로 전환" actions={['신규 전략 등록','자동 분류 실행','추천 다시 계산']} />
    <div className="metrics five">
      <Metric label="전체 전략" value="128" sub="등록·수집된 전략" />
      <Metric label="검증 완료" value="47" sub="재현성 확인" tone="green" />
      <Metric label="자동 매칭 완료" value="93" sub="국가·시장·종목 적합도" tone="cyan" />
      <Metric label="생성 에이전트" value="216" sub="전략 × 시장 × 시간축" />
      <Metric label="실전 운용" value="31" sub="Nautilus 연결" tone="green" />
    </div>

    <div className="callout">
      <b>핵심 원칙</b>
      <span>TradingView 전략 하나를 그대로 한 전략으로 끝내지 않습니다. 같은 원천 전략이라도 국가·시장·종목군·시간축이 다르면 별도 실험과 별도 에이전트 후보로 분리합니다.</span>
    </div>

    <div className="subnav strategy-categories">
      {categories.map(c=><button key={c} className={category===c?'active':''} onClick={()=>setCategory(c)}>{c}</button>)}
    </div>

    <div className="grid two tv-library-grid">
      <div className="panel">
        <div className="panel-title"><b>전체 전략 보관함</b><span>{category} · {filtered.length}개 표시 / 총 128개</span></div>
        <div className="tv-list">
          {filtered.map(x=><button key={x.id} className={selected===x.id?'tv-row selected':'tv-row'} onClick={()=>{setSelected(x.id);setCreated([])}}>
            <span className="tv-id">{x.id}</span>
            <span className="tv-name"><b>{x.name}</b><small>{x.logic}</small></span>
            <span><Badge tone="purple">{x.category}</Badge></span>
            <span className="tv-domain">{x.domain}</span>
            <span className="tv-score"><b>{x.score}</b><small>적합도</small></span>
          </button>)}
        </div>
      </div>

      <div className="panel">
        <div className="panel-title"><b>{current.id} · {current.name}</b><Badge tone={scoreTone(current.score)}>{`${current.score}점`}</Badge></div>
        <dl className="kv">
          <dt>전략 영역</dt><dd>{current.category} → {current.domain}</dd>
          <dt>핵심 로직</dt><dd>{current.logic}</dd>
          <dt>권장 시간축</dt><dd>{current.horizons}</dd>
          <dt>원천</dt><dd>{current.source}</dd>
          <dt>현재 최고 적합</dt><dd>{current.best}</dd>
          <dt>연결 에이전트</dt><dd>{current.agents}개</dd>
          <dt>상태</dt><dd>{current.status}</dd>
        </dl>
        <div className="actions left">
          <button>원문 보기</button>
          <button>백테스트 열기</button>
          <button onClick={makeAgents}>추천 조합으로 에이전트 생성</button>
        </div>
      </div>
    </div>

    <div className="grid two wide-left">
      <div className="panel">
        <div className="panel-title"><b>자동 시장·종목 적합도 매칭</b><span>전략 구조 + 거래비용 + 변동성 + 유동성 + 시장제도 + 시간축</span></div>
        <DataTable headers={['국가/자산군','시장','추천 종목군','권장 시간축','적합도']} rows={matches}/>
      </div>
      <div className="panel">
        <div className="panel-title"><b>자동 판단 근거</b><Badge tone="cyan">에이전트 평가</Badge></div>
        <RiskBar label="신호 재현성" value={94} text="94"/>
        <RiskBar label="유동성 적합" value={91} text="91"/>
        <RiskBar label="비용 내성" value={86} text="86"/>
        <RiskBar label="시장 구조" value={89} text="89"/>
        <RiskBar label="과최적화 위험" value={28} text="낮음"/>
        <p className="note">추천 점수는 단순 수익률 순위가 아니라 시장별 슬리피지·수수료·거래빈도·변동성·체결 가능성·홀드아웃 안정성까지 합산해 계산하는 전제로 설계합니다.</p>
      </div>
    </div>

    <div className="grid two">
      <div className="panel">
        <div className="panel-title"><b>관리자 선택 → 에이전트 생성 방식</b><span>한 전략에서 여러 독립 투자 에이전트 생성 가능</span></div>
        <ol className="steps">
          <li>관리자가 TradingView 전략 선택</li>
          <li>시스템이 전략 영역 자동 분류</li>
          <li>국가·시장·종목군 후보 자동 탐색</li>
          <li>각 후보별 최적 시간축 탐색</li>
          <li>상위 조합마다 독립 연구 에이전트 생성</li>
          <li>각 에이전트가 별도 백테스트·워크포워드·홀드아웃 수행</li>
          <li>통과한 에이전트만 Paper → Shadow → Small Live → Live 승격</li>
        </ol>
      </div>
      <div className="panel">
        <div className="panel-title"><b>생성 예정 에이전트</b><span>{created.length ? current.id+' 기준 생성 계획' : '전략을 선택하고 생성 버튼을 누르십시오'}</span></div>
        {created.length ? created.map((x,i)=><div className="agent-plan" key={x}><Badge tone="green">{`후보 ${i+1}`}</Badge><b>{x}</b><span>독립 메모리 · 독립 성과 · 독립 실패이력</span></div>) :
        <div className="empty-state">아직 생성 계획이 없습니다.</div>}
      </div>
    </div>

    <div className="panel">
      <div className="panel-title"><b>전략 영역 자동 분류 현황</b><span>전략 쏠림을 막고 비어 있는 영역을 자동 탐지</span></div>
      <DataTable headers={['영역','보유 전략','연구 에이전트','실전 에이전트','부족 여부','자동 행동']} rows={[
        ['추세추종','31','52','12','충분','상위 전략만 추가 검증'],
        ['평균회귀','26','44','9','충분','시장 다변화'],
        ['돌파','18','31','5','보통','한국·일본 추가 탐색'],
        ['변동성','9','16','2','부족','신규 전략 우선 수집'],
        ['페어 / 차익','7','12','1','부족','전략 자동 추천 강화'],
        ['FX 매크로','11','20','2','부족','통화쌍별 후보 확장'],
        ['위기 헤지','4','10','0','매우 부족','최우선 보강'],
      ]}/>
    </div>
  </>;
}

function StrategyFactory() { const [tab,setTab]=useState<'hub'|'tv'|'horizon'|'family'>('hub'); return <><SectionHeader title="전략 공장" eyebrow="외부 전략 원천과 내부 AI 발굴 결과를 추적 가능한 전략 계보로 전환" actions={['새 전략 등록','자동 발굴 실행']} /><div className="subnav">{[['hub','전략 원천'],['tv','트레이딩뷰 등록'],['horizon','시간축 탐색'],['family','전략 계열']].map(([k,l])=><button className={tab===k?'active':''} onClick={()=>setTab(k as typeof tab)} key={k}>{l}</button>)}</div>{tab==='hub'&&<SourceHub/>}{tab==='tv'&&<TradingViewConnector/>}{tab==='horizon'&&<HorizonLab/>}{tab==='family'&&<FamilyMatrix/>}</>; }
function SourceHub(){return <><div className="source-cards"><SourceCard title="TradingView" detail="Public / own Pine + official alert webhook" count="21"/><SourceCard title="GitHub" detail="Licensed strategy repositories" count="18"/><SourceCard title="Papers" detail="Academic strategy descriptions" count="12"/><SourceCard title="Internal AI" detail="RD-Agent · Qlib · pattern mining" count="34"/></div><div className="panel"><DataTable headers={['SOURCE','CHANNEL','STRATEGY','ACCESS','STATUS','HORIZONS']} rows={sources}/></div></>}
function SourceCard({title,detail,count}:{title:string;detail:string;count:string}){return <div className="panel source-card"><strong>{title}</strong><b>{count}</b><span>{detail}</span></div>}
function TradingViewConnector(){return <div className="grid two"><div className="panel"><div className="panel-title"><b>TradingView 신규 전략 등록</b><Badge tone="cyan">수동 / 공식</Badge></div><label>TradingView 전략 주소<input placeholder="https://www.tradingview.com/script/..." /></label><label>공개 또는 직접 보유한 Pine 소스<textarea rows={10} placeholder={"//@version=6\nstrategy(...)\n..."} /></label><div className="actions left"><button>TradingView 열기</button><button>원천 검증</button><button>Pine 가져오기</button></div><p className="note">자동 스크래핑 및 보호·초대전용 소스 추출은 사용하지 않습니다. 원천 주소·작성자·URL·내용 해시는 보존합니다.</p></div><div className="panel"><div className="panel-title"><b>TradingView 알림 Webhook</b><Badge tone="green">백엔드 연결 준비</Badge></div><label>Webhook endpoint<input readOnly value="/webhooks/tradingview/{connection_id}" /></label><dl className="kv"><dt>상태</dt><dd>아직 연결되지 않음</dd><dt>용도</dt><dd>TradingView 알림 신호 수신</dd><dt>소스 코드</dt><dd>Webhook으로 소스코드를 가져오지 않음</dd></dl><button>연결 생성</button><hr/><div className="panel-title"><b>Pine → Python 변환 흐름</b></div><ol className="steps"><li>Pine 전략 구조 분석</li><li>진입·청산·위험 규칙 추출</li><li>Python 실행 구조로 변환</li><li>원본 신호 일치도 검증</li><li>시간축 탐색으로 전달</li><li>변경 불가 전략 계보 생성</li></ol></div></div>}
function HorizonLab(){return <div className="panel"><div className="panel-title"><b>시간축 탐색 · TV-021</b><span>전략 계보 생성 전 검증</span></div><DataTable headers={['HORIZON','EVENTS','COST-ADJ EV','STABILITY','HOLDOUT','DECISION']} rows={[["10m","12,421","+0.18%","PASS","PASS","CANDIDATE"],["30m","8,112","+0.23%","PASS","PASS","CANDIDATE"],["1h","4,219","+0.31%","PASS","PASS","CANDIDATE"],["4h","1,110","+0.15%","REVIEW","REVIEW","REVIEW"],["1d","822","+0.72%","PASS","PASS","CANDIDATE"],["3d","282","-0.11%","WEAK","FAIL","REJECT"]]}/><div className="actions left"><button>CREATE 10m LINEAGE</button><button>CREATE 30m LINEAGE</button><button>CREATE 1h LINEAGE</button><button>CREATE 1d LINEAGE</button></div></div>}
function FamilyMatrix(){return <div className="panel"><div className="panel-title"><b>원천 전략 × 고정 시간축 전략 계열</b><span>각 칸은 독립 전략 계보</span></div><DataTable headers={['SOURCE','10m','30m','1h','4h','1d','3d','1w']} rows={[["TV-RSI","L-101","L-104","L-105","—","L-108","—","—"],["TV-Supertrend","L-201","—","—","L-205","L-208","—","—"],["GH-Breakout","—","L-301","—","L-305","—","—","—"],["AI-Liquidity","L-401","—","L-403","—","—","—","—"]]}/></div>}

function Research(){return <><SectionHeader title="시장 연구" eyebrow="시장·거시·펀더멘털·뉴스·기회 근거"/><div className="grid three"><MiniStat title="시장" lines={['Regime: Risk-On','Volatility: Moderate','Breadth: Positive','Liquidity: Normal']}/><MiniStat title="거시경제" lines={['Rates: Stable','USD: Firm','Inflation: Cooling','Growth: Mixed']}/><MiniStat title="시장심리" lines={['Bull: 72%','Bear: 28%','News score: +0.34','Uncertainty: 0.19']}/></div><div className="grid two"><div className="panel"><div className="panel-title"><b>기회 후보</b></div><DataTable headers={['ASSET','INVESTOR','THESIS','HORIZON','EXPECTED','CONFIDENCE']} rows={[["NVDA","A-043","Earnings revision + momentum","5d","+4.2%","81%"],["EURUSD","A-071","Rate differential","1d","+1.1%","68%"],["GOLD","A-102","Inflation hedge breakout","4h","+0.9%","66%"]]}/></div><div className="panel"><div className="panel-title"><b>근거 자료</b></div><EventLine time="RSH" tag="AI" text="TradingAgents market/news/fundamental debate"/><EventLine time="FIN" tag="DATA" text="FinRobot valuation and earnings computations"/><EventLine time="MAC" tag="MACRO" text="Macro evidence bundle"/><EventLine time="SRC" tag="SOURCE" text="External strategy provenance linked where applicable"/></div></div></>}

function Lab(){return <><SectionHeader title="퀀트 연구소" eyebrow="가설 → 실험 → 모델 → 검증" actions={['새 가설','대기 실험 실행']} /><div className="metrics four"><Metric label="RUNNING" value="8"/><Metric label="QUEUED" value="21"/><Metric label="PASSED" value="284" tone="green"/><Metric label="FAILED" value="193" tone="red"/></div><div className="panel"><DataTable headers={['EXPERIMENT','INVESTOR','LINEAGE','ENGINE','STATUS','PROGRESS','RESULT']} rows={[["EXP-1203","A-043","L-101","RLlib","RUNNING","71%","—"],["EXP-1204","A-071","L-502","Qlib","VALIDATING","92%","—"],["EXP-1199","A-102","L-445","Chronos","PASSED","100%","Sharpe 1.81"],["EXP-1190","A-055","L-318","vectorbt","FAILED","100%","Cost removes alpha"]]}/></div><div className="grid two"><div className="panel"><div className="panel-title"><b>Model Consensus · NVDA</b></div><DataTable headers={['ENGINE','OUTPUT','CONFIDENCE']} rows={[["Qlib","Score +0.82","82%"],["Chronos","Forecast +3.2%","74%"],["SB3","LONG","69%"],["RLlib","LONG","71%"]]}/></div><div className="panel"><div className="panel-title"><b>Validation Chain</b></div><ol className="steps"><li>vectorbt quick screen <Badge tone="green">PASS</Badge></li><li>Leakage / multiple-test check <Badge tone="green">PASS</Badge></li><li>Walk-forward <Badge tone="green">PASS</Badge></li><li>Holdout <Badge tone="green">PASS</Badge></li><li>Nautilus realistic backtest <Badge tone="cyan">RUNNING</Badge></li></ol></div></div></>}

function Strategies(){return <><SectionHeader title="운용 전략 등록부" eyebrow="고정 시간축 전략 계보는 버전 단위로 진화" actions={['백테스트','모의운용','승격 단계']} /><div className="panel"><DataTable headers={['LINEAGE','SOURCE','HORIZON','VERSION','INVESTOR','CAPITAL','NET PNL','STATE']} rows={strategies}/></div><div className="grid two"><div className="panel"><div className="panel-title"><b>챔피언 / 도전자 · L-101</b><span>Horizon 10m LOCKED</span></div><div className="compare"><div><Badge tone="green">CHAMPION v1.4</Badge><p>현재 실전 버전</p><b>Net EV +0.18%</b><span>MDD -4.2%</span></div><div><Badge tone="purple">CHALLENGER v1.5</Badge><p>변동성 필터 추가</p><b>Net EV +0.23%</b><span>MDD -3.5%</span></div></div><div className="actions left"><button>RETEST</button><button>PROMOTE v1.5</button><button>REJECT</button></div></div><div className="panel"><div className="panel-title"><b>승격 단계</b></div><ol className="steps"><li>시장 연구 ✓</li><li>Experiment ✓</li><li>Walk-forward ✓</li><li>Holdout ✓</li><li>Nautilus Backtest ✓</li><li>Paper ✓</li><li>Shadow ●</li><li>Small Live ○</li><li>Live ○</li></ol></div></div></>}

function Performance(){return <><SectionHeader title="성과 / 예측 검증" eyebrow="예측 정확도와 투자 손익을 분리 평가"/><div className="metrics five"><Metric label="NET RETURN" value="+8.35%" tone="green"/><Metric label="SHARPE" value="1.71"/><Metric label="SORTINO" value="2.12"/><Metric label="MDD" value="-4.81%" tone="amber"/><Metric label="PROFIT FACTOR" value="1.63"/></div><div className="grid two"><div className="panel chart-panel"><div className="panel-title"><b>Cost-adjusted 평가자산</b></div><Sparkline/></div><div className="panel"><div className="panel-title"><b>Attribution</b></div>{[['CTA','+3.1%'],['Growth','+2.8%'],['Neutral','+1.7%'],['FX','+1.1%'],['Hedge','-0.4%']].map(r=><div className="row-line" key={r[0]}><span>{r[0]}</span><b className={r[1].startsWith('+')?'txt-green':'txt-red'}>{r[1]}</b></div>)}</div></div><div className="panel"><div className="panel-title"><b>예측 원장</b><span>발행된 예측값은 변경 불가</span></div><DataTable headers={['TICKET','INVESTOR','LINEAGE','HORIZON','CREATED','PREDICTED','ACTUAL','VERDICT']} rows={[["P-8821","A-043","L-101","10m","10:30","+0.30%","+0.10%","DIR CORRECT"],["P-8822","A-043","L-105","1h","10:30","-0.50%","PENDING","DUE 11:30"],["P-8823","A-017","L-208","1d","Oct 23","+1.20%","PENDING","NOT MATURED"]]}/></div></>}

function Memory(){return <><SectionHeader title="기억 / 진화" eyebrow="투자 에이전트 기억과 전략 기억을 분리"/><div className="grid two"><div className="panel"><div className="panel-title"><b>투자 에이전트 기억 · A-043</b></div><MiniLines lines={['Successful regimes 12','Portfolio mistakes 8','Capital decisions 31','Risk events 4','Cross-strategy lessons 19']}/></div><div className="panel"><div className="panel-title"><b>전략 기억 · L-101</b><span>10m fixed</span></div><MiniLines lines={['Prediction failures 142','Execution failures 18','Regime failures 31','Versions 5','Current champion v1.4']}/></div></div><div className="panel"><div className="panel-title"><b>최근 자기평가</b></div><dl className="kv"><dt>Context</dt><dd>High volatility 10m downtrend</dd><dt>Failure</dt><dd>Momentum turnover increased sharply</dd><dt>Root cause</dt><dd>Volatility filter lag</dd><dt>Proposed change</dt><dd>Create v1.5 challenger with volume + volatility filter</dd><dt>Forbidden</dt><dd>Change lineage horizon or erase failed evidence</dd></dl></div></>}
function MiniLines({lines}:{lines:string[]}){return <>{lines.map(l=><div className="row-line" key={l}><span>{l}</span></div>)}</>}

function Audit(){return <><SectionHeader title="의사결정 / 근거 추적" eyebrow="에이전트·전략·예측·주문이 왜 만들어졌는지 재현" actions={['추적 기록 내보내기']} /><div className="panel"><div className="trace"><TraceNode title="SOURCE" text="TV-021 · original URL · author · hash"/><TraceNode title="HORIZON EVIDENCE" text="10m selected with independent holdout"/><TraceNode title="STRATEGY LINEAGE" text="L-101 · fixed_horizon=10m · immutable"/><TraceNode title="INVESTOR ASSIGNMENT" text="A-043 · 평가자산 Growth"/><TraceNode title="VERSION" text="Champion v1.4"/><TraceNode title="PREDICTION" text="P-8821 · created before outcome"/><TraceNode title="RISK" text="Local PASS → Global PASS"/><TraceNode title="EXECUTION" text="Nautilus → Broker fill #1882"/><TraceNode title="LEDGER" text="A-043 / L-101 virtual fill attribution"/><TraceNode title="REALITY" text="Forecast +0.30% · Actual +0.10%"/><TraceNode title="EVOLUTION" text="Challenger v1.5 proposed"/></div></div></>}
function TraceNode({title,text}:{title:string;text:string}){return <div className="trace-node"><Badge tone="cyan">{title}</Badge><b>{text}</b></div>}

function System(){return <><SectionHeader title="시스템 상태" eyebrow="설치된 퀀트 엔진과 구축 중인 제품 엔진"/><div className="grid two"><div className="panel"><div className="panel-title"><b>퀀트 / 매매 엔진</b></div>{['TradingAgents','FinRobot','RD-Agent','Qlib','Chronos','Stable-Baselines3','Ray RLlib','vectorbt','FinRL','Riskfolio','PyPortfolioOpt','NautilusTrader'].map(x=><div className="row-line" key={x}><span>{x}</span><Badge tone="green">설치완료</Badge></div>)}</div><div className="panel"><div className="panel-title"><b>제품 기능 엔진</b><span>프론트 기능 구조 우선 설계</span></div>{['Source Registry','Pine Importer','Horizon Discovery','예측 원장','가상 에이전트 원장','Capital Allocator','Population Controller','Evolution Engine','Broker Reconciliation'].map(x=><div className="row-line" key={x}><span>{x}</span><Badge tone="amber">구축예정</Badge></div>)}</div></div></>}

function Settings(){return <><SectionHeader title="설정" eyebrow="정책·제약·안전 설정"/><div className="grid two"><div className="panel"><div className="panel-title"><b>영역 / 에이전트 수 정책</b></div><label>영역별 최소 연구 에이전트 수<input value="10" readOnly/></label><label>전체 최대 허용 낙폭<input value="10%" readOnly/></label><label>최대 레버리지<input value="1.5x" readOnly/></label></div><div className="panel"><div className="panel-title"><b>전략 계보 고정 규칙</b></div><dl className="kv"><dt>전략 계보 ID</dt><dd>LOCKED</dd><dt>원천 전략</dt><dd>LOCKED</dd><dt>고정 시간축</dt><dd>LOCKED</dd><dt>전략 버전</dt><dd>EVOLVES via Champion / Challenger</dd></dl></div></div><div className="panel danger-zone"><div className="panel-title"><b>실전 매매 안전장치</b><Badge tone="red">고위험 조작</Badge></div><button>신규 주문 일시정지</button><button>미체결 주문 취소</button><button className="kill">긴급 전체정지</button></div></>}

function App() {
  const [page, setPage] = useState<PageKey>('command');
  const [collapsed, setCollapsed] = useState(false);
  const title = useMemo(() => nav.find(n => n.key === page)?.label ?? '통합 관제', [page]);
  const content = { command:<CommandCenter setPage={setPage}/>, domains:<Domains/>, investors:<Investors/>, capital:<Capital/>, portfolio:<Portfolio/>, risk:<Risk/>, trading:<Trading/>, tvstrategies:<TradingViewStrategies/>, factory:<StrategyFactory/>, research:<Research/>, lab:<Lab/>, strategies:<Strategies/>, performance:<Performance/>, memory:<Memory/>, audit:<Audit/>, system:<System/>, settings:<Settings/> }[page];
  return <div className={`app ${collapsed ? 'collapsed' : ''}`}>
    <header className="topbar"><div className="brand"><button className="collapse" onClick={()=>setCollapsed(v=>!v)}>☰</button><span className="brand-mark">AI</span><div><b>AUTONOMOUS INVESTOR</b><small>{title}</small></div></div><div className="top-metrics"><span>평가자산 <b>₩1.083B</b></span><span>오늘 <b className="txt-green">+₩4.2M</b></span><span>DD <b className="txt-amber">-1.12%</b></span><Badge tone="green">LIVE</Badge><button className="danger">전체정지</button></div></header>
    <aside className="sidebar"><div className="nav-label">관리 메뉴</div>{nav.map(n=><button key={n.key} className={page===n.key?'active':''} onClick={()=>setPage(n.key)}><span className="nav-short">{n.short}</span><span>{n.label}</span></button>)}</aside>
    <main><div className="filterbar"><span>전체 필터</span><button>영역: 전체</button><button>에이전트: 전체</button><button>원천: 전체</button><button>시간축: 전체</button><button>운용단계: 전체</button><i>현재 예시 데이터 · 실제 API 연결 준비 구조</i></div><div className="workspace">{content}</div></main>
    <aside className="events"><div className="event-head"><b>실시간 이벤트</b><Badge tone="green">WS</Badge></div><EventLine time="11:08" tag="RISK" text="전체 위험 정상"/><EventLine time="11:07" tag="TRADE" text="NVDA 체결 대조 완료"/><EventLine time="11:06" tag="PRED" text="예측 12건 결과 확인 예정"/><EventLine time="11:04" tag="SOURCE" text="신규 전략 원천 4건 대기"/><div className="event-spacer"/><div className="health"><span>NAUTILUS</span><b>● 정상</b><span>BROKER</span><b>● 연결됨</b><span>시장 데이터</span><b>● 실시간</b></div></aside>
    <footer><span>WS ● 연결됨</span><span>Nautilus ● 정상</span><span>증권사 ● 연결됨</span><span>시장 데이터 ● 실시간</span><span className="spacer"/><span>프론트 v0.2 · Vite / React / TypeScript</span></footer>
  </div>;
}

export default App;
