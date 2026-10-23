import { useEffect, useMemo, useState } from 'react';

type Tone = 'green' | 'red' | 'amber' | 'cyan' | 'purple' | 'muted';
const API_BASE = 'https://autonomous-investor-tradingview-production.up.railway.app';
const QUANT_API_BASE = 'https://autonomous-investor-quant-lab-production.up.railway.app';
type PageKey =
  | 'command' | 'domains' | 'investors' | 'capital' | 'portfolio' | 'risk'
  | 'trading' | 'tvideas' | 'tvmarkets' | 'tvstrategies' | 'factory' | 'research' | 'lab' | 'strategies' | 'performance'
  | 'memory' | 'audit' | 'system' | 'settings';

const nav: { key: PageKey; label: string; short: string }[] = [
  { key: 'command', label: '통합 관제', short: '관제' },
  { key: 'domains', label: '투자 영역', short: '영역' },
  { key: 'investors', label: '투자 에이전트', short: '에이전트' },
  { key: 'capital', label: '자본 배분', short: '자본' },
  { key: 'portfolio', label: '포트폴리오', short: '포트' },
  { key: 'risk', label: '위험 관리', short: '위험' },
  { key: 'trading', label: '실전 매매', short: '매매' },
  { key: 'tvideas', label: 'TradingView 아이디어', short: 'TV-I' },
  { key: 'tvmarkets', label: 'TradingView 마켓', short: 'TV-M' },
  { key: 'tvstrategies', label: 'TradingView 전략평가', short: 'TV-S' },
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
    <SectionHeader title="통합 관제" eyebrow="자본 → 에이전트 → 매매 → 수익" actions={['신규 주문 일시정지', '긴급 전체정지']} />
    <div className="metrics four"><Metric label="총 운용자본" value="₩1.000B" sub="배정 자본 + 예비자금" /><Metric label="총 평가자산" value="₩1.083B" sub="+8.35% 누적" tone="green" /><Metric label="오늘 순손익" value="+₩4.2M" sub="비용 차감 후" tone="green" /><Metric label="낙폭" value="-1.12%" sub="한도 -10.0%" tone="amber" /></div>
    <div className="grid two wide-left"><div className="panel chart-panel"><div className="panel-title"><b>자산 곡선</b><span>비용 반영 · 증권사 대조 완료</span></div><Sparkline /></div><div className="panel"><div className="panel-title"><b>전체 위험</b><Badge tone="green">NORMAL</Badge></div><div className="risk-bars"><RiskBar label="총 익스포저" value={68} text="118%"/><RiskBar label="순 익스포저" value={54} text="54%"/><RiskBar label="VaR" value={34} text="1.8%"/><RiskBar label="기술주 위험군" value={72} text="23%"/></div></div></div>
    <div className="grid two"><div className="panel clickable" onClick={() => setPage('domains')}><div className="panel-title"><b>영역별 자본배분</b><span>10개 분산·헤지 영역</span></div>{domains.slice(0,6).map(d => <div className="row-line" key={String(d[0])}><span>{d[0]}</span><b>{d[2]}</b></div>)}</div><div className="panel clickable" onClick={() => setPage('investors')}><div className="panel-title"><b>투자 에이전트 순위</b><span>상위 실전 에이전트</span></div>{investors.slice(0,4).map((a,i) => <div className="row-line" key={a[0]}><span>#{i+1} <b>{a[0]}</b> · {a[1]}</span><b className={String(a[3]).startsWith('+')?'txt-green':'txt-red'}>{a[3]}</b></div>)}</div></div>
    <div className="grid three"><MiniStat title="에이전트 분포" lines={['RESEARCH 46', '모의운용 21', 'SHADOW 17', 'SMALL LIVE 9', 'LIVE 31']} /><MiniStat title="전략 공장" lines={['신규 원천 18', '시간축 후보 32', '신규 전략 계보 7', '도전자 버전 11']} /><MiniStat title="실행 상태" lines={['Nautilus HEALTHY', 'Broker CONNECTED', 'Market Data LIVE', 'Pending Predictions 128']} /></div>
    <div className="panel"><div className="panel-title"><b>실시간 이벤트</b><span>변경 불가 추적 기록</span></div><EventLine time="10:31:04" tag="SOURCE" text="TradingView source TV-221 registered"/><EventLine time="10:31:08" tag="STRATEGY" text="Lineage L-812 / 1h created and assigned to A-043"/><EventLine time="10:31:11" tag="PRED" text="P-8122 matured → actual outcome stored"/><EventLine time="10:31:15" tag="TRADE" text="A-043 · L-101 · NVDA BUY 100 → Nautilus FILLED"/></div>
  </>;
}

function RiskBar({label,value,text}:{label:string;value:number;text:string}) { return <div className="risk-row"><span>{label}</span><div className="bar"><i style={{width:`${value}%`}} /></div><b>{text}</b></div>; }
function MiniStat({title,lines}:{title:string;lines:string[]}) { return <div className="panel"><div className="panel-title"><b>{title}</b></div>{lines.map(l=><div className="mono-line" key={l}>{l}</div>)}</div>; }
function EventLine({time,tag,text}:{time:string;tag:string;text:string}) { return <div className="event"><time>{time}</time><Badge tone={tag==='TRADE'?'green':tag==='PRED'?'purple':'cyan'}>{tag}</Badge><span>{text}</span></div>; }

function Domains() { return <><SectionHeader title="투자 / 헤지 영역" eyebrow="에이전트 경쟁보다 먼저 영역 분산을 강제" actions={['새 영역', '위험군']} /><div className="callout"><b>에이전트 최소 수 규칙</b><span>각 영역마다 연구 가능한 투자 에이전트를 최소 10개 유지합니다. 최소 수를 맞추기 위해 실전 자본을 강제로 배정하지는 않습니다.</span></div><div className="panel"><DataTable headers={['DOMAIN','INVESTORS','CAPITAL','RETURN','MANDATE','SHARPE']} rows={domains}/></div><div className="grid two"><div className="panel"><div className="panel-title"><b>Domain Constitution · Crisis Hedge</b><Badge tone="purple">TAIL PROTECTION</Badge></div><dl className="kv"><dt>용도</dt><dd>Offset systemic Risk-On drawdowns</dd><dt>Normal market</dt><dd>Low / slightly negative return allowed</dd><dt>Minimum capital</dt><dd>5%</dd><dt>Maximum capital</dt><dd>15%</dd><dt>Evaluation</dt><dd>Tail contribution + downside protection</dd></dl></div><div className="panel"><div className="panel-title"><b>Dynamic Risk Clusters</b><span>measured, not named</span></div><RiskBar label="Tech / Risk-On" value={78} text="23%"/><RiskBar label="추세" value={58} text="17%"/><RiskBar label="USD / Rates" value={46} text="14%"/><RiskBar label="Crisis Protection" value={30} text="8%"/></div></div></> }

function Investors() { const [selected,setSelected]=useState('A-043'); const inv=investors.find(x=>x[0]===selected) ?? investors[0]; return <><SectionHeader title="Autonomous 투자 에이전트 순위" eyebrow="분산·헤지 영역 안에서 독립 투자 에이전트들이 경쟁" actions={['에이전트 생성','에이전트 수 관리']} /><div className="panel"><DataTable headers={['INVESTOR','DOMAIN','CAPITAL','NET RETURN','SHARPE','MDD','STRATEGIES','STATE']} rows={investors}/></div><div className="chips">{investors.map(a=><button className={selected===a[0]?'active':''} onClick={()=>setSelected(String(a[0]))} key={a[0]}>{a[0]}</button>)}</div><div className="grid two wide-left"><div className="panel"><div className="panel-title"><b>{inv[0]} 전략 묶음</b><span>{inv[1]} · {inv[2]}</span></div><DataTable headers={['LINEAGE','SOURCE','HORIZON','VERSION','INVESTOR','ALLOCATION','NET PNL','STATE']} rows={strategies.filter(s=>s[4]===inv[0])}/></div><div className="panel"><div className="panel-title"><b>에이전트 판단</b><Badge tone="green">AUTONOMOUS</Badge></div><dl className="kv"><dt>Market regime</dt><dd>Risk-On / medium volatility</dd><dt>Current thesis</dt><dd>AI infrastructure revision remains positive</dd><dt>Capital usage</dt><dd>71%</dd><dt>시장 연구 queue</dt><dd>8 hypotheses · 3 experiments</dd></dl></div></div></>; }

function Capital() { return <><SectionHeader title="3단계 자본 배분" eyebrow="총자본 → 영역 → 투자 에이전트 → 전략" actions={['시뮬레이션','승인 모드','자동 실행']} /><div className="metrics three"><Metric label="배정 자본" value="₩925M"/><Metric label="현금" value="₩108M"/><Metric label="예비자금" value="₩50M"/></div><div className="grid three"><Allocation title="1 · DOMAIN" rows={[['평가자산 Growth','15%'],['CTA','15%'],['Neutral','14%'],['FX','10%'],['Crisis Hedge','7%']]} /><Allocation title="2 · INVESTOR" rows={[['A-043','28%'],['A-017','22%'],['A-102','18%'],['A-055','14%'],['Other','18%']]} /><Allocation title="3 · STRATEGY" rows={[['L-101','18%'],['L-102','25%'],['L-110','15%'],['L-208','20%'],['Cash','22%']]} /></div><div className="panel"><div className="panel-title"><b>다음 자본 재배분 후보</b><span>verified net PnL + risk + correlation + capacity + cost</span></div><EventLine time="NEXT" tag="CAP" text="A-043 +₩20M · sustained risk-adjusted return"/><EventLine time="NEXT" tag="CAP" text="A-071 -₩15M · drawdown and negative alpha"/><EventLine time="NEXT" tag="RISK" text="Crisis Hedge +2% · Risk-On cluster concentration"/></div></>; }
function Allocation({title,rows}:{title:string;rows:string[][]}) { return <div className="panel"><div className="panel-title"><b>{title}</b></div>{rows.map(r=><div className="row-line" key={r[0]}><span>{r[0]}</span><b>{r[1]}</b></div>)}</div>; }

function Portfolio() { return <><SectionHeader title="전체 포트폴리오" eyebrow="Actual broker positions mapped back to Domains, Investors and 전략 묶음s" actions={['리밸런싱']} /><div className="tabs"><Badge tone="cyan">ASSET</Badge><Badge>DOMAIN</Badge><Badge>INVESTOR</Badge><Badge>STRATEGY</Badge><Badge>RISK CLUSTER</Badge></div><div className="grid three"><Allocation title="자산군" rows={[['평가자산','42%'],['Futures','21%'],['FX','12%'],['Bonds','9%'],['Commodity','8%'],['Cash','8%']]} /><Allocation title="영역" rows={[['Growth','15%'],['Neutral','14%'],['CTA','15%'],['FX','10%'],['Hedge','7%']]} /><Allocation title="위험군" rows={[['Tech Risk-On','23%'],['Trend','17%'],['USD/Rates','14%'],['Crisis','8%']]} /></div><div className="panel"><DataTable headers={['ASSET','ACTUAL','TARGET','DELTA','PROPOSED ORDER','ATTRIBUTION']} rows={[["NVDA","8.0%","11.0%","+3.0%","BUY 100","A-043 / L-101"],["MSFT","9.0%","7.0%","-2.0%","SELL 51","A-017 / L-208"],["GOLD","3.0%","5.0%","+2.0%","BUY","위기 헤지"]]}/></div></>; }

function Risk() { return <><SectionHeader title="전체 위험" eyebrow="위험 통제가 모든 에이전트보다 우선" actions={['스트레스 테스트','위험자산 일시정지']} /><div className="metrics five"><Metric label="GROSS" value="118%"/><Metric label="NET" value="54%"/><Metric label="LEVERAGE" value="1.18x"/><Metric label="VaR" value="1.8%"/><Metric label="CVaR" value="2.7%"/></div><div className="grid two"><div className="panel"><div className="panel-title"><b>집중도</b><Badge tone="green">NORMAL</Badge></div><RiskBar label="Domain · Growth" value={52} text="15%"/><RiskBar label="Investor · A-043" value={41} text="10%"/><RiskBar label="Source Family · TV-RSI" value={30} text="7%"/><RiskBar label="Horizon · 10m" value={48} text="14%"/><RiskBar label="Instrument · NVDA" value={26} text="8%"/></div><div className="panel"><div className="panel-title"><b>계층형 중지 스위치</b><span>scoped controls</span></div>{['GLOBAL · 전체정지','DOMAIN · STOP DOMAIN','INVESTOR · PAUSE INVESTOR','STRATEGY · PAUSE STRATEGY','INSTRUMENT · BLOCK SYMBOL','BROKER / VENUE · DISCONNECT'].map((x,i)=><button className={i===0?'kill':''} key={x}>{x}</button>)}</div></div></>; }

function Trading() { return <><SectionHeader title="Nautilus 실전 매매" eyebrow="주문·체결의 최종 기준" actions={['LIVE ●','미체결 주문 취소','전체정지']} /><div className="grid two wide-left"><div className="panel chart-panel"><div className="panel-title"><b>NVDA · 143.21</b><span>Live Market</span></div><Sparkline /></div><div className="panel"><div className="panel-title"><b>계좌</b><Badge tone="green">BROKER 대조완료</Badge></div><dl className="kv"><dt>평가자산</dt><dd>₩1.083B</dd><dt>Cash</dt><dd>₩108M</dd><dt>Margin</dt><dd>₩71M</dd><dt>Buying power</dt><dd>₩240M</dd></dl></div></div><div className="panel"><div className="panel-title"><b>주문 / 체결</b><span>Agent + Strategy + Prediction lineage retained</span></div><DataTable headers={['ID','INVESTOR','LINEAGE','TICKET','ASSET','SIDE','QTY','STATE']} rows={[["1882","A-043","L-101","P-8821","NVDA","BUY","100","FILLED"],["1883","A-017","L-208","P-8824","NVDA","SELL","40","FILLED"],["1884","A-102","L-445","P-8830","ES","BUY","3","OPEN"]]}/></div><VirtualLedger /></>; }
function VirtualLedger(){return <div className="panel"><div className="panel-title"><b>가상 에이전트 원장 · NVDA</b><Badge tone="green">대조완료</Badge></div><DataTable headers={['ATTRIBUTION','VIRTUAL POSITION','NET PNL','BROKER NET']} rows={[["A-043 / L-101","+100","+₩842K",""],["A-017 / L-208","-40","-₩112K",""],["A-055 / L-318","+20","+₩93K",""],["TOTAL","+80","+₩823K","+80 ✓"]]}/></div>}



function TradingViewHeader({active}:{active:'ideas'|'markets'}) {
  return <div className="tv-global-head">
    <div className="tv-brand">TradingView</div>
    <button className="tv-search">⌕ 찾기</button>
    <div className="tv-global-nav">
      <button>프로덕트</button>
      <button className={active==='ideas'?'active':''}>커뮤니티</button>
      <button className={active==='markets'?'active':''}>마켓</button>
      <button>브로커</button>
      <button>더보기 ▾</button>
    </div>
    <div className="tv-global-actions"><button>KO</button><button className="tv-start">지금 시작</button></div>
  </div>;
}

type IdeaCardData = {
  id:string;
  user:string;
  time:string;
  title:string;
  text:string;
  symbol:string;
  bias:string;
  comments:number;
  market:string;
  chartUrl?:string | null;
  imageUrl?:string | null;
  isVideo:boolean;
  isEducation:boolean;
  isPicked:boolean;
};

type LiveIdeaResponseItem = {
  idea_id:string;
  title:string;
  description:string;
  author:string;
  symbol:string;
  exchange:string;
  asset_type:string;
  direction:string;
  interval:string;
  created_at:string;
  comments_count:number;
  likes_count:number;
  views_count:number;
  chart_url?:string | null;
  image_url?:string | null;
  is_video:boolean | number;
  is_education:boolean | number;
  is_picked:boolean | number;
  is_hot:boolean | number;
};

type LiveSourceDetail = {
  source_kind:string;
  source_id:string;
  source_url:string;
  title:string;
  full_text:string;
  hero_images:string[];
  content_images:string[];
  page_hash:string;
  fetched_at:string;
  from_cache:boolean;
};

type LivePineSource = {
  ok:boolean;
  protected?:boolean;
  reason?:string;
  script_id_part:string;
  version?:string;
  script_name?:string;
  kind?:string;
  pine_version?:number | null;
  source_hash?:string;
  source?:string;
  source_chars?:number;
  fetched_at?:string;
};

function IdeaCard({idea}:{idea:IdeaCardData}) {
  const [candidateId,setCandidateId]=useState<string | null>(null);
  const [agentCount,setAgentCount]=useState<number | null>(null);
  const [busy,setBusy]=useState(false);
  const [status,setStatus]=useState('');
  const [detail,setDetail]=useState<LiveSourceDetail | null>(null);
  const [detailOpen,setDetailOpen]=useState(false);
  const [detailLoading,setDetailLoading]=useState(false);

  const loadDetail=async()=>{
    setDetailOpen(v=>!v);
    if(detail || detailLoading) return;
    setDetailLoading(true);
    try{
      const r=await fetch(`${API_BASE}/api/v1/tradingview/ideas/${encodeURIComponent(idea.id)}/full`);
      if(!r.ok) throw new Error(await r.text());
      setDetail(await r.json() as LiveSourceDetail);
    }catch(e){
      setStatus('TradingView 전체 본문 수집 오류');
    }finally{
      setDetailLoading(false);
    }
  };

  const saveCandidate=async():Promise<string | null>=>{
    if(candidateId) return candidateId;
    setBusy(true);
    setStatus('전략 후보 생성 중');
    try{
      const r=await fetch(`${API_BASE}/api/v1/tradingview/ideas/${encodeURIComponent(idea.id)}/candidate`,{method:'POST'});
      if(!r.ok) throw new Error(await r.text());
      const data=await r.json();
      setCandidateId(data.candidate_id);
      setStatus(`${data.category} · ${(data.candidate_horizons||[]).join(' / ')}`);
      return data.candidate_id as string;
    }catch(e){
      setStatus('전략 후보 생성 오류');
      return null;
    }finally{
      setBusy(false);
    }
  };

  const makeAgents=async()=>{
    const cid=await saveCandidate();
    if(!cid) return;
    setBusy(true);
    setStatus('시장·시간축 Discovery 실행 중');
    try{
      const d=await fetch(`${API_BASE}/api/v1/horizon-discovery/${encodeURIComponent(cid)}?max_markets=3`,{method:'POST'});
      if(!d.ok) throw new Error(await d.text());
      const discovery=await d.json();
      const r=await fetch(`${API_BASE}/api/v1/agent-factory/${encodeURIComponent(cid)}?min_score=72&max_agents=12`,{method:'POST'});
      if(!r.ok) throw new Error(await r.text());
      const data=await r.json();
      setAgentCount(data.count);
      setStatus(`Discovery ${discovery.count||0}개 평가 · 통과 Agent ${data.count}개`);
    }catch(e){
      setStatus('Discovery / Agent Factory 오류');
    }finally{
      setBusy(false);
    }
  };

  const visibleText=detail?.full_text || idea.text;
  const hero=detail?.hero_images?.[0] || idea.imageUrl;

  return <article className="tv-idea-card">
    <div className="idea-chart">
      {hero ? <img className="idea-chart-image" src={hero} alt={idea.title} loading="lazy"/> : null}
      <div className="idea-symbol"><b>{idea.symbol}</b><span>{idea.market}</span></div>
      <span className={`idea-bias ${idea.bias==='롱'?'long':idea.bias==='숏'?'short':''}`}>{idea.bias}</span>
    </div>
    <div className="idea-body">
      <div className="idea-meta"><span><b>{idea.user || 'TradingView'}</b>의</span><time>{idea.time}</time></div>
      <h3>{idea.title}</h3>
      <div className={detailOpen?'tv-full-text open':'tv-full-text'}>
        {visibleText.split('\n').map((line,i)=>line.trim()?<p key={i}>{line}</p>:<br key={i}/>)}
      </div>
      {detailOpen && detail?.content_images?.length ? <div className="tv-inline-images">
        {detail.content_images.map((src,i)=><img src={src} alt={`${idea.title} chart ${i+1}`} loading="lazy" key={src+i}/>)}
      </div> : null}
      <div className="idea-bottom">
        <span>💬 {idea.comments}</span><span>TradingView 원본 수집 <b>LIVE</b></span>
      </div>
      <div className="idea-actions">
        <button onClick={loadDetail} disabled={detailLoading}>{detailLoading?'전체 원본 수집 중':detailOpen?'전체내용 접기':'이미지·본문·차트 전체 보기'}</button>
        <button disabled={busy} onClick={saveCandidate}>{candidateId?'전략 후보 저장됨':'전략 후보로 저장'}</button>
        <button disabled={busy} onClick={makeAgents}>{agentCount!==null?`통과 Agent ${agentCount}개`:'Discovery 후 Agent 생성'}</button>
      </div>
      {status && <p className="note">{status}</p>}
      {idea.chartUrl && <small className="source-ref">출처 URL 보존: {idea.chartUrl}</small>}
    </div>
  </article>;
}

function TradingViewIdeas(){
  const [topTab,setTopTab]=useState<'popular'|'editors'>('popular');
  const [ideaType,setIdeaType]=useState('모든 아이디어');
  const [video,setVideo]=useState(false);
  const [sort,setSort]=useState<'recent'|'popular'>('recent');
  const [cards,setCards]=useState<IdeaCardData[]>([]);
  const [loading,setLoading]=useState(true);
  const [loadError,setLoadError]=useState('');

  useEffect(()=>{
    const controller=new AbortController();
    const sortParam=topTab==='editors'?'picked_time':sort==='recent'?'recent':'trending';
    setLoading(true);
    setLoadError('');
    fetch(`${API_BASE}/api/v1/tradingview/ideas/live?sort=${sortParam}&page=1&lang=ko`,{signal:controller.signal})
      .then(async r=>{
        if(!r.ok) throw new Error(await r.text());
        return r.json();
      })
      .then(data=>{
        const rows=(data.items||[]) as LiveIdeaResponseItem[];
        setCards(rows.map(x=>{
          const dt=x.created_at ? new Date(x.created_at) : null;
          const time=dt && !Number.isNaN(dt.getTime()) ? dt.toLocaleString('ko-KR') : (x.created_at||'');
          return {
            id:x.idea_id,
            user:x.author,
            time,
            title:x.title,
            text:x.description,
            symbol:[x.exchange,x.symbol].filter(Boolean).join(':') || x.symbol,
            bias:x.direction || '중립',
            comments:x.comments_count||0,
            market:[x.asset_type,x.interval].filter(Boolean).join(' · '),
            chartUrl:x.chart_url,
            imageUrl:x.image_url,
            isVideo:Boolean(x.is_video),
            isEducation:Boolean(x.is_education),
            isPicked:Boolean(x.is_picked),
          };
        }));
      })
      .catch(e=>{
        if(e?.name!=='AbortError') setLoadError('TradingView 아이디어 실수집 연결 오류');
      })
      .finally(()=>setLoading(false));
    return ()=>controller.abort();
  },[topTab,sort]);

  const filteredCards=cards.filter(x=>{
    if(video && !x.isVideo) return false;
    if(ideaType==='교육 아이디어' && !x.isEducation) return false;
    if(ideaType==='트레이딩 아이디어' && x.isEducation) return false;
    return true;
  });

  return <>
    <TradingViewHeader active="ideas"/>
    <div className="tv-page">
      <h1>커뮤니티 아이디어</h1>
      <div className="tv-primary-tabs">
        <button className={topTab==='popular'?'active':''} onClick={()=>setTopTab('popular')}>포퓰러</button>
        <button className={topTab==='editors'?'active':''} onClick={()=>setTopTab('editors')}>에디터즈 픽</button>
      </div>
      <div className="tv-filterbar">
        <select value={ideaType} onChange={e=>setIdeaType(e.target.value)}>
          <option>모든 아이디어</option><option>트레이딩 아이디어</option><option>교육 아이디어</option>
        </select>
        <button className={video?'active':''} onClick={()=>setVideo(v=>!v)}>비디오 온리</button>
        <span className="spacer"/>
        <button className={sort==='recent'?'active':''} onClick={()=>setSort('recent')}>가장 최근</button>
        <button className={sort==='popular'?'active':''} onClick={()=>setSort('popular')}>가장 인기 있는</button>
      </div>
      {loading && <div className="panel"><span>TradingView 공개 아이디어를 실시간 수집 중입니다.</span></div>}
      {loadError && <div className="panel"><span>{loadError}</span></div>}
      {!loading && !loadError && filteredCards.length>0 && <div className="tv-idea-grid">{filteredCards.map(x=><IdeaCard key={x.id} idea={x}/>)}</div>}
      {!loading && !loadError && filteredCards.length===0 && <div className="panel"><span>현재 페이지에서 선택한 실제 TradingView 필터 조건에 맞는 아이디어가 없습니다.</span></div>}
      <div className="tv-pagination"><button className="active">1</button><button>2</button><button>3</button><span>…</span><button>50</button><button>발행물 더 보기</button></div>
      <div className="panel tv-ai-extension">
        <div className="panel-title"><b>우리 시스템 연결 기능</b><span>TradingView 아이디어 → 구조화 전략 → 시장/종목 매칭 → 고정 시간축 독립 에이전트</span></div>
        <div className="grid three">
          <MiniStat title="현재 실수집" lines={[`원본 ${cards.length}건 · 필터 결과 ${filteredCards.length}건`,topTab==='editors'?'에디터즈 픽':'포퓰러',video?'비디오 온리':ideaType]}/>
          <MiniStat title="전략 후보화" lines={['원본 Source ID 영구 보존','자동 전략 유형 분류','후보 시간축 분리']}/>
          <MiniStat title="에이전트 불변식" lines={['Origin Source 불변','Fixed Horizon 불변','시장 Universe별 독립 성과']}/>
        </div>
      </div>
    </div>
  </>;
}

type MarketTab='한국 주식'|'세계 주식'|'크립토'|'선물'|'외환'|'국채'|'회사채'|'ETFs'|'경제'|'지수';

const marketTabs:MarketTab[]=['한국 주식','세계 주식','크립토','선물','외환','국채','회사채','ETFs','경제','지수'];

const marketData:Record<MarketTab,{sections:{title:string;subtitle:string;items:[string,string,string][];links?:string[]}[]}> = {
  '한국 주식':{sections:[
    {title:'지수',subtitle:'한국 주요 지수',items:[['KOSPI','4,021.18','+0.62%'],['KOSPI 200','538.42','+0.48%'],['KOSDAQ','891.25','-0.17%']]},
    {title:'한국 주식',subtitle:'대표 종목',items:[['삼성전자','005930','+1.12%'],['SK하이닉스','000660','+2.06%'],['현대자동차','005380','-0.31%']]},
    {title:'커뮤니티 트렌드',subtitle:'커뮤니티에서 많이 보는 심볼',items:[['KB금융','105560','+0.42%'],['한국전력','015760','+1.71%'],['POSCO홀딩스','005490','-0.52%']]},
    {title:'거래량이 가장 많은 주식',subtitle:'활발한 종목',items:[['빅텍','065450','+9.5%'],['세아메카닉스','396300','+6.2%'],['폴라리스에이아이','039980','+4.8%']],links:['가장 활발하게 거래되는 모든 종목 보기']},
    {title:'가장 변동성이 높은 주식',subtitle:'당일 변동성',items:[['컨텍','451760','+18.2%'],['에스제이켐','217910','-14.4%'],['판도라티비','202960','+12.1%']]},
    {title:'상승주 / 하락주',subtitle:'일일 등락 상하위',items:[['상승주','전체 보기','+'],['하락주','전체 보기','-']]},
    {title:'실적 캘린더',subtitle:'실제 / 예상 EPS',items:[['현대자동차','오늘','예상 8,192 KRW'],['우리금융지주','오늘','예상 1,307 KRW']]},
    {title:'IPO 캘린더',subtitle:'예정 상장 일정',items:[['신규 상장','일정','공모가']]},
  ]},
  '세계 주식':{sections:[
    {title:'세계 주식',subtitle:'글로벌 대표 기업',items:[['Microsoft','MSFT','+0.8%'],['TSMC','TSM','+1.4%'],['LVMH','MC','-0.3%']]},
    {title:'세계 최대 기업',subtitle:'시가총액 기준',items:[['NVIDIA','NVDA','5.11T USD'],['Apple','AAPL','5.08T USD'],['Alphabet','GOOG','3.95T USD']]},
    {title:'세계 최대 고용주',subtitle:'직원 수 기준',items:[['Walmart','WMT','2.1M'],['Amazon','AMZN','1.6M'],['BYD','002594','869.6K']]},
    {title:'실적 캘린더',subtitle:'글로벌 실적 일정',items:[['대형주 실적','오늘','예정']]},
    {title:'IPO 캘린더',subtitle:'글로벌 신규 상장',items:[['IPO 일정','이번주','예정']]},
  ]},
  '크립토':{sections:[
    {title:'크립토',subtitle:'주요 암호화폐',items:[['Bitcoin','BTCUSD','+2.1%'],['Ethereum','ETHUSD','+1.4%'],['XRP','XRPUSD','-0.6%']]},
    {title:'커뮤니티 트렌드',subtitle:'인기 심볼',items:[['ETHUSD','Ethereum','인기'],['SOLUSD','Solana','인기'],['BTCUSDT','Bitcoin / Tether','인기']]},
    {title:'암호화폐 시가총액 랭킹',subtitle:'시가총액',items:[['Bitcoin','BTC','1.63T'],['Ethereum','ETH','291.4B'],['Tether','USDT','182.5B']]},
    {title:'TVL 랭킹',subtitle:'잠긴 가치 기준',items:[['Aave','AAVE','30.93B'],['Lido DAO','LDO','23.69B'],['Uniswap','UNI','4.13B']]},
    {title:'크립토 승자 / 패자',subtitle:'일일 등락 상하위',items:[['상승','MemeCore','+15.93%'],['하락','Pons','-12.4%']]},
  ]},
  '선물':{sections:[
    {title:'선물 및 원자재',subtitle:'대표 선물',items:[['금','GC','+0.8%'],['원유','CL','-1.2%'],['S&P 500','ES','+0.3%']]},
    {title:'에너지 선물',subtitle:'원유·가스',items:[['경질 원유','CL','-1.2%'],['천연가스','NG','+2.0%'],['브렌트','BRN','-0.9%']]},
    {title:'농산물 선물',subtitle:'농산물',items:[['커피','KC','+1.1%'],['대두','ZS','-0.4%'],['옥수수','ZC','+0.2%']]},
    {title:'금속 선물',subtitle:'귀금속·산업금속',items:[['금','GC','+0.8%'],['은','SI','+1.3%'],['구리','HG','+0.5%']]},
    {title:'지수 선물',subtitle:'주가지수 선물',items:[['KOSPI200','101','+0.4%'],['NASDAQ 100','NQ','+0.6%'],['S&P 500','ES','+0.3%']]},
  ]},
  '외환':{sections:[
    {title:'외환 및 통화',subtitle:'원화 환율',items:[['USD/KRW','USDKRW','-0.31%'],['EUR/KRW','EURKRW','+0.12%'],['JPY/KRW','JPYKRW','-0.08%']]},
    {title:'주요 통화쌍',subtitle:'글로벌 FX',items:[['EUR/USD','EURUSD','+0.21%'],['USD/JPY','USDJPY','-0.34%'],['GBP/USD','GBPUSD','+0.18%']]},
    {title:'통화 지수',subtitle:'통화 강도 지수',items:[['미국 달러 지수','DXY','-0.22%'],['유로 지수','EXY','+0.19%'],['엔 지수','JXY','+0.33%']]},
  ]},
  '국채':{sections:[
    {title:'수익률 곡선',subtitle:'국가별 만기 구조',items:[['대한민국','KR','3Y / 10Y'],['미국','US','2Y / 10Y'],['일본','JP','2Y / 10Y']]},
    {title:'대한민국 채권',subtitle:'국고채 수익률',items:[['KR01Y','1년','2.81%'],['KR03Y','3년','3.02%'],['KR10Y','10년','3.31%']]},
    {title:'주요 10년물 채권',subtitle:'글로벌 벤치마크',items:[['미국','US10Y','4.21%'],['독일','DE10Y','2.76%'],['일본','JP10Y','1.54%']]},
  ]},
  '회사채':{sections:[
    {title:'회사채',subtitle:'기업 채권',items:[['회사채 A','2031-10','5.4%'],['회사채 B','2034-03','4.9%'],['회사채 C','2030-06','6.1%']]},
    {title:'최고 수익률',subtitle:'수익률 상위',items:[['고수익 1','단기','8.2%'],['고수익 2','장기','7.7%']]},
    {title:'만기 / 금리 유형',subtitle:'세부 분류',items:[['단기','Short-Term','보기'],['장기','Long-Term','보기'],['변동금리','Floating','보기'],['고정 금리','Fixed','보기']]},
  ]},
  'ETFs':{sections:[
    {title:'ETFs',subtitle:'대표 ETF',items:[['SPDR S&P 500','SPY','+0.4%'],['Invesco QQQ','QQQ','+0.7%'],['iShares Bitcoin','IBIT','+2.1%']]},
    {title:'가장 많이 거래된',subtitle:'거래대금/거래량',items:[['SOXL','반도체 3x','활발'],['IWM','Russell 2000','활발'],['SOXX','반도체','활발']]},
    {title:'가장 높은 AUM 성장률',subtitle:'자산 유입 성장',items:[['RINK','ETF','높음'],['DACU','ETF','높음']]},
    {title:'최고 수익률',subtitle:'성과 상위',items:[['반도체 ETF','테마','+'],['레버리지 ETF','테마','+']]},
    {title:'가장 높은 배당 수익률',subtitle:'배당률 상위',items:[['YieldMax','MSTR','고배당'],['YieldMax','COIN','고배당']]},
  ]},
  '경제':{sections:[
    {title:'한국 경제',subtitle:'주요 경제지표',items:[['GDP','대한민국','2.4%'],['기준금리','대한민국','2.50%'],['물가상승률','대한민국','2.1%'],['실업률','대한민국','3.0%']]},
    {title:'경제 지표 히트맵',subtitle:'국가 × 지표',items:[['미국','GDP / 금리 / 물가','보기'],['중국','GDP / 금리 / 물가','보기'],['대한민국','GDP / 금리 / 물가','보기']]},
    {title:'글로벌 인플레이션 맵',subtitle:'국가별 물가 비교',items:[['글로벌','Inflation','지도 보기']]},
  ]},
  '지수':{sections:[
    {title:'주요 지수',subtitle:'전세계 주요 지수',items:[['KOSPI','KOSPI','+0.62%'],['S&P 500','SPX','+0.41%'],['NASDAQ 100','NDX','+0.66%'],['Nikkei 225','NI225','-0.20%']]},
    {title:'한국 지수',subtitle:'한국 시장',items:[['KOSPI 50','KOSPI50','+0.4%'],['KOSPI 200','KOSPI200','+0.5%'],['KOSDAQ 150','KQ150','-0.1%']]},
    {title:'전세계 인덱스',subtitle:'지역별',items:[['DAX','독일','+0.2%'],['FTSE 100','영국','-0.1%'],['HSI','홍콩','+0.8%']]},
  ]},
};

function MiniMarketChart({positive=true}:{positive?:boolean}) {
  return <svg viewBox="0 0 180 52" className={positive?'mini-market-chart positive':'mini-market-chart negative'}>
    <path d="M1 40 C20 37 27 23 43 29 S68 40 82 25 S108 13 122 20 S151 9 179 12" fill="none" stroke="currentColor" strokeWidth="2"/>
  </svg>;
}

function MarketCard({item}:{item:[string,string,string]}) {
  const positive=!String(item[2]).startsWith('-');
  return <div className="market-card">
    <div><b>{item[0]}</b><small>{item[1]}</small></div>
    <MiniMarketChart positive={positive}/>
    <span className={positive?'txt-green':'txt-red'}>{item[2]}</span>
    <div className="market-card-actions"><button>차트</button><button>아이디어</button><button>전략추천</button></div>
  </div>;
}

function MarketSection({title,subtitle,items,links}:{title:string;subtitle:string;items:[string,string,string][];links?:string[]}) {
  return <section className="tv-market-section">
    <div className="market-section-head"><div><h2>{title}</h2><p>{subtitle}</p></div><button>모두 보기 →</button></div>
    <div className="market-card-grid">{items.map((x,i)=><MarketCard item={x} key={title+i}/>)}</div>
    {links?.map(x=><button className="market-more" key={x}>{x} →</button>)}
  </section>;
}

type LiveMarketRow = {
  ticker?:string;
  name?:string;
  description?:string;
  close?:number | string | null;
  change?:number | string | null;
  volume?:number | string | null;
  'Volatility.D'?:number | string | null;
  relative_volume_10d_calc?:number | string | null;
  RSI?:number | string | null;
  ATR?:number | string | null;
  ADX?:number | string | null;
  'Recommend.All'?:number | string | null;
  market_cap_basic?:number | string | null;
  market_cap_calc?:number | string | null;
  sector?:string | null;
  exchange?:string;
  type?:string;
};

const liveMarketCode:Partial<Record<MarketTab,string>> = {
  '한국 주식':'korea',
  '세계 주식':'america',
  '크립토':'crypto',
  '외환':'forex',
};

const marketViews:Partial<Record<MarketTab,string[]>> = {
  '한국 주식':['개요','거래량 상위','변동성 상위','상승주','하락주','실적 캘린더','IPO 캘린더'],
  '세계 주식':['개요','시총 상위','거래량 상위','변동성 상위','상승주','하락주'],
  '크립토':['개요','거래량 상위','변동성 상위','상승주','하락주','TVL'],
  '외환':['개요','거래량 상위','변동성 상위','상승주','하락주','통화지수'],
};

function scannerSortForView(view:string,tab:MarketTab):{sortBy:string;sortOrder:'asc'|'desc'} {
  if(view==='변동성 상위') return {sortBy:'Volatility.D',sortOrder:'desc'};
  if(view==='상승주') return {sortBy:'change',sortOrder:'desc'};
  if(view==='하락주') return {sortBy:'change',sortOrder:'asc'};
  if(view==='시총 상위') return {sortBy:tab==='크립토'?'market_cap_calc':'market_cap_basic',sortOrder:'desc'};
  return {sortBy:'volume',sortOrder:'desc'};
}

function TradingViewMarkets(){
  const [tab,setTab]=useState<MarketTab>('한국 주식');
  const [marketView,setMarketView]=useState('개요');
  const [liveRows,setLiveRows]=useState<LiveMarketRow[]>([]);
  const [liveTotal,setLiveTotal]=useState<number | null>(null);
  const [liveCollectedAt,setLiveCollectedAt]=useState('');
  const [liveError,setLiveError]=useState('');
  const data=marketData[tab];

  useEffect(()=>{
    setMarketView('개요');
  },[tab]);

  useEffect(()=>{
    const code=liveMarketCode[tab];
    const sort=scannerSortForView(marketView,tab);
    const supported=marketView!=='실적 캘린더' && marketView!=='IPO 캘린더' && marketView!=='TVL' && marketView!=='통화지수';
    if(!code || !supported){
      setLiveRows([]);
      setLiveTotal(null);
      setLiveCollectedAt('');
      setLiveError('');
      return;
    }
    const controller=new AbortController();
    const params=new URLSearchParams({
      limit:'50',
      sort_by:sort.sortBy,
      sort_order:sort.sortOrder,
    });
    setLiveError('');
    fetch(API_BASE+'/api/v1/tradingview/markets/'+code+'?'+params.toString(),{signal:controller.signal})
      .then(async r=>{
        if(!r.ok) throw new Error(await r.text());
        return r.json();
      })
      .then(res=>{
        setLiveRows((res.items||[]) as LiveMarketRow[]);
        setLiveTotal(typeof res.total_count==='number'?res.total_count:null);
        setLiveCollectedAt(res.collected_at||'');
      })
      .catch(e=>{
        if(e?.name!=='AbortError') setLiveError('TradingView Scanner 실데이터 연결 오류');
      });
    return ()=>controller.abort();
  },[tab,marketView]);

  const liveTableRows=liveRows.map(x=>[
    x.ticker || x.name || '',
    x.description || '',
    x.close===null || x.close===undefined ? '' : Number(x.close).toLocaleString('ko-KR'),
    x.change===null || x.change===undefined ? '' : Number(x.change).toFixed(2)+'%',
    x.volume===null || x.volume===undefined ? '' : Number(x.volume).toLocaleString('ko-KR'),
    x['Volatility.D']===null || x['Volatility.D']===undefined ? '' : Number(x['Volatility.D']).toFixed(2)+'%',
    x.relative_volume_10d_calc===null || x.relative_volume_10d_calc===undefined ? '' : Number(x.relative_volume_10d_calc).toFixed(2),
    x.RSI===null || x.RSI===undefined ? '' : Number(x.RSI).toFixed(1),
    x.exchange || '',
  ]);

  const views=marketViews[tab]||[];
  const scannerSupported=Boolean(liveMarketCode[tab]) && !['실적 캘린더','IPO 캘린더','TVL','통화지수'].includes(marketView);

  return <>
    <TradingViewHeader active="markets"/>
    <div className="tv-page markets-page">
      <div className="market-hero">
        <div><span>마켓</span><h1>{tab}</h1><p>시장 탐색 데이터가 전략 적합도·Universe 구성·에이전트 생성으로 직접 연결됩니다.</p></div>
        <div className="market-clock"><b>실시간 시장 탐색</b><span>TradingView Scanner + 15분 자동 적재</span></div>
      </div>
      <div className="market-tabs">{marketTabs.map(x=><button className={tab===x?'active':''} key={x} onClick={()=>setTab(x)}>{x}</button>)}</div>
      <div className="market-submenu">
        {views.length>0 ? views.map(x=><button key={x} className={marketView===x?'active':''} onClick={()=>setMarketView(x)}>{x}</button>) :
          <>
            {tab==='선물' && <><button className="active">개요</button><button>에너지</button><button>농산물</button><button>금속</button><button>지수</button><button>통화</button></>}
            {tab==='국채' && <><button className="active">개요</button><button>미국</button><button>유럽</button><button>아시아</button><button>수익률곡선</button></>}
            {tab==='회사채' && <><button className="active">개요</button><button>등급별</button><button>만기별</button><button>수익률</button></>}
            {tab==='ETFs' && <><button className="active">개요</button><button>랭킹</button><button>자산군</button><button>섹터</button><button>국가</button></>}
            {tab==='경제' && <><button className="active">개요</button><button>경제지표</button><button>캘린더</button><button>국가</button></>}
            {tab==='지수' && <><button className="active">개요</button><button>주요 지수</button><button>지역별</button><button>섹터 지수</button></>}
          </>}
      </div>

      {liveMarketCode[tab] && scannerSupported && <div className="panel">
        <div className="panel-title">
          <b>TradingView Scanner · {marketView}</b>
          <span>{liveTotal===null?'실시간 조회':('전체 '+liveTotal.toLocaleString('ko-KR')+'개 · 현재 50개')} {liveCollectedAt?'· DB 스냅샷 저장':''}</span>
        </div>
        {liveError ? <div className="empty-state">{liveError}</div> :
          <DataTable headers={['티커','종목','현재가','등락률','거래량','일변동성','상대거래량','RSI','거래소']} rows={liveTableRows}/>}
      </div>}

      {liveMarketCode[tab] && !scannerSupported && <div className="panel">
        <div className="panel-title"><b>{marketView}</b><span>TradingView의 해당 전용 데이터 소스 연결 대상</span></div>
        <div className="empty-state">이 메뉴는 주식/FX Scanner가 아닌 별도 캘린더·랭킹 데이터 소스로 연결합니다. 가짜 숫자는 표시하지 않습니다.</div>
      </div>}

      {!liveMarketCode[tab] && <div className="panel">
        <div className="panel-title"><b>{tab} 실데이터 연결 상태</b><span>TradingView 원본 메뉴 구조는 유지</span></div>
        <div className="empty-state">이 자산군의 전용 TradingView 데이터 소스는 아직 백엔드에 연결하지 않았습니다. 예시·가상 시세는 표시하지 않습니다.</div>
      </div>}
      <div className="panel market-match-panel">
        <div className="panel-title"><b>{tab} 전략 매칭 입력 데이터</b><span>현재 실수집 피처를 실제 백테스트·Walk-forward 평가 엔진으로 전달</span></div>
        <DataTable headers={['입력 피처','용도','현재 상태']} rows={[
          ['거래량 · 상대거래량','유동성/체결 가능 Universe 선별','실수집·DB 저장'],
          ['일변동성 · ATR','전략별 변동성 레짐 및 손절/포지션 크기','실수집·DB 저장'],
          ['RSI · ADX · TradingView Recommendation','평균회귀/추세/모멘텀 사전 레짐 분류','실수집·DB 저장'],
          ['시장 × 전략 × 고정 시간축','Walk-forward 및 Holdout 적합도 산출','다음 Quant 평가 단계'],
        ]}/>
        <p className="note">검증되지 않은 92점·89점 같은 예시 적합도는 제거했습니다. 실제 적합도는 백테스트와 Holdout 결과가 생성된 뒤에만 표시합니다.</p>
      </div>
    </div>
  </>;
}

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

type LivePineStrategy = {
  script_id_part:string;
  script_id:string;
  name:string;
  author:string;
  script_type:string;
  script_access:number;
  version:string;
  likes_count:number;
  comments_count:number;
  views_count:number;
  created_at:string;
  updated_at:string;
  chart_url?:string | null;
  image_url?:string | null;
  symbol:string;
  interval:string;
  is_picked:number | boolean;
  is_hot:number | boolean;
  description:string;
};

type LiveStrategyCandidate = {
  candidate_id:string;
  source_kind:string;
  source_id:string;
  source_version?:string | null;
  source_hash?:string | null;
  name:string;
  author?:string | null;
  category:string;
  domain:string;
  logic:string;
  candidate_horizons:string[];
  status:string;
  origin_source_immutable:boolean;
};

type LiveHorizonDiscovery = {
  discovery_id:string;
  candidate_id:string;
  registry_source_id:string;
  source_id:string;
  origin_source_id:string;
  horizon:string;
  country:string;
  market:string;
  universe:string;
  scanner_market?:string | null;
  fit_score:number;
  market_score:number;
  horizon_score:number;
  source_score:number;
  status:string;
  rationale:string;
  evaluated_at:string;
};

type LiveAgentPlan = {
  agent_id:string;
  candidate_id:string;
  source_id:string;
  registry_source_id?:string;
  origin_source_id?:string;
  origin_source_immutable:boolean;
  fixed_horizon:string;
  fixed_horizon_immutable:boolean;
  country:string;
  market:string;
  universe:string;
  discovery_fit_score?:number;
  status:string;
};

type AgentResearchState = {
  loading:boolean;
  universeCount?:number;
  symbols?:string[];
  experimentId?:string;
  status?:string;
  reason?:string | null;
};

function TradingViewStrategies(){
  const topics=[
    {label:'전체',slug:''},
    {label:'추세추종',slug:'trend-following'},
    {label:'평균회귀',slug:'mean-reversion'},
    {label:'돌파',slug:'breakout'},
    {label:'모멘텀',slug:'momentum'},
    {label:'변동성',slug:'volatility'},
    {label:'스캘핑',slug:'scalping'},
    {label:'에디터즈 픽',slug:'editors-picks'},
  ];
  const [topic,setTopic]=useState('');
  const [sort,setSort]=useState<'latest_popular'|'recent_extended'>('latest_popular');
  const [page,setPage]=useState(1);
  const [scripts,setScripts]=useState<LivePineStrategy[]>([]);
  const [total,setTotal]=useState<number | null>(null);
  const [selected,setSelected]=useState('');
  const [candidate,setCandidate]=useState<LiveStrategyCandidate | null>(null);
  const [scriptDetail,setScriptDetail]=useState<LiveSourceDetail | null>(null);
  const [pineSource,setPineSource]=useState<LivePineSource | null>(null);
  const [detailLoading,setDetailLoading]=useState(false);
  const [discovery,setDiscovery]=useState<LiveHorizonDiscovery[]>([]);
  const [agents,setAgents]=useState<LiveAgentPlan[]>([]);
  const [agentResearch,setAgentResearch]=useState<Record<string,AgentResearchState>>({});
  const [loading,setLoading]=useState(true);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');

  const editors=topic==='editors-picks';
  useEffect(()=>{
    const controller=new AbortController();
    const params=new URLSearchParams({
      page:String(page),
      sort,
      editors_picks:String(editors),
    });
    if(topic && !editors) params.set('topic',topic);
    setLoading(true);
    setError('');
    fetch(API_BASE+'/api/v1/tradingview/scripts/live?'+params.toString(),{signal:controller.signal})
      .then(async r=>{
        if(!r.ok) throw new Error(await r.text());
        return r.json();
      })
      .then(data=>{
        const rows=(data.items||[]) as LivePineStrategy[];
        setScripts(rows);
        setTotal(typeof data.total_count==='number'?data.total_count:null);
        setSelected(prev=>rows.some(x=>x.script_id_part===prev)?prev:(rows[0]?.script_id_part||''));
      })
      .catch(e=>{
        if(e?.name!=='AbortError') setError('TradingView 공개 전략 수집 연결 오류');
      })
      .finally(()=>setLoading(false));
    return ()=>controller.abort();
  },[topic,sort,page,editors]);

  const current=scripts.find(x=>x.script_id_part===selected) ?? scripts[0] ?? null;

  useEffect(()=>{
    setCandidate(null);
    setScriptDetail(null);
    setPineSource(null);
    setDiscovery([]);
    setAgents([]);
    setAgentResearch({});
  },[selected]);

  useEffect(()=>{
    if(!current?.script_id_part) return;
    let cancelled=false;
    setDetailLoading(true);
    Promise.allSettled([
      fetch(API_BASE+'/api/v1/tradingview/scripts/'+encodeURIComponent(current.script_id_part)+'/full').then(async r=>{
        if(!r.ok) throw new Error(await r.text());
        return r.json();
      }),
      fetch(API_BASE+'/api/v1/tradingview/scripts/'+encodeURIComponent(current.script_id_part)+'/source').then(async r=>{
        if(!r.ok) throw new Error(await r.text());
        return r.json();
      }),
    ]).then(results=>{
      if(cancelled) return;
      if(results[0].status==='fulfilled') setScriptDetail(results[0].value as LiveSourceDetail);
      if(results[1].status==='fulfilled') setPineSource(results[1].value as LivePineSource);
    }).finally(()=>{if(!cancelled) setDetailLoading(false);});
    return ()=>{cancelled=true;};
  },[current?.script_id_part]);

  const analyze=async():Promise<LiveStrategyCandidate | null>=>{
    if(!current) return null;
    if(candidate && candidate.source_id===current.script_id_part) return candidate;
    setBusy(true);
    setError('');
    try{
      const r=await fetch(API_BASE+'/api/v1/tradingview/scripts/'+encodeURIComponent(current.script_id_part)+'/candidate?fetch_source=true',{method:'POST'});
      if(!r.ok) throw new Error(await r.text());
      const data=await r.json() as LiveStrategyCandidate;
      setCandidate(data);
      return data;
    }catch(e){
      setError('Pine 전략 원문 분석 또는 후보 생성 오류');
      return null;
    }finally{
      setBusy(false);
    }
  };

  const discoverHorizons=async():Promise<LiveHorizonDiscovery[]>=>{
    const c=await analyze();
    if(!c) return [];
    setBusy(true);
    setError('');
    try{
      const r=await fetch(API_BASE+'/api/v1/horizon-discovery/'+encodeURIComponent(c.candidate_id)+'?max_markets=3',{method:'POST'});
      if(!r.ok) throw new Error(await r.text());
      const data=await r.json();
      const rows=(data.items||[]) as LiveHorizonDiscovery[];
      setDiscovery(rows);
      return rows;
    }catch(e){
      setError('시장·시간축 사전 적합도 분석 오류');
      return [];
    }finally{
      setBusy(false);
    }
  };

  const makeAgents=async()=>{
    const c=await analyze();
    if(!c) return;
    let rows=discovery;
    if(!rows.length) rows=await discoverHorizons();
    if(!rows.length) return;
    setBusy(true);
    setError('');
    try{
      const r=await fetch(API_BASE+'/api/v1/agent-factory/'+encodeURIComponent(c.candidate_id)+'?min_score=72&max_agents=12',{method:'POST'});
      if(!r.ok) throw new Error(await r.text());
      const data=await r.json();
      setAgents((data.items||[]) as LiveAgentPlan[]);
    }catch(e){
      setError('Discovery 통과 조합의 에이전트 생성 오류');
    }finally{
      setBusy(false);
    }
  };

  const prepareResearch=async(agent:LiveAgentPlan)=>{
    setAgentResearch(prev=>({...prev,[agent.agent_id]:{loading:true,status:'UNIVERSE_RESOLVING'}}));
    try{
      const u=await fetch(
        API_BASE+'/api/v1/tradingview/agent-plans/'+encodeURIComponent(agent.agent_id)+'/resolve-universe?limit=20',
        {method:'POST'}
      );
      if(!u.ok) throw new Error(await u.text());
      const universe=await u.json();
      const explicitUniverse=universe.method==='EXPLICIT_SOURCE_UNIVERSE';
      const symbols=((universe.items||[]) as Array<{ticker:string}>)
        .map(x=>{
          const ticker=x.ticker||'';
          return explicitUniverse ? ticker : (ticker.split(':').pop()||'');
        })
        .filter(Boolean);

      const e=await fetch(
        QUANT_API_BASE+'/api/v1/quant/experiments/from-agent/'+encodeURIComponent(agent.agent_id),
        {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body:JSON.stringify({symbols})
        }
      );
      if(!e.ok) throw new Error(await e.text());
      const experiment=await e.json();
      setAgentResearch(prev=>({...prev,[agent.agent_id]:{
        loading:false,
        universeCount:universe.count||symbols.length,
        symbols,
        experimentId:experiment.experiment_id,
        status:experiment.status,
        reason:experiment.blocked_reason,
      }}));
    }catch(err){
      setAgentResearch(prev=>({...prev,[agent.agent_id]:{
        loading:false,
        status:'ERROR',
        reason:err instanceof Error?err.message:'연구 준비 오류',
      }}));
    }
  };

  const discoveryRows=discovery.map(x=>[
    x.country,
    x.market,
    x.universe,
    x.horizon,
    x.fit_score.toFixed(1)+'점',
    x.status,
  ]);

  const matchRows=agents.map(x=>[
    x.country,
    x.market,
    x.universe,
    x.fixed_horizon,
    x.discovery_fit_score==null?'—':x.discovery_fit_score.toFixed(1)+'점',
    x.agent_id,
    x.status,
  ]);

  return <>
    <SectionHeader title="트레이딩뷰 전략 전체 관리" eyebrow="TradingView Community Scripts의 공개 전략을 실수집해 원천 계보·시장·고정 시간축별 독립 에이전트로 전환" actions={['실시간 전략 수집','원천 분석','에이전트 생성']} />

    <div className="metrics five">
      <Metric label="TradingView 전체 결과" value={total===null?'—':total.toLocaleString('ko-KR')} sub="현재 필터 기준" />
      <Metric label="현재 페이지" value={String(scripts.length)} sub={page+'페이지 · 공개 전략'} tone="green" />
      <Metric label="원천 유형" value="Pine" sub="Open Source Strategy" tone="cyan" />
      <Metric label="선택 전략 반응" value={current?current.likes_count.toLocaleString('ko-KR'):'—'} sub="좋아요" />
      <Metric label="생성 에이전트" value={String(agents.length)} sub="Source × Market × Fixed Horizon" tone={agents.length?'green':'muted'} />
    </div>

    <div className="callout">
      <b>불변 원칙</b>
      <span>원천 TradingView Script ID와 각 Agent의 거래·예측 시간축은 생성 후 변경하지 않습니다. 같은 전략 원천이라도 시장·종목군·시간축이 다르면 별도의 독립 Agent ID, 메모리, 성과, 실패이력과 리스크 예산을 가집니다.</span>
    </div>

    <div className="subnav strategy-categories">
      {topics.map(x=><button key={x.label} className={topic===x.slug?'active':''} onClick={()=>{setTopic(x.slug);setPage(1)}}>{x.label}</button>)}
      <span className="spacer"/>
      <button className={sort==='latest_popular'?'active':''} onClick={()=>{setSort('latest_popular');setPage(1)}}>인기 전략</button>
      <button className={sort==='recent_extended'?'active':''} onClick={()=>{setSort('recent_extended');setPage(1)}}>최신 전략</button>
    </div>

    {error && <div className="panel"><span>{error}</span></div>}

    <div className="grid two tv-library-grid">
      <div className="panel">
        <div className="panel-title"><b>TradingView 공개 전략 보관함</b><span>{loading?'실수집 중':scripts.length+'개 표시 · '+page+'페이지'}</span></div>
        {loading ? <div className="empty-state">TradingView Community Scripts에서 공개 전략을 읽는 중입니다.</div> :
        <div className="tv-list">
          {scripts.map(x=><button key={x.script_id_part} className={selected===x.script_id_part?'tv-row selected':'tv-row'} onClick={()=>setSelected(x.script_id_part)}>
            <span className="tv-id">{x.script_id_part.replace('PUB;','')}</span>
            <span className="tv-name"><b>{x.name}</b><small>{x.author} · 좋아요 {x.likes_count.toLocaleString('ko-KR')}</small></span>
            <span><Badge tone={x.is_picked?'green':'purple'}>{x.is_picked?'에디터즈 픽':'공개 전략'}</Badge></span>
            <span className="tv-domain">{x.symbol || '전 종목'} {x.interval?'· '+x.interval:''}</span>
            <span className="tv-score"><b>{x.version || '—'}</b><small>버전</small></span>
          </button>)}
        </div>}
        <div className="tv-pagination">
          <button disabled={page<=1} onClick={()=>setPage(p=>Math.max(1,p-1))}>이전</button>
          <button className="active">{page} / {total?Math.max(1,Math.ceil(total/24)):'?'}</button>
          <button disabled={Boolean(total && page>=Math.ceil(total/24))} onClick={()=>setPage(p=>p+1)}>다음</button>
        </div>
      </div>

      <div className="panel">
        {current ? <>
          <div className="panel-title"><b>{current.name}</b><Badge tone="green">Open Source</Badge></div>
          <dl className="kv">
            <dt>TradingView 원천 ID</dt><dd>{current.script_id_part}</dd>
            <dt>작성자</dt><dd>{current.author || '—'}</dd>
            <dt>버전</dt><dd>{current.version || '—'}</dd>
            <dt>게시 시간축</dt><dd>{current.interval || '미지정'}</dd>
            <dt>좋아요 / 댓글 / 조회</dt><dd>{current.likes_count.toLocaleString('ko-KR')} / {current.comments_count.toLocaleString('ko-KR')} / {current.views_count.toLocaleString('ko-KR')}</dd>
            <dt>자동 분류</dt><dd>{candidate?candidate.category+' → '+candidate.domain:'분석 전'}</dd>
            <dt>고정 시간축 후보</dt><dd>{candidate?candidate.candidate_horizons.join(' · '):'분석 후 생성'}</dd>
            <dt>Pine 원문 해시</dt><dd>{candidate?.source_hash?candidate.source_hash.slice(0,20)+'…':'분석 후 저장'}</dd>
          </dl>
          <div className="tv-script-original">
            {(scriptDetail?.hero_images?.[0] || current.image_url) &&
              <img className="tv-script-hero" src={scriptDetail?.hero_images?.[0] || current.image_url || ''} alt={current.name} loading="lazy"/>}
            <div className="tv-script-body">
              <div className="panel-title"><b>TradingView 원본 전체 설명</b><span>{detailLoading?'수집 중':scriptDetail?.fetched_at?'DB 저장 완료':'목록 원문'}</span></div>
              <div className="tv-full-text open">
                {(scriptDetail?.full_text || current.description || '설명이 없습니다.').split('\n').map((line,i)=>line.trim()?<p key={i}>{line}</p>:<br key={i}/>)}
              </div>
              {scriptDetail?.content_images?.length ? <div className="tv-inline-images">
                {scriptDetail.content_images.map((src,i)=><img src={src} alt={current.name+' chart '+(i+1)} loading="lazy" key={src+i}/>)}
              </div> : null}
              <small className="source-ref">출처 URL 보존: {current.chart_url || '—'}</small>
            </div>
          </div>
          <div className="tv-pine-source">
            <div className="panel-title"><b>공개 Pine 원문</b><span>{pineSource?.ok?((pineSource.source_chars||pineSource.source?.length||0).toLocaleString('ko-KR')+'자'):(pineSource?.protected?'보호된 소스':'수집 중')}</span></div>
            {pineSource?.ok && pineSource.source ?
              <pre>{pineSource.source}</pre> :
              <div className="empty-state">{pineSource?.reason || (detailLoading?'Pine 원문을 수집 중입니다.':'공개 Pine 원문이 반환되지 않았습니다.')}</div>}
          </div>
          <div className="actions left">
            <button disabled={busy} onClick={analyze}>{candidate?'원천 분석 완료':'원천 분석 · 전략 후보 생성'}</button>
            <button disabled={busy} onClick={discoverHorizons}>{discovery.length?'사전 적합도 재분석':'시장·시간축 사전 적합도 분석'}</button>
            <button disabled={busy || !candidate} onClick={makeAgents}>통과 조합만 독립 에이전트 생성</button>
          </div>
        </> : <div className="empty-state">전략을 선택하십시오.</div>}
      </div>
    </div>

    <div className="panel">
      <div className="panel-title"><b>Horizon Discovery · 시장×종목군×고정 시간축 사전 적합도</b><span>현재 시장 피처 + 원천 품질 + 시간축 구조를 평가하며, 아직 백테스트 성과점수는 아닙니다.</span></div>
      {discovery.length ?
        <DataTable headers={['국가/자산군','시장','추천 종목군','고정 시간축','사전 적합도','판정']} rows={discoveryRows}/> :
        <div className="empty-state">원천 분석 후 ‘시장·시간축 사전 적합도 분석’을 실행하면 실제 TradingView 시장 스냅샷을 사용한 Discovery 결과가 표시됩니다.</div>}
    </div>

    <div className="panel">
      <div className="panel-title"><b>Discovery 통과 조합 → 독립 Agent</b><span>72점 이상 DISCOVERY_PASS 조합만 생성하며 Origin Source와 Fixed Horizon은 변경하지 않습니다.</span></div>
      {agents.length ?
        <DataTable headers={['국가/자산군','시장','추천 종목군','고정 시간축','사전 적합도','Agent ID','상태']} rows={matchRows}/> :
        <div className="empty-state">Discovery를 통과한 조합에 대해서만 Agent Factory를 실행합니다.</div>}
    </div>

    <div className="grid two">
      <div className="panel">
        <div className="panel-title"><b>원천 계보</b><span>복제 가능한 근거를 끝까지 보존</span></div>
        <ol className="steps">
          <li>TradingView 공개 Strategy의 실제 Script ID 저장</li>
          <li>버전·작성자·게시 시점·원문 URL 저장</li>
          <li>공개 Pine 원문은 내부에서만 읽고 SHA-256 해시로 계보 고정</li>
          <li>전략 유형 및 후보 시간축 생성</li>
          <li>국가·시장·종목 Universe별 독립 Agent 생성</li>
          <li>각 Agent가 백테스트 → Walk-forward → Holdout을 독립 수행</li>
          <li>통과 Agent만 Paper → Shadow → Small Live → Live 승격</li>
        </ol>
      </div>
      <div className="panel">
        <div className="panel-title"><b>현재 선택 전략의 생성 결과</b><span>{candidate?candidate.candidate_id:'아직 후보가 생성되지 않았습니다.'}</span></div>
        {candidate && <div className="agent-plan"><Badge tone="cyan">{candidate.category}</Badge><b>{candidate.candidate_id} · {candidate.name}</b><span>{candidate.domain} · 후보 시간축 {candidate.candidate_horizons.join(' / ')}</span></div>}
        {agents.slice(0,12).map((x,i)=>{
          const research=agentResearch[x.agent_id];
          return <div className="agent-plan" key={x.agent_id}>
            <Badge tone="green">{'Agent '+(i+1)}</Badge>
            <b>{x.agent_id}</b>
            <span>{x.country} · {x.market} · {x.universe} · {x.fixed_horizon}</span>
            <div className="actions left">
              <button disabled={Boolean(research?.loading)} onClick={()=>prepareResearch(x)}>
                {research?.loading?'Universe 분석 중':research?.experimentId?'Quant 실험 등록됨':'Universe 선정 · Quant 실험 등록'}
              </button>
            </div>
            {research?.experimentId && <small>{research.experimentId} · {research.status} · Universe {research.universeCount||0}종목</small>}
            {research?.symbols?.length ? <small>{research.symbols.slice(0,8).join(' · ')}{research.symbols.length>8?' …':''}</small> : null}
            {research?.reason && <small>{research.reason}</small>}
          </div>;
        })}
        {!candidate && <div className="empty-state">원천 분석을 실행하면 실제 후보 ID와 고정 시간축 계보가 생성됩니다.</div>}
      </div>
    </div>
  </>;
}

type RegistrySource = {
  registry_source_id:string;
  source_id:string;
  origin_source_id:string;
  source_kind:string;
  source_name:string;
  source_version?:string | null;
  source_hash?:string | null;
  source_url?:string | null;
  source_status:string;
  created_at:string;
  updated_at:string;
  metadata?:Record<string,unknown>;
};

function StrategyFactory() {
  const [tab,setTab]=useState<'hub'|'tv'|'horizon'|'family'>('hub');
  return <>
    <SectionHeader title="전략 공장" eyebrow="외부 전략 원천과 내부 AI 발굴 결과를 추적 가능한 전략 계보로 전환" actions={['새 전략 등록','자동 발굴 실행']} />
    <div className="subnav">
      {([['hub','전략 원천'],['tv','트레이딩뷰 등록'],['horizon','시간축 탐색'],['family','전략 계열']] as const).map(([k,l])=>
        <button className={tab===k?'active':''} onClick={()=>setTab(k)} key={k}>{l}</button>
      )}
    </div>
    {tab==='hub'&&<SourceHub/>}
    {tab==='tv'&&<TradingViewConnector/>}
    {tab==='horizon'&&<HorizonLab/>}
    {tab==='family'&&<FamilyMatrix/>}
  </>;
}

function SourceHub(){
  const [items,setItems]=useState<RegistrySource[]>([]);
  const [loading,setLoading]=useState(true);
  const [syncing,setSyncing]=useState(false);
  const [error,setError]=useState('');

  const load=()=>{
    setLoading(true);
    setError('');
    fetch(API_BASE+'/api/v1/strategy-sources?limit=500')
      .then(async r=>{if(!r.ok) throw new Error(await r.text()); return r.json();})
      .then(data=>setItems((data.items||[]) as RegistrySource[]))
      .catch(e=>setError(e instanceof Error?e.message:'Source Registry 조회 오류'))
      .finally(()=>setLoading(false));
  };
  useEffect(()=>{load();},[]);

  const sync=async()=>{
    setSyncing(true);
    setError('');
    try{
      const r=await fetch(API_BASE+'/api/v1/strategy-sources/sync?limit=5000',{method:'POST'});
      if(!r.ok) throw new Error(await r.text());
      load();
    }catch(e){
      setError(e instanceof Error?e.message:'Source Registry 동기화 오류');
    }finally{
      setSyncing(false);
    }
  };

  const count=(kind:string)=>items.filter(x=>x.source_kind===kind).length;
  const rows=items.slice(0,200).map(x=>[
    x.registry_source_id,
    x.source_kind,
    x.source_name,
    x.source_version||'—',
    x.source_hash?x.source_hash.slice(0,12)+'…':'—',
    x.source_status,
    x.updated_at,
  ]);

  return <>
    <div className="actions left">
      <button onClick={sync} disabled={syncing}>{syncing?'동기화 중':'TradingView 원천 지금 동기화'}</button>
      <button onClick={load} disabled={loading}>{loading?'불러오는 중':'Registry 새로고침'}</button>
    </div>
    {error && <div className="panel"><span>{error}</span></div>}
    <div className="source-cards">
      <SourceCard title="TradingView 아이디어" detail="커뮤니티 아이디어 원본" count={String(count('TradingViewIdea'))}/>
      <SourceCard title="TradingView Pine" detail="공개 Pine 전략 원천" count={String(count('TradingViewPineStrategy'))}/>
      <SourceCard title="GitHub" detail="등록된 라이선스 전략 저장소" count={String(count('GitHub'))}/>
      <SourceCard title="논문 / 내부 AI" detail="Paper + AIResearch" count={String(count('Paper')+count('AIResearch'))}/>
    </div>
    <div className="panel">
      <div className="panel-title"><b>Strategy Source Registry</b><span>{items.length}개 실제 등록 원천 · Origin Source ID 보존</span></div>
      {rows.length?
        <DataTable headers={['REGISTRY SOURCE','TYPE','NAME','VERSION','HASH','STATUS','UPDATED']} rows={rows}/>:
        <div className="empty-state">등록된 전략 원천이 없습니다.</div>}
    </div>
  </>;
}

function SourceCard({title,detail,count}:{title:string;detail:string;count:string}){
  return <div className="panel source-card"><strong>{title}</strong><b>{count}</b><span>{detail}</span></div>;
}

function TradingViewConnector(){
  return <div className="grid two">
    <div className="panel">
      <div className="panel-title"><b>TradingView 신규 전략 등록</b><Badge tone="cyan">수동 / 공식</Badge></div>
      <label>TradingView 전략 주소<input placeholder="https://www.tradingview.com/script/..." /></label>
      <label>공개 또는 직접 보유한 Pine 소스<textarea rows={10} placeholder={"//@version=6\nstrategy(...)\n..."} /></label>
      <div className="actions left"><button>TradingView 열기</button><button>원천 검증</button><button>Pine 가져오기</button></div>
      <p className="note">원천 주소·작성자·버전·내용 해시를 Source Registry에 보존하고 이후 모든 파생 Agent가 동일 Origin Source를 참조하도록 합니다.</p>
    </div>
    <div className="panel">
      <div className="panel-title"><b>TradingView 알림 Webhook</b><Badge tone="green">백엔드 연결 준비</Badge></div>
      <label>Webhook endpoint<input readOnly value="/webhooks/tradingview/{connection_id}" /></label>
      <dl className="kv"><dt>상태</dt><dd>아직 연결되지 않음</dd><dt>용도</dt><dd>TradingView 알림 신호 수신</dd><dt>소스 코드</dt><dd>Webhook으로 소스코드를 가져오지 않음</dd></dl>
      <hr/>
      <div className="panel-title"><b>Pine → 자율 연구 흐름</b></div>
      <ol className="steps"><li>원천 검증·해시 저장</li><li>전략 후보 생성</li><li>Source-Aware Market Matching</li><li>Horizon Discovery</li><li>Discovery Gate 통과 조합만 Agent 생성</li><li>Quant Lab 검증으로 전달</li></ol>
    </div>
  </div>;
}

function HorizonLab(){
  const [candidates,setCandidates]=useState<LiveStrategyCandidate[]>([]);
  const [selected,setSelected]=useState('');
  const [discovery,setDiscovery]=useState<LiveHorizonDiscovery[]>([]);
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState('');
  const [error,setError]=useState('');

  useEffect(()=>{
    fetch(API_BASE+'/api/v1/tradingview/candidates?limit=100')
      .then(async r=>{if(!r.ok) throw new Error(await r.text()); return r.json();})
      .then(data=>{
        const rows=(data.items||[]) as LiveStrategyCandidate[];
        setCandidates(rows);
        setSelected(prev=>prev||rows[0]?.candidate_id||'');
      })
      .catch(e=>setError(e instanceof Error?e.message:'전략 후보 조회 오류'));
  },[]);

  useEffect(()=>{
    if(!selected){setDiscovery([]);return;}
    fetch(API_BASE+'/api/v1/horizon-discovery/'+encodeURIComponent(selected))
      .then(async r=>{if(!r.ok) throw new Error(await r.text()); return r.json();})
      .then(data=>setDiscovery((data.items||[]) as LiveHorizonDiscovery[]))
      .catch(()=>setDiscovery([]));
  },[selected]);

  const run=async()=>{
    if(!selected) return;
    setBusy(true);setError('');setMessage('');
    try{
      const r=await fetch(API_BASE+'/api/v1/horizon-discovery/'+encodeURIComponent(selected)+'?max_markets=3',{method:'POST'});
      if(!r.ok) throw new Error(await r.text());
      const data=await r.json();
      setDiscovery((data.items||[]) as LiveHorizonDiscovery[]);
      setMessage((data.market_match_mode||'')+' · '+(data.run_id||'')+' · '+(data.count||0)+'개 조합 평가');
    }catch(e){
      setError(e instanceof Error?e.message:'Horizon Discovery 실행 오류');
    }finally{setBusy(false);}
  };

  const create=async()=>{
    if(!selected) return;
    setBusy(true);setError('');setMessage('');
    try{
      const r=await fetch(API_BASE+'/api/v1/agent-factory/'+encodeURIComponent(selected)+'?min_score=72&max_agents=12',{method:'POST'});
      if(!r.ok) throw new Error(await r.text());
      const data=await r.json();
      setMessage('Discovery Gate 통과 Agent '+String(data.count||0)+'개 생성/확인');
    }catch(e){
      setError(e instanceof Error?e.message:'Agent Factory 실행 오류');
    }finally{setBusy(false);}
  };

  const rows=discovery.map(x=>[
    x.country,
    x.market,
    x.universe,
    x.horizon,
    x.fit_score.toFixed(1),
    x.market_score.toFixed(1),
    x.horizon_score.toFixed(1),
    x.status,
  ]);

  return <div className="panel">
    <div className="panel-title"><b>Horizon Discovery</b><span>원본 전략 시장문맥을 카테고리 기본값보다 우선</span></div>
    <div className="actions left">
      <select value={selected} onChange={e=>setSelected(e.target.value)}>
        {candidates.map(x=><option key={x.candidate_id} value={x.candidate_id}>{x.candidate_id} · {x.name}</option>)}
      </select>
      <button disabled={busy||!selected} onClick={run}>{busy?'처리 중':'실제 Discovery 실행'}</button>
      <button disabled={busy||!selected||!discovery.length} onClick={create}>통과 조합 Agent 생성</button>
    </div>
    {message && <p className="note">{message}</p>}
    {error && <p className="note">{error}</p>}
    {rows.length?
      <DataTable headers={['국가/자산군','시장','UNIVERSE','HORIZON','사전적합도','MARKET','HORIZON','판정']} rows={rows}/>:
      <div className="empty-state">선택한 후보의 현재 Discovery 결과가 없습니다. 실제 Discovery를 실행하십시오.</div>}
    <p className="note">사전 적합도는 백테스트 수익률이 아닙니다. Discovery Gate 이후 Quant Lab에서 Walk-forward와 Holdout을 별도로 통과해야 합니다.</p>
  </div>;
}

function FamilyMatrix(){
  const [agents,setAgents]=useState<LiveAgentPlan[]>([]);
  const [error,setError]=useState('');
  useEffect(()=>{
    fetch(API_BASE+'/api/v1/tradingview/agent-plans?limit=1000')
      .then(async r=>{if(!r.ok) throw new Error(await r.text()); return r.json();})
      .then(data=>setAgents((data.items||[]) as LiveAgentPlan[]))
      .catch(e=>setError(e instanceof Error?e.message:'Agent 계보 조회 오류'));
  },[]);

  const rows=agents.map(x=>[
    x.candidate_id,
    x.agent_id,
    x.source_id,
    x.fixed_horizon,
    x.country,
    x.market,
    x.universe,
    x.status,
  ]);

  return <div className="panel">
    <div className="panel-title"><b>원천 전략 × 고정 시간축 Agent 계열</b><span>{agents.length}개 실제 Agent Plan · 퇴역 이력 포함</span></div>
    {error && <p className="note">{error}</p>}
    {rows.length?
      <DataTable headers={['CANDIDATE','AGENT','SOURCE','HORIZON','국가','시장','UNIVERSE','상태']} rows={rows}/>:
      <div className="empty-state">생성된 Agent 계열이 없습니다.</div>}
  </div>;
}

function Research(){return <><SectionHeader title="시장 연구" eyebrow="시장·거시·펀더멘털·뉴스·기회 근거"/><div className="grid three"><MiniStat title="시장" lines={['Regime: Risk-On','Volatility: Moderate','Breadth: Positive','Liquidity: Normal']}/><MiniStat title="거시경제" lines={['Rates: Stable','USD: Firm','Inflation: Cooling','Growth: Mixed']}/><MiniStat title="시장심리" lines={['Bull: 72%','Bear: 28%','News score: +0.34','Uncertainty: 0.19']}/></div><div className="grid two"><div className="panel"><div className="panel-title"><b>기회 후보</b></div><DataTable headers={['ASSET','INVESTOR','THESIS','HORIZON','EXPECTED','CONFIDENCE']} rows={[["NVDA","A-043","Earnings revision + momentum","5d","+4.2%","81%"],["EURUSD","A-071","Rate differential","1d","+1.1%","68%"],["GOLD","A-102","Inflation hedge breakout","4h","+0.9%","66%"]]}/></div><div className="panel"><div className="panel-title"><b>근거 자료</b></div><EventLine time="RSH" tag="AI" text="TradingAgents market/news/fundamental debate"/><EventLine time="FIN" tag="DATA" text="FinRobot valuation and earnings computations"/><EventLine time="MAC" tag="MACRO" text="Macro evidence bundle"/><EventLine time="SRC" tag="SOURCE" text="External strategy provenance linked where applicable"/></div></div></>}

type QuantExperiment = {
  experiment_id:string;
  agent_id:string;
  candidate_id:string;
  source_id:string;
  fixed_horizon:string;
  country:string;
  market:string;
  universe:string;
  data_source:string;
  base_interval:string;
  strategy_engine:string;
  validation_plan:{
    screen?:{engine?:string;purpose?:string};
    walk_forward?:{enabled?:boolean;folds?:number;anchored?:boolean};
    holdout?:{enabled?:boolean;fraction?:number;untouched_until_final?:boolean};
    final_runtime?:{engine?:string;modes?:string[]};
  };
  status:string;
  blocked_reason?:string | null;
  created_at:string;
  symbols:string[];
};

type QuantReadiness = {
  data_sources?:{toss?:{configured?:boolean;official_intervals?:string[];role?:string}};
  strategy_execution?:{pine_engine_configured?:boolean;policy?:string};
  quant_engines?:{state?:string};
};

type QuantPipelineStage = {
  order:number;
  key:string;
  name:string;
  engines:string[];
  engine_ready:boolean;
  state:string;
  blocker?:string | null;
};

type QuantPipeline = {
  count:number;
  pipeline:string;
  integrated_engine_probe_error?:string | null;
  tradingview_ready:boolean;
  toss_ready:boolean;
  pine_executor_ready:boolean;
  macro_data_ready?:boolean;
  stages:QuantPipelineStage[];
};

type MacroSnapshot = {
  ready:boolean;
  snapshot_id?:string;
  snapshot_date?:string;
  collected_at?:string;
  sources?:string[];
  data?:{
    cpi_index?:number | null;
    cpi_yoy?:number | null;
    unemployment_rate?:number | null;
    nonfarm_payroll_thousands?:number | null;
    nonfarm_payroll_mom_change_thousands?:number | null;
    treasury_2y?:number | null;
    treasury_10y?:number | null;
    treasury_30y?:number | null;
    yield_curve_10y_2y?:number | null;
  };
  source_dates?:Record<string,string>;
};

function Lab(){
  const [experiments,setExperiments]=useState<QuantExperiment[]>([]);
  const [readiness,setReadiness]=useState<QuantReadiness | null>(null);
  const [pipeline,setPipeline]=useState<QuantPipeline | null>(null);
  const [macro,setMacro]=useState<MacroSnapshot | null>(null);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState('');

  const reload=()=>{
    setLoading(true);
    setError('');
    Promise.all([
      fetch(QUANT_API_BASE+'/api/v1/quant/experiments?limit=200').then(async r=>{
        if(!r.ok) throw new Error(await r.text());
        return r.json();
      }),
      fetch(QUANT_API_BASE+'/api/v1/quant/readiness').then(async r=>{
        if(!r.ok) throw new Error(await r.text());
        return r.json();
      }),
      fetch(QUANT_API_BASE+'/api/v1/quant/pipeline').then(async r=>{
        if(!r.ok) throw new Error(await r.text());
        return r.json();
      }),
      fetch(QUANT_API_BASE+'/api/v1/quant/macro/snapshot').then(async r=>{
        if(!r.ok) throw new Error(await r.text());
        return r.json();
      }),
    ]).then(([exp,ready,pipe,macroData])=>{
      setExperiments((exp.items||[]) as QuantExperiment[]);
      setReadiness(ready as QuantReadiness);
      setPipeline(pipe as QuantPipeline);
      setMacro(macroData as MacroSnapshot);
    }).catch(e=>setError(e instanceof Error?e.message:'Quant Lab 연결 오류'))
      .finally(()=>setLoading(false));
  };

  useEffect(()=>{ reload(); },[]);

  const blockedUniverse=experiments.filter(x=>x.status==='BLOCKED_UNIVERSE').length;
  const blockedData=experiments.filter(x=>x.status==='BLOCKED_DATA_SOURCE').length;
  const blockedEngine=experiments.filter(x=>x.status==='BLOCKED_STRATEGY_ENGINE').length;
  const completed=experiments.filter(x=>x.status==='COMPLETED').length;
  const superseded=experiments.filter(x=>x.status==='SUPERSEDED').length;
  const selected=experiments.find(x=>x.status!=='SUPERSEDED')||experiments[0];

  const rows=experiments.map(x=>[
    x.experiment_id,
    x.agent_id,
    x.candidate_id,
    x.fixed_horizon,
    x.symbols.length+'종목',
    x.base_interval,
    x.status,
    x.blocked_reason||'—',
  ]);

  const pipelineRows=(pipeline?.stages||[]).map(x=>[
    String(x.order).padStart(2,'0'),
    x.name,
    x.engines.join(' / '),
    x.engine_ready?'ENGINE OK':'ENGINE CHECK',
    x.state,
    x.blocker||'—',
  ]);

  return <>
    <SectionHeader title="퀀트 연구소" eyebrow="실제 Agent → Universe → Experiment Registry → Walk-forward → Holdout → Nautilus" actions={['실험 목록 새로고침']} />
    <div className="actions left"><button onClick={reload} disabled={loading}>{loading?'불러오는 중':'실제 상태 새로고침'}</button></div>
    {error && <div className="panel"><span>{error}</span></div>}
    <div className="metrics five">
      <Metric label="REGISTERED" value={String(experiments.length)} />
      <Metric label="UNIVERSE 차단" value={String(blockedUniverse)} tone={blockedUniverse?'amber':'green'} />
      <Metric label="DATA 차단" value={String(blockedData)} tone={blockedData?'amber':'green'} />
      <Metric label="ENGINE 차단" value={String(blockedEngine)} tone={blockedEngine?'amber':'green'} />
      <Metric label="COMPLETED" value={String(completed)} tone={completed?'green':'muted'} />
      <Metric label="SUPERSEDED" value={String(superseded)} tone={superseded?'amber':'muted'} />
    </div>

    <div className="panel">
      <div className="panel-title"><b>Autonomous Quant Lab · 14단계 실제 상태</b><span>OSS import probe + 데이터 소스 + 실행기 연결 상태</span></div>
      {pipelineRows.length ?
        <DataTable headers={['#','단계','연결 엔진','ENGINE','현재 상태','남은 연결']} rows={pipelineRows}/> :
        <div className="empty-state">14단계 파이프라인 상태를 읽는 중입니다.</div>}
      <p className="note">{pipeline?.pipeline||'Research Agent → Market Agent → Macro Agent → Hypothesis Engine → Python Experiment Engine → Model Family → Validation → Portfolio → Risk → Paper → Live'}</p>
      {pipeline?.integrated_engine_probe_error && <p className="note">통합 엔진 probe 오류: {pipeline.integrated_engine_probe_error}</p>}
    </div>

    <div className="panel">
      <div className="panel-title"><b>Macro Agent · 공식 거시 데이터</b><span>{macro?.ready?'BLS + U.S. Treasury 영구 DB':'첫 수집 대기'}</span></div>
      {macro?.ready ? <div className="grid three">
        <MiniStat title="물가·고용" lines={[
          'CPI YoY '+(macro.data?.cpi_yoy==null?'—':macro.data.cpi_yoy.toFixed(2)+'%'),
          '실업률 '+(macro.data?.unemployment_rate==null?'—':macro.data.unemployment_rate.toFixed(2)+'%'),
          '비농업고용 MoM '+(macro.data?.nonfarm_payroll_mom_change_thousands==null?'—':macro.data.nonfarm_payroll_mom_change_thousands.toLocaleString('ko-KR')+'천명')
        ]}/>
        <MiniStat title="미 국채 금리" lines={[
          '2Y '+(macro.data?.treasury_2y==null?'—':macro.data.treasury_2y.toFixed(2)+'%'),
          '10Y '+(macro.data?.treasury_10y==null?'—':macro.data.treasury_10y.toFixed(2)+'%'),
          '30Y '+(macro.data?.treasury_30y==null?'—':macro.data.treasury_30y.toFixed(2)+'%')
        ]}/>
        <MiniStat title="금리곡선" lines={[
          '10Y−2Y '+(macro.data?.yield_curve_10y_2y==null?'—':macro.data.yield_curve_10y_2y.toFixed(2)+'%p'),
          'Snapshot '+(macro.snapshot_date||'—'),
          (macro.sources||[]).join(' + ')
        ]}/>
      </div> : <div className="empty-state">공식 BLS·미 재무부 데이터의 첫 영구 스냅샷을 생성 중입니다.</div>}
    </div>

    <div className="panel">
      <div className="panel-title"><b>Experiment Registry</b><span>예시 성과값 없이 실제 DB 상태만 표시</span></div>
      {rows.length ? <DataTable headers={['EXPERIMENT','AGENT','CANDIDATE','HORIZON','UNIVERSE','BASE DATA','STATUS','BLOCKER']} rows={rows}/> :
        <div className="empty-state">아직 등록된 Quant Experiment가 없습니다. TradingView 전략평가에서 Agent를 생성한 뒤 Quant 실험 등록을 실행하십시오.</div>}
    </div>

    <div className="grid two">
      <div className="panel">
        <div className="panel-title"><b>실행 준비 상태</b><span>실제 서버 환경</span></div>
        <dl className="kv">
          <dt>TradingView Source</dt><dd>연결됨</dd>
          <dt>Toss OHLCV</dt><dd>{readiness?.data_sources?.toss?.configured?'자격증명 연결됨':'자격증명 미설정'}</dd>
          <dt>공식 기본 봉</dt><dd>{readiness?.data_sources?.toss?.official_intervals?.join(' / ')||'1m / 1d'}</dd>
          <dt>Pine 실행엔진</dt><dd>{readiness?.strategy_execution?.pine_engine_configured?'연결됨':'미연결'}</dd>
          <dt>12개 OSS 프로젝트</dt><dd>{readiness?.quant_engines?.state||'상태 조회 중'}</dd>
          <dt>14단계 Quant Lab</dt><dd>{pipeline?.count===14?'구조 고정 · 실제 상태 연동':'상태 조회 중'}</dd>
          <dt>Macro 공식 데이터</dt><dd>{pipeline?.macro_data_ready?'BLS + Treasury READY':'첫 스냅샷 대기'}</dd>
        </dl>
        <p className="note">{readiness?.strategy_execution?.policy||'실행기가 준비되기 전에는 성과를 생성하지 않습니다.'}</p>
      </div>
      <div className="panel">
        <div className="panel-title"><b>Validation Chain</b><span>{selected?selected.experiment_id:'등록 실험 없음'}</span></div>
        {selected ? <ol className="steps">
          <li>Universe Resolver <Badge tone={selected.symbols.length?'green':'amber'}>{selected.symbols.length?'READY':'BLOCKED'}</Badge></li>
          <li>{selected.data_source} <Badge tone={selected.status==='BLOCKED_DATA_SOURCE'?'amber':'green'}>{selected.status==='BLOCKED_DATA_SOURCE'?'BLOCKED':'READY'}</Badge></li>
          <li>{selected.validation_plan.screen?.engine||'vectorbt'} quick screen <Badge tone="muted">PENDING</Badge></li>
          <li>Walk-forward · {selected.validation_plan.walk_forward?.folds||5} folds <Badge tone="muted">PENDING</Badge></li>
          <li>Holdout · {Math.round((selected.validation_plan.holdout?.fraction||0.2)*100)}% untouched <Badge tone="muted">PENDING</Badge></li>
          <li>{selected.validation_plan.final_runtime?.engine||'NautilusTrader'} realistic backtest <Badge tone="muted">PENDING</Badge></li>
        </ol> : <div className="empty-state">Experiment를 등록하면 실제 검증 체인이 표시됩니다.</div>}
      </div>
    </div>
  </>;
}

function Strategies(){return <><SectionHeader title="운용 전략 등록부" eyebrow="고정 시간축 전략 계보는 버전 단위로 진화" actions={['백테스트','모의운용','승격 단계']} /><div className="panel"><DataTable headers={['LINEAGE','SOURCE','HORIZON','VERSION','INVESTOR','CAPITAL','NET PNL','STATE']} rows={strategies}/></div><div className="grid two"><div className="panel"><div className="panel-title"><b>챔피언 / 도전자 · L-101</b><span>Horizon 10m LOCKED</span></div><div className="compare"><div><Badge tone="green">CHAMPION v1.4</Badge><p>현재 실전 버전</p><b>Net EV +0.18%</b><span>MDD -4.2%</span></div><div><Badge tone="purple">CHALLENGER v1.5</Badge><p>변동성 필터 추가</p><b>Net EV +0.23%</b><span>MDD -3.5%</span></div></div><div className="actions left"><button>RETEST</button><button>PROMOTE v1.5</button><button>REJECT</button></div></div><div className="panel"><div className="panel-title"><b>승격 단계</b></div><ol className="steps"><li>시장 연구 ✓</li><li>Experiment ✓</li><li>Walk-forward ✓</li><li>Holdout ✓</li><li>Nautilus Backtest ✓</li><li>Paper ✓</li><li>Shadow ●</li><li>Small Live ○</li><li>Live ○</li></ol></div></div></>}

function Performance(){return <><SectionHeader title="성과 / 예측 검증" eyebrow="예측 정확도와 투자 손익을 분리 평가"/><div className="metrics five"><Metric label="NET RETURN" value="+8.35%" tone="green"/><Metric label="SHARPE" value="1.71"/><Metric label="SORTINO" value="2.12"/><Metric label="MDD" value="-4.81%" tone="amber"/><Metric label="PROFIT FACTOR" value="1.63"/></div><div className="grid two"><div className="panel chart-panel"><div className="panel-title"><b>Cost-adjusted 평가자산</b></div><Sparkline/></div><div className="panel"><div className="panel-title"><b>Attribution</b></div>{[['CTA','+3.1%'],['Growth','+2.8%'],['Neutral','+1.7%'],['FX','+1.1%'],['Hedge','-0.4%']].map(r=><div className="row-line" key={r[0]}><span>{r[0]}</span><b className={r[1].startsWith('+')?'txt-green':'txt-red'}>{r[1]}</b></div>)}</div></div><div className="panel"><div className="panel-title"><b>예측 원장</b><span>발행된 예측값은 변경 불가</span></div><DataTable headers={['TICKET','INVESTOR','LINEAGE','HORIZON','CREATED','PREDICTED','ACTUAL','VERDICT']} rows={[["P-8821","A-043","L-101","10m","10:30","+0.30%","+0.10%","DIR CORRECT"],["P-8822","A-043","L-105","1h","10:30","-0.50%","PENDING","DUE 11:30"],["P-8823","A-017","L-208","1d","Oct 23","+1.20%","PENDING","NOT MATURED"]]}/></div></>}

function Memory(){return <><SectionHeader title="기억 / 진화" eyebrow="투자 에이전트 기억과 전략 기억을 분리"/><div className="grid two"><div className="panel"><div className="panel-title"><b>투자 에이전트 기억 · A-043</b></div><MiniLines lines={['Successful regimes 12','Portfolio mistakes 8','Capital decisions 31','Risk events 4','Cross-strategy lessons 19']}/></div><div className="panel"><div className="panel-title"><b>전략 기억 · L-101</b><span>10m fixed</span></div><MiniLines lines={['Prediction failures 142','Execution failures 18','Regime failures 31','Versions 5','Current champion v1.4']}/></div></div><div className="panel"><div className="panel-title"><b>최근 자기평가</b></div><dl className="kv"><dt>Context</dt><dd>High volatility 10m downtrend</dd><dt>Failure</dt><dd>Momentum turnover increased sharply</dd><dt>Root cause</dt><dd>Volatility filter lag</dd><dt>Proposed change</dt><dd>Create v1.5 challenger with volume + volatility filter</dd><dt>Forbidden</dt><dd>Change lineage horizon or erase failed evidence</dd></dl></div></>}
function MiniLines({lines}:{lines:string[]}){return <>{lines.map(l=><div className="row-line" key={l}><span>{l}</span></div>)}</>}

function Audit(){return <><SectionHeader title="의사결정 / 근거 추적" eyebrow="에이전트·전략·예측·주문이 왜 만들어졌는지 재현" actions={['추적 기록 내보내기']} /><div className="panel"><div className="trace"><TraceNode title="SOURCE" text="TV-021 · original URL · author · hash"/><TraceNode title="HORIZON EVIDENCE" text="10m selected with independent holdout"/><TraceNode title="STRATEGY LINEAGE" text="L-101 · fixed_horizon=10m · immutable"/><TraceNode title="INVESTOR ASSIGNMENT" text="A-043 · 평가자산 Growth"/><TraceNode title="VERSION" text="Champion v1.4"/><TraceNode title="PREDICTION" text="P-8821 · created before outcome"/><TraceNode title="RISK" text="Local PASS → Global PASS"/><TraceNode title="EXECUTION" text="Nautilus → Broker fill #1882"/><TraceNode title="LEDGER" text="A-043 / L-101 virtual fill attribution"/><TraceNode title="REALITY" text="Forecast +0.30% · Actual +0.10%"/><TraceNode title="EVOLUTION" text="Challenger v1.5 proposed"/></div></div></>}
function TraceNode({title,text}:{title:string;text:string}){return <div className="trace-node"><Badge tone="cyan">{title}</Badge><b>{text}</b></div>}

function System(){
  const productEngines:[string,'LIVE'|'PARTIAL'|'PLANNED'][]=[
    ['Source Registry','LIVE'],
    ['TradingView Collector','LIVE'],
    ['Horizon Discovery','LIVE'],
    ['Agent Factory','LIVE'],
    ['Pine Importer','PARTIAL'],
    ['예측 원장','PLANNED'],
    ['Capital Allocator','PLANNED'],
    ['Population Controller','PLANNED'],
    ['Evolution Engine','PLANNED'],
    ['Broker Reconciliation','PLANNED'],
  ];
  return <><SectionHeader title="시스템 상태" eyebrow="실제 배포 엔진과 다음 구축 대상을 구분"/><div className="grid two"><div className="panel"><div className="panel-title"><b>퀀트 / 매매 엔진</b></div>{['TradingAgents','FinRobot','RD-Agent','Qlib','Chronos','Stable-Baselines3','Ray RLlib','vectorbt','FinRL','Riskfolio','PyPortfolioOpt','NautilusTrader'].map(x=><div className="row-line" key={x}><span>{x}</span><Badge tone="green">설치완료</Badge></div>)}</div><div className="panel"><div className="panel-title"><b>제품 기능 엔진</b><span>실제 배포 상태</span></div>{productEngines.map(([name,state])=><div className="row-line" key={name}><span>{name}</span><Badge tone={state==='LIVE'?'green':state==='PARTIAL'?'cyan':'amber'}>{state==='LIVE'?'운영중':state==='PARTIAL'?'부분연결':'다음 구축'}</Badge></div>)}</div></div></>;
}

function Settings(){return <><SectionHeader title="설정" eyebrow="정책·제약·안전 설정"/><div className="grid two"><div className="panel"><div className="panel-title"><b>영역 / 에이전트 수 정책</b></div><label>영역별 최소 연구 에이전트 수<input value="10" readOnly/></label><label>전체 최대 허용 낙폭<input value="10%" readOnly/></label><label>최대 레버리지<input value="1.5x" readOnly/></label></div><div className="panel"><div className="panel-title"><b>전략 계보 고정 규칙</b></div><dl className="kv"><dt>전략 계보 ID</dt><dd>LOCKED</dd><dt>원천 전략</dt><dd>LOCKED</dd><dt>고정 시간축</dt><dd>LOCKED</dd><dt>전략 버전</dt><dd>EVOLVES via Champion / Challenger</dd></dl></div></div><div className="panel danger-zone"><div className="panel-title"><b>실전 매매 안전장치</b><Badge tone="red">고위험 조작</Badge></div><button>신규 주문 일시정지</button><button>미체결 주문 취소</button><button className="kill">긴급 전체정지</button></div></>}

function App() {
  const [page, setPage] = useState<PageKey>('command');
  const [collapsed, setCollapsed] = useState(false);
  const [runtime,setRuntime]=useState({
    tradingview:false,
    quant:false,
    toss:false,
    pine:false,
    experiments:0,
  });

  useEffect(()=>{
    let cancelled=false;
    Promise.allSettled([
      fetch(API_BASE+'/health').then(async r=>r.ok?r.json():Promise.reject(new Error('TradingView health'))),
      fetch(QUANT_API_BASE+'/api/v1/quant/readiness').then(async r=>r.ok?r.json():Promise.reject(new Error('Quant readiness'))),
      fetch(QUANT_API_BASE+'/api/v1/quant/experiments?limit=200').then(async r=>r.ok?r.json():Promise.reject(new Error('Quant experiments'))),
    ]).then(results=>{
      if(cancelled) return;
      const tv=results[0].status==='fulfilled';
      const quantReady=results[1].status==='fulfilled' ? results[1].value : null;
      const exp=results[2].status==='fulfilled' ? results[2].value : null;
      setRuntime({
        tradingview:tv,
        quant:Boolean(quantReady),
        toss:Boolean(quantReady?.data_sources?.toss?.configured),
        pine:Boolean(quantReady?.strategy_execution?.pine_engine_configured),
        experiments:Number(exp?.count||0),
      });
    });
    return ()=>{cancelled=true;};
  },[]);

  const title = useMemo(() => nav.find(n => n.key === page)?.label ?? '통합 관제', [page]);
  const content = { command:<CommandCenter setPage={setPage}/>, domains:<Domains/>, investors:<Investors/>, capital:<Capital/>, portfolio:<Portfolio/>, risk:<Risk/>, trading:<Trading/>, tvideas:<TradingViewIdeas/>, tvmarkets:<TradingViewMarkets/>, tvstrategies:<TradingViewStrategies/>, factory:<StrategyFactory/>, research:<Research/>, lab:<Lab/>, strategies:<Strategies/>, performance:<Performance/>, memory:<Memory/>, audit:<Audit/>, system:<System/>, settings:<Settings/> }[page];
  const isLiveDataPage=['tvideas','tvmarkets','tvstrategies','lab'].includes(page);
  const systemReady=runtime.tradingview && runtime.quant;

  return <div className={`app ${collapsed ? 'collapsed' : ''}`}>
    <header className="topbar">
      <div className="brand"><button className="collapse" onClick={()=>setCollapsed(v=>!v)}>☰</button><span className="brand-mark">AI</span><div><b>AUTONOMOUS INVESTOR</b><small>{title}</small></div></div>
      <div className="top-metrics">
        <span>TradingView <b className={runtime.tradingview?'txt-green':'txt-amber'}>{runtime.tradingview?'LIVE':'CHECK'}</b></span>
        <span>Quant Lab <b className={runtime.quant?'txt-green':'txt-amber'}>{runtime.quant?'LIVE':'CHECK'}</b></span>
        <span>실험 <b>{runtime.experiments}</b></span>
        <Badge tone={systemReady?'green':'amber'}>{systemReady?'DATA LIVE':'PARTIAL'}</Badge>
        <button className="danger" disabled>실거래 OFF</button>
      </div>
    </header>
    <aside className="sidebar"><div className="nav-label">관리 메뉴</div>{nav.map(n=><button key={n.key} className={page===n.key?'active':''} onClick={()=>setPage(n.key)}><span className="nav-short">{n.short}</span><span>{n.label}</span></button>)}</aside>
    <main>
      <div className="filterbar">
        <span>전체 필터</span><button>영역: 전체</button><button>에이전트: 전체</button><button>원천: 전체</button><button>시간축: 전체</button><button>운용단계: 전체</button>
        <i>{isLiveDataPage?'TradingView / Quant Lab 실제 API·영구 DB 연결':'이 관리화면은 아직 예시 데이터가 포함되어 있으며 API 전환 대상입니다.'}</i>
      </div>
      <div className="workspace">{content}</div>
    </main>
    <aside className="events">
      <div className="event-head"><b>실제 연결 상태</b><Badge tone={systemReady?'green':'amber'}>API</Badge></div>
      <EventLine time="NOW" tag="SOURCE" text={runtime.tradingview?'TradingView 수집 서비스 정상':'TradingView 수집 서비스 점검 필요'}/>
      <EventLine time="NOW" tag="LAB" text={runtime.quant?`Quant Experiment Registry ${runtime.experiments}건`:'Quant Lab 서비스 점검 필요'}/>
      <EventLine time="DATA" tag="TOSS" text={runtime.toss?'토스증권 OHLCV 자격증명 연결됨':'토스증권 OHLCV 자격증명 미설정'}/>
      <EventLine time="EXEC" tag="PINE" text={runtime.pine?'Pine 실행엔진 연결됨':'Pine 실행엔진 미연결'}/>
      <div className="event-spacer"/>
      <div className="health">
        <span>TRADINGVIEW</span><b>{runtime.tradingview?'● 정상':'● 점검'}</b>
        <span>QUANT LAB</span><b>{runtime.quant?'● 정상':'● 점검'}</b>
        <span>실거래</span><b>● OFF</b>
      </div>
    </aside>
    <footer>
      <span>TradingView {runtime.tradingview?'● LIVE':'● CHECK'}</span>
      <span>Quant Lab {runtime.quant?'● LIVE':'● CHECK'}</span>
      <span>Toss Data {runtime.toss?'● READY':'● 미설정'}</span>
      <span>Pine Engine {runtime.pine?'● READY':'● 미연결'}</span>
      <span className="spacer"/><span>Vite / React / TypeScript · 실제 데이터 화면 단계적 전환 중</span>
    </footer>
  </div>;
}

export default App;
