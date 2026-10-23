import { useMemo, useState } from 'react';

type Tone = 'green' | 'red' | 'amber' | 'cyan' | 'purple' | 'muted';
type PageKey =
  | 'command' | 'domains' | 'investors' | 'capital' | 'portfolio' | 'risk'
  | 'trading' | 'factory' | 'research' | 'lab' | 'strategies' | 'performance'
  | 'memory' | 'audit' | 'system' | 'settings';

const nav: { key: PageKey; label: string; short: string }[] = [
  { key: 'command', label: 'COMMAND CENTER', short: 'CMD' },
  { key: 'domains', label: 'DOMAINS', short: 'DOM' },
  { key: 'investors', label: 'INVESTORS', short: 'INV' },
  { key: 'capital', label: 'CAPITAL', short: 'CAP' },
  { key: 'portfolio', label: 'PORTFOLIO', short: 'PRT' },
  { key: 'risk', label: 'RISK', short: 'RSK' },
  { key: 'trading', label: 'TRADING', short: 'TRD' },
  { key: 'factory', label: 'STRATEGY FACTORY', short: 'SRC' },
  { key: 'research', label: 'RESEARCH', short: 'RSH' },
  { key: 'lab', label: 'QUANT LAB', short: 'LAB' },
  { key: 'strategies', label: 'STRATEGIES', short: 'STG' },
  { key: 'performance', label: 'PERFORMANCE', short: 'PER' },
  { key: 'memory', label: 'MEMORY / EVOLUTION', short: 'MEM' },
  { key: 'audit', label: 'AUDIT', short: 'AUD' },
  { key: 'system', label: 'SYSTEM', short: 'SYS' },
  { key: 'settings', label: 'SETTINGS', short: 'SET' },
];

const domains = [
  ['Equity Growth', 14, '15.0%', '+12.4%', 'Return', '1.84'],
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
  ['A-043', 'Equity Growth', '₩105M', '+21.4%', '2.14', '-4.1%', '7', 'SCALE'],
  ['A-017', 'Market Neutral', '₩82M', '+18.8%', '1.92', '-3.8%', '5', 'LIVE'],
  ['A-102', 'CTA / Futures', '₩63M', '+14.7%', '1.81', '-5.2%', '9', 'LIVE'],
  ['A-055', 'Equity Growth', '₩48M', '+11.2%', '1.62', '-4.7%', '6', 'LIVE'],
  ['A-071', 'FX Macro', '₩10M', '-6.2%', '-0.20', '-11.4%', '4', 'CUT'],
];

const strategies = [
  ['L-101', 'TV-021', '10m', 'v1.4', 'A-043', '18%', '+18.2%', 'LIVE'],
  ['L-102', 'AI-112', '4h', 'v2.1', 'A-043', '25%', '+14.1%', 'LIVE'],
  ['L-110', 'PAPER-012', '3d', 'v1.2', 'A-043', '15%', '+8.4%', 'PAPER'],
  ['L-208', 'TV-044', '1d', 'v1.7', 'A-017', '20%', '+9.3%', 'SHADOW'],
  ['L-318', 'GH-018', '30m', 'v1.1', 'A-055', '12%', '-1.3%', 'PAUSED'],
];

const sources = [
  ['TV-021', 'TradingView', 'RSI Mean Reversion', 'Open Source', 'VERIFIED', '10m · 30m · 1h'],
  ['TV-044', 'TradingView', 'Supertrend Regime', 'Own/Public Pine', 'VERIFIED', '1h · 1d'],
  ['GH-018', 'GitHub', 'Breakout Engine', 'Licensed', 'TESTING', '30m · 4h'],
  ['PAPER-012', 'Paper', 'Revision Momentum', 'Described', 'READY', '1d · 3d'],
  ['AI-112', 'Internal AI', 'Liquidity Regime Alpha', 'Internal', 'ACTIVE', '10m · 4h'],
];

function toneClass(value: string): Tone {
  if (/^-|CUT|PAUS|RETIRED|CRITICAL/.test(value)) return 'red';
  if (/\+|LIVE|SCALE|PASS|VERIFIED|ACTIVE|READY|NORMAL/.test(value)) return 'green';
  if (/PAPER|SHADOW|TEST|REVIEW/.test(value)) return 'cyan';
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
    <SectionHeader title="Command Center" eyebrow="Money → Agents → Trading → Profit" actions={['PAUSE NEW ORDERS', 'EMERGENCY STOP']} />
    <div className="metrics four"><Metric label="MASTER CAPITAL" value="₩1.000B" sub="deployed + reserve" /><Metric label="TOTAL EQUITY" value="₩1.083B" sub="+8.35% all-time" tone="green" /><Metric label="NET TODAY PNL" value="+₩4.2M" sub="after costs" tone="green" /><Metric label="DRAWDOWN" value="-1.12%" sub="limit -10.0%" tone="amber" /></div>
    <div className="grid two wide-left"><div className="panel chart-panel"><div className="panel-title"><b>Equity Curve</b><span>Cost-adjusted · Broker reconciled</span></div><Sparkline /></div><div className="panel"><div className="panel-title"><b>Global Risk</b><Badge tone="green">NORMAL</Badge></div><div className="risk-bars"><RiskBar label="Gross" value={68} text="118%"/><RiskBar label="Net" value={54} text="54%"/><RiskBar label="VaR" value={34} text="1.8%"/><RiskBar label="Tech Cluster" value={72} text="23%"/></div></div></div>
    <div className="grid two"><div className="panel clickable" onClick={() => setPage('domains')}><div className="panel-title"><b>Domain Allocation</b><span>10 hedge-aware domains</span></div>{domains.slice(0,6).map(d => <div className="row-line" key={String(d[0])}><span>{d[0]}</span><b>{d[2]}</b></div>)}</div><div className="panel clickable" onClick={() => setPage('investors')}><div className="panel-title"><b>Investor League</b><span>Top live agents</span></div>{investors.slice(0,4).map((a,i) => <div className="row-line" key={a[0]}><span>#{i+1} <b>{a[0]}</b> · {a[1]}</span><b className={String(a[3]).startsWith('+')?'txt-green':'txt-red'}>{a[3]}</b></div>)}</div></div>
    <div className="grid three"><MiniStat title="Agent Population" lines={['RESEARCH 46', 'PAPER 21', 'SHADOW 17', 'SMALL LIVE 9', 'LIVE 31']} /><MiniStat title="Strategy Factory" lines={['New Sources 18', 'Horizon Candidates 32', 'New Lineages 7', 'Challengers 11']} /><MiniStat title="Runtime" lines={['Nautilus HEALTHY', 'Broker CONNECTED', 'Market Data LIVE', 'Pending Predictions 128']} /></div>
    <div className="panel"><div className="panel-title"><b>Live Events</b><span>immutable audit stream</span></div><EventLine time="10:31:04" tag="SOURCE" text="TradingView source TV-221 registered"/><EventLine time="10:31:08" tag="STRATEGY" text="Lineage L-812 / 1h created and assigned to A-043"/><EventLine time="10:31:11" tag="PRED" text="P-8122 matured → actual outcome stored"/><EventLine time="10:31:15" tag="TRADE" text="A-043 · L-101 · NVDA BUY 100 → Nautilus FILLED"/></div>
  </>;
}

function RiskBar({label,value,text}:{label:string;value:number;text:string}) { return <div className="risk-row"><span>{label}</span><div className="bar"><i style={{width:`${value}%`}} /></div><b>{text}</b></div>; }
function MiniStat({title,lines}:{title:string;lines:string[]}) { return <div className="panel"><div className="panel-title"><b>{title}</b></div>{lines.map(l=><div className="mono-line" key={l}>{l}</div>)}</div>; }
function EventLine({time,tag,text}:{time:string;tag:string;text:string}) { return <div className="event"><time>{time}</time><Badge tone={tag==='TRADE'?'green':tag==='PRED'?'purple':'cyan'}>{tag}</Badge><span>{text}</span></div>; }

function Domains() { return <><SectionHeader title="Investment / Hedge Domains" eyebrow="Diversification is enforced before agent competition" actions={['NEW DOMAIN', 'RISK CLUSTERS']} /><div className="callout"><b>Population rule</b><span>Minimum 10 research-capable Autonomous Investor Agents per Domain. Live capital is never assigned only to satisfy the population minimum.</span></div><div className="panel"><DataTable headers={['DOMAIN','INVESTORS','CAPITAL','RETURN','MANDATE','SHARPE']} rows={domains}/></div><div className="grid two"><div className="panel"><div className="panel-title"><b>Domain Constitution · Crisis Hedge</b><Badge tone="purple">TAIL PROTECTION</Badge></div><dl className="kv"><dt>Purpose</dt><dd>Offset systemic Risk-On drawdowns</dd><dt>Normal market</dt><dd>Low / slightly negative return allowed</dd><dt>Minimum capital</dt><dd>5%</dd><dt>Maximum capital</dt><dd>15%</dd><dt>Evaluation</dt><dd>Tail contribution + downside protection</dd></dl></div><div className="panel"><div className="panel-title"><b>Dynamic Risk Clusters</b><span>measured, not named</span></div><RiskBar label="Tech / Risk-On" value={78} text="23%"/><RiskBar label="Trend" value={58} text="17%"/><RiskBar label="USD / Rates" value={46} text="14%"/><RiskBar label="Crisis Protection" value={30} text="8%"/></div></div></> }

function Investors() { const [selected,setSelected]=useState('A-043'); const inv=investors.find(x=>x[0]===selected) ?? investors[0]; return <><SectionHeader title="Autonomous Investor League" eyebrow="Independent investors compete inside hedge-aware domains" actions={['CREATE INVESTOR','POPULATION CONTROLLER']} /><div className="panel"><DataTable headers={['INVESTOR','DOMAIN','CAPITAL','NET RETURN','SHARPE','MDD','STRATEGIES','STATE']} rows={investors}/></div><div className="chips">{investors.map(a=><button className={selected===a[0]?'active':''} onClick={()=>setSelected(String(a[0]))} key={a[0]}>{a[0]}</button>)}</div><div className="grid two wide-left"><div className="panel"><div className="panel-title"><b>{inv[0]} Strategy Book</b><span>{inv[1]} · {inv[2]}</span></div><DataTable headers={['LINEAGE','SOURCE','HORIZON','VERSION','INVESTOR','ALLOCATION','NET PNL','STATE']} rows={strategies.filter(s=>s[4]===inv[0])}/></div><div className="panel"><div className="panel-title"><b>Agent Brain</b><Badge tone="green">AUTONOMOUS</Badge></div><dl className="kv"><dt>Market regime</dt><dd>Risk-On / medium volatility</dd><dt>Current thesis</dt><dd>AI infrastructure revision remains positive</dd><dt>Capital usage</dt><dd>71%</dd><dt>Research queue</dt><dd>8 hypotheses · 3 experiments</dd></dl></div></div></>; }

function Capital() { return <><SectionHeader title="3-Level Capital Allocator" eyebrow="Master → Domain → Investor → Strategy" actions={['SIMULATE','APPROVAL MODE','AUTO EXECUTE']} /><div className="metrics three"><Metric label="ALLOCATED" value="₩925M"/><Metric label="CASH" value="₩108M"/><Metric label="RESERVE (inside cash)" value="₩50M"/></div><div className="grid three"><Allocation title="1 · DOMAIN" rows={[['Equity Growth','15%'],['CTA','15%'],['Neutral','14%'],['FX','10%'],['Crisis Hedge','7%']]} /><Allocation title="2 · INVESTOR" rows={[['A-043','28%'],['A-017','22%'],['A-102','18%'],['A-055','14%'],['Other','18%']]} /><Allocation title="3 · STRATEGY" rows={[['L-101','18%'],['L-102','25%'],['L-110','15%'],['L-208','20%'],['Cash','22%']]} /></div><div className="panel"><div className="panel-title"><b>Next Reallocation Candidates</b><span>verified net PnL + risk + correlation + capacity + cost</span></div><EventLine time="NEXT" tag="CAP" text="A-043 +₩20M · sustained risk-adjusted return"/><EventLine time="NEXT" tag="CAP" text="A-071 -₩15M · drawdown and negative alpha"/><EventLine time="NEXT" tag="RISK" text="Crisis Hedge +2% · Risk-On cluster concentration"/></div></>; }
function Allocation({title,rows}:{title:string;rows:string[][]}) { return <div className="panel"><div className="panel-title"><b>{title}</b></div>{rows.map(r=><div className="row-line" key={r[0]}><span>{r[0]}</span><b>{r[1]}</b></div>)}</div>; }

function Portfolio() { return <><SectionHeader title="Global Portfolio" eyebrow="Actual broker positions mapped back to Domains, Investors and Strategy Books" actions={['REBALANCE']} /><div className="tabs"><Badge tone="cyan">ASSET</Badge><Badge>DOMAIN</Badge><Badge>INVESTOR</Badge><Badge>STRATEGY</Badge><Badge>RISK CLUSTER</Badge></div><div className="grid three"><Allocation title="ASSET CLASS" rows={[['Equity','42%'],['Futures','21%'],['FX','12%'],['Bonds','9%'],['Commodity','8%'],['Cash','8%']]} /><Allocation title="DOMAIN" rows={[['Growth','15%'],['Neutral','14%'],['CTA','15%'],['FX','10%'],['Hedge','7%']]} /><Allocation title="RISK CLUSTER" rows={[['Tech Risk-On','23%'],['Trend','17%'],['USD/Rates','14%'],['Crisis','8%']]} /></div><div className="panel"><DataTable headers={['ASSET','ACTUAL','TARGET','DELTA','PROPOSED ORDER','ATTRIBUTION']} rows={[["NVDA","8.0%","11.0%","+3.0%","BUY 100","A-043 / L-101"],["MSFT","9.0%","7.0%","-2.0%","SELL 51","A-017 / L-208"],["GOLD","3.0%","5.0%","+2.0%","BUY","Crisis Hedge"]]}/></div></>; }

function Risk() { return <><SectionHeader title="Global Risk" eyebrow="Risk control overrides every agent" actions={['STRESS TEST','PAUSE RISK-ON']} /><div className="metrics five"><Metric label="GROSS" value="118%"/><Metric label="NET" value="54%"/><Metric label="LEVERAGE" value="1.18x"/><Metric label="VaR" value="1.8%"/><Metric label="CVaR" value="2.7%"/></div><div className="grid two"><div className="panel"><div className="panel-title"><b>Concentration</b><Badge tone="green">NORMAL</Badge></div><RiskBar label="Domain · Growth" value={52} text="15%"/><RiskBar label="Investor · A-043" value={41} text="10%"/><RiskBar label="Source Family · TV-RSI" value={30} text="7%"/><RiskBar label="Horizon · 10m" value={48} text="14%"/><RiskBar label="Instrument · NVDA" value={26} text="8%"/></div><div className="panel"><div className="panel-title"><b>Hierarchical Kill Switch</b><span>scoped controls</span></div>{['GLOBAL · STOP ALL','DOMAIN · STOP DOMAIN','INVESTOR · PAUSE INVESTOR','STRATEGY · PAUSE STRATEGY','INSTRUMENT · BLOCK SYMBOL','BROKER / VENUE · DISCONNECT'].map((x,i)=><button className={i===0?'kill':''} key={x}>{x}</button>)}</div></div></>; }

function Trading() { return <><SectionHeader title="Nautilus Trading Terminal" eyebrow="Execution source of truth" actions={['LIVE ●','CANCEL OPEN ORDERS','STOP ALL']} /><div className="grid two wide-left"><div className="panel chart-panel"><div className="panel-title"><b>NVDA · 143.21</b><span>Live Market</span></div><Sparkline /></div><div className="panel"><div className="panel-title"><b>Account</b><Badge tone="green">BROKER RECONCILED</Badge></div><dl className="kv"><dt>Equity</dt><dd>₩1.083B</dd><dt>Cash</dt><dd>₩108M</dd><dt>Margin</dt><dd>₩71M</dd><dt>Buying power</dt><dd>₩240M</dd></dl></div></div><div className="panel"><div className="panel-title"><b>Orders / Fills</b><span>Agent + Strategy + Prediction lineage retained</span></div><DataTable headers={['ID','INVESTOR','LINEAGE','TICKET','ASSET','SIDE','QTY','STATE']} rows={[["1882","A-043","L-101","P-8821","NVDA","BUY","100","FILLED"],["1883","A-017","L-208","P-8824","NVDA","SELL","40","FILLED"],["1884","A-102","L-445","P-8830","ES","BUY","3","OPEN"]]}/></div><VirtualLedger /></>; }
function VirtualLedger(){return <div className="panel"><div className="panel-title"><b>Virtual Agent Ledger · NVDA</b><Badge tone="green">RECONCILED</Badge></div><DataTable headers={['ATTRIBUTION','VIRTUAL POSITION','NET PNL','BROKER NET']} rows={[["A-043 / L-101","+100","+₩842K",""],["A-017 / L-208","-40","-₩112K",""],["A-055 / L-318","+20","+₩93K",""],["TOTAL","+80","+₩823K","+80 ✓"]]}/></div>}

function StrategyFactory() { const [tab,setTab]=useState<'hub'|'tv'|'horizon'|'family'>('hub'); return <><SectionHeader title="Strategy Factory" eyebrow="External sources + internal AI discovery become auditable strategy lineages" actions={['NEW SOURCE','RUN DISCOVERY']} /><div className="subnav">{[['hub','SOURCE HUB'],['tv','TRADINGVIEW'],['horizon','HORIZON DISCOVERY'],['family','FAMILY MATRIX']].map(([k,l])=><button className={tab===k?'active':''} onClick={()=>setTab(k as typeof tab)} key={k}>{l}</button>)}</div>{tab==='hub'&&<SourceHub/>}{tab==='tv'&&<TradingViewConnector/>}{tab==='horizon'&&<HorizonLab/>}{tab==='family'&&<FamilyMatrix/>}</>; }
function SourceHub(){return <><div className="source-cards"><SourceCard title="TradingView" detail="Public / own Pine + official alert webhook" count="21"/><SourceCard title="GitHub" detail="Licensed strategy repositories" count="18"/><SourceCard title="Papers" detail="Academic strategy descriptions" count="12"/><SourceCard title="Internal AI" detail="RD-Agent · Qlib · pattern mining" count="34"/></div><div className="panel"><DataTable headers={['SOURCE','CHANNEL','STRATEGY','ACCESS','STATUS','HORIZONS']} rows={sources}/></div></>}
function SourceCard({title,detail,count}:{title:string;detail:string;count:string}){return <div className="panel source-card"><strong>{title}</strong><b>{count}</b><span>{detail}</span></div>}
function TradingViewConnector(){return <div className="grid two"><div className="panel"><div className="panel-title"><b>TradingView Source Intake</b><Badge tone="cyan">MANUAL / OFFICIAL</Badge></div><label>TradingView strategy URL<input placeholder="https://www.tradingview.com/script/..." /></label><label>Public or own Pine source<textarea rows={10} placeholder={"//@version=6\nstrategy(...)\n..."} /></label><div className="actions left"><button>OPEN TRADINGVIEW</button><button>VALIDATE SOURCE</button><button>IMPORT PINE</button></div><p className="note">Automated scraping and protected/invite-only source extraction are disabled. Source provenance, author, URL and content hash are retained.</p></div><div className="panel"><div className="panel-title"><b>TradingView Alert Webhook</b><Badge tone="green">READY FOR BACKEND</Badge></div><label>Webhook endpoint<input readOnly value="/webhooks/tradingview/{connection_id}" /></label><dl className="kv"><dt>Status</dt><dd>Not connected yet</dd><dt>Purpose</dt><dd>Receive TradingView alert signals</dd><dt>Source code</dt><dd>Not fetched by webhook</dd></dl><button>CREATE CONNECTION</button><hr/><div className="panel-title"><b>Pine → Python Pipeline</b></div><ol className="steps"><li>Parse Pine strategy</li><li>Extract entry / exit / risk rules</li><li>Translate to Python representation</li><li>Signal fidelity test</li><li>Send to Horizon Discovery</li><li>Create immutable Strategy Lineage</li></ol></div></div>}
function HorizonLab(){return <div className="panel"><div className="panel-title"><b>Horizon Discovery · TV-021</b><span>before strategy lineage birth</span></div><DataTable headers={['HORIZON','EVENTS','COST-ADJ EV','STABILITY','HOLDOUT','DECISION']} rows={[["10m","12,421","+0.18%","PASS","PASS","CANDIDATE"],["30m","8,112","+0.23%","PASS","PASS","CANDIDATE"],["1h","4,219","+0.31%","PASS","PASS","CANDIDATE"],["4h","1,110","+0.15%","REVIEW","REVIEW","REVIEW"],["1d","822","+0.72%","PASS","PASS","CANDIDATE"],["3d","282","-0.11%","WEAK","FAIL","REJECT"]]}/><div className="actions left"><button>CREATE 10m LINEAGE</button><button>CREATE 30m LINEAGE</button><button>CREATE 1h LINEAGE</button><button>CREATE 1d LINEAGE</button></div></div>}
function FamilyMatrix(){return <div className="panel"><div className="panel-title"><b>Source × Fixed Horizon Strategy Family</b><span>each cell = independent lineage</span></div><DataTable headers={['SOURCE','10m','30m','1h','4h','1d','3d','1w']} rows={[["TV-RSI","L-101","L-104","L-105","—","L-108","—","—"],["TV-Supertrend","L-201","—","—","L-205","L-208","—","—"],["GH-Breakout","—","L-301","—","L-305","—","—","—"],["AI-Liquidity","L-401","—","L-403","—","—","—","—"]]}/></div>}

function Research(){return <><SectionHeader title="Research" eyebrow="Market, macro, fundamental, news and opportunity evidence"/><div className="grid three"><MiniStat title="Market" lines={['Regime: Risk-On','Volatility: Moderate','Breadth: Positive','Liquidity: Normal']}/><MiniStat title="Macro" lines={['Rates: Stable','USD: Firm','Inflation: Cooling','Growth: Mixed']}/><MiniStat title="Sentiment" lines={['Bull: 72%','Bear: 28%','News score: +0.34','Uncertainty: 0.19']}/></div><div className="grid two"><div className="panel"><div className="panel-title"><b>Opportunity Board</b></div><DataTable headers={['ASSET','INVESTOR','THESIS','HORIZON','EXPECTED','CONFIDENCE']} rows={[["NVDA","A-043","Earnings revision + momentum","5d","+4.2%","81%"],["EURUSD","A-071","Rate differential","1d","+1.1%","68%"],["GOLD","A-102","Inflation hedge breakout","4h","+0.9%","66%"]]}/></div><div className="panel"><div className="panel-title"><b>Evidence</b></div><EventLine time="RSH" tag="AI" text="TradingAgents market/news/fundamental debate"/><EventLine time="FIN" tag="DATA" text="FinRobot valuation and earnings computations"/><EventLine time="MAC" tag="MACRO" text="Macro evidence bundle"/><EventLine time="SRC" tag="SOURCE" text="External strategy provenance linked where applicable"/></div></div></>}

function Lab(){return <><SectionHeader title="Quant Lab" eyebrow="Hypothesis → experiment → models → validation" actions={['NEW HYPOTHESIS','RUN QUEUE']} /><div className="metrics four"><Metric label="RUNNING" value="8"/><Metric label="QUEUED" value="21"/><Metric label="PASSED" value="284" tone="green"/><Metric label="FAILED" value="193" tone="red"/></div><div className="panel"><DataTable headers={['EXPERIMENT','INVESTOR','LINEAGE','ENGINE','STATUS','PROGRESS','RESULT']} rows={[["EXP-1203","A-043","L-101","RLlib","RUNNING","71%","—"],["EXP-1204","A-071","L-502","Qlib","VALIDATING","92%","—"],["EXP-1199","A-102","L-445","Chronos","PASSED","100%","Sharpe 1.81"],["EXP-1190","A-055","L-318","vectorbt","FAILED","100%","Cost removes alpha"]]}/></div><div className="grid two"><div className="panel"><div className="panel-title"><b>Model Consensus · NVDA</b></div><DataTable headers={['ENGINE','OUTPUT','CONFIDENCE']} rows={[["Qlib","Score +0.82","82%"],["Chronos","Forecast +3.2%","74%"],["SB3","LONG","69%"],["RLlib","LONG","71%"]]}/></div><div className="panel"><div className="panel-title"><b>Validation Chain</b></div><ol className="steps"><li>vectorbt quick screen <Badge tone="green">PASS</Badge></li><li>Leakage / multiple-test check <Badge tone="green">PASS</Badge></li><li>Walk-forward <Badge tone="green">PASS</Badge></li><li>Holdout <Badge tone="green">PASS</Badge></li><li>Nautilus realistic backtest <Badge tone="cyan">RUNNING</Badge></li></ol></div></div></>}

function Strategies(){return <><SectionHeader title="Strategy Registry" eyebrow="Fixed-horizon lineages evolve by immutable versions" actions={['BACKTEST','PAPER','PROMOTION PIPELINE']} /><div className="panel"><DataTable headers={['LINEAGE','SOURCE','HORIZON','VERSION','INVESTOR','CAPITAL','NET PNL','STATE']} rows={strategies}/></div><div className="grid two"><div className="panel"><div className="panel-title"><b>Champion / Challenger · L-101</b><span>Horizon 10m LOCKED</span></div><div className="compare"><div><Badge tone="green">CHAMPION v1.4</Badge><p>Current live version</p><b>Net EV +0.18%</b><span>MDD -4.2%</span></div><div><Badge tone="purple">CHALLENGER v1.5</Badge><p>Volatility filter added</p><b>Net EV +0.23%</b><span>MDD -3.5%</span></div></div><div className="actions left"><button>RETEST</button><button>PROMOTE v1.5</button><button>REJECT</button></div></div><div className="panel"><div className="panel-title"><b>Promotion Pipeline</b></div><ol className="steps"><li>Research ✓</li><li>Experiment ✓</li><li>Walk-forward ✓</li><li>Holdout ✓</li><li>Nautilus Backtest ✓</li><li>Paper ✓</li><li>Shadow ●</li><li>Small Live ○</li><li>Live ○</li></ol></div></div></>}

function Performance(){return <><SectionHeader title="Performance & Prediction Truth" eyebrow="Forecast skill and investment PnL are separate KPIs"/><div className="metrics five"><Metric label="NET RETURN" value="+8.35%" tone="green"/><Metric label="SHARPE" value="1.71"/><Metric label="SORTINO" value="2.12"/><Metric label="MDD" value="-4.81%" tone="amber"/><Metric label="PROFIT FACTOR" value="1.63"/></div><div className="grid two"><div className="panel chart-panel"><div className="panel-title"><b>Cost-adjusted Equity</b></div><Sparkline/></div><div className="panel"><div className="panel-title"><b>Attribution</b></div>{[['CTA','+3.1%'],['Growth','+2.8%'],['Neutral','+1.7%'],['FX','+1.1%'],['Hedge','-0.4%']].map(r=><div className="row-line" key={r[0]}><span>{r[0]}</span><b className={r[1].startsWith('+')?'txt-green':'txt-red'}>{r[1]}</b></div>)}</div></div><div className="panel"><div className="panel-title"><b>Prediction Ledger</b><span>issued values are immutable</span></div><DataTable headers={['TICKET','INVESTOR','LINEAGE','HORIZON','CREATED','PREDICTED','ACTUAL','VERDICT']} rows={[["P-8821","A-043","L-101","10m","10:30","+0.30%","+0.10%","DIR CORRECT"],["P-8822","A-043","L-105","1h","10:30","-0.50%","PENDING","DUE 11:30"],["P-8823","A-017","L-208","1d","Oct 23","+1.20%","PENDING","NOT MATURED"]]}/></div></>}

function Memory(){return <><SectionHeader title="Memory / Evolution" eyebrow="Investor memory and strategy memory are separate"/><div className="grid two"><div className="panel"><div className="panel-title"><b>Investor Memory · A-043</b></div><MiniLines lines={['Successful regimes 12','Portfolio mistakes 8','Capital decisions 31','Risk events 4','Cross-strategy lessons 19']}/></div><div className="panel"><div className="panel-title"><b>Strategy Memory · L-101</b><span>10m fixed</span></div><MiniLines lines={['Prediction failures 142','Execution failures 18','Regime failures 31','Versions 5','Current champion v1.4']}/></div></div><div className="panel"><div className="panel-title"><b>Latest Reflection</b></div><dl className="kv"><dt>Context</dt><dd>High volatility 10m downtrend</dd><dt>Failure</dt><dd>Momentum turnover increased sharply</dd><dt>Root cause</dt><dd>Volatility filter lag</dd><dt>Proposed change</dt><dd>Create v1.5 challenger with volume + volatility filter</dd><dt>Forbidden</dt><dd>Change lineage horizon or erase failed evidence</dd></dl></div></>}
function MiniLines({lines}:{lines:string[]}){return <>{lines.map(l=><div className="row-line" key={l}><span>{l}</span></div>)}</>}

function Audit(){return <><SectionHeader title="Decision / Evidence Audit" eyebrow="Reproduce why an investor, strategy, prediction and order existed" actions={['EXPORT TRACE']} /><div className="panel"><div className="trace"><TraceNode title="SOURCE" text="TV-021 · original URL · author · hash"/><TraceNode title="HORIZON EVIDENCE" text="10m selected with independent holdout"/><TraceNode title="STRATEGY LINEAGE" text="L-101 · fixed_horizon=10m · immutable"/><TraceNode title="INVESTOR ASSIGNMENT" text="A-043 · Equity Growth"/><TraceNode title="VERSION" text="Champion v1.4"/><TraceNode title="PREDICTION" text="P-8821 · created before outcome"/><TraceNode title="RISK" text="Local PASS → Global PASS"/><TraceNode title="EXECUTION" text="Nautilus → Broker fill #1882"/><TraceNode title="LEDGER" text="A-043 / L-101 virtual fill attribution"/><TraceNode title="REALITY" text="Forecast +0.30% · Actual +0.10%"/><TraceNode title="EVOLUTION" text="Challenger v1.5 proposed"/></div></div></>}
function TraceNode({title,text}:{title:string;text:string}){return <div className="trace-node"><Badge tone="cyan">{title}</Badge><b>{text}</b></div>}

function System(){return <><SectionHeader title="System Health" eyebrow="Installed Quant engines vs product engines under construction"/><div className="grid two"><div className="panel"><div className="panel-title"><b>Quant / Trading Engines</b></div>{['TradingAgents','FinRobot','RD-Agent','Qlib','Chronos','Stable-Baselines3','Ray RLlib','vectorbt','FinRL','Riskfolio','PyPortfolioOpt','NautilusTrader'].map(x=><div className="row-line" key={x}><span>{x}</span><Badge tone="green">INSTALLED</Badge></div>)}</div><div className="panel"><div className="panel-title"><b>Product Engines</b><span>frontend contract first</span></div>{['Source Registry','Pine Importer','Horizon Discovery','Prediction Ledger','Virtual Agent Ledger','Capital Allocator','Population Controller','Evolution Engine','Broker Reconciliation'].map(x=><div className="row-line" key={x}><span>{x}</span><Badge tone="amber">PLANNED</Badge></div>)}</div></div></>}

function Settings(){return <><SectionHeader title="Settings" eyebrow="Policies, constraints and safety"/><div className="grid two"><div className="panel"><div className="panel-title"><b>Domain / Population Policy</b></div><label>Minimum research investors per domain<input value="10" readOnly/></label><label>Global maximum drawdown<input value="10%" readOnly/></label><label>Maximum leverage<input value="1.5x" readOnly/></label></div><div className="panel"><div className="panel-title"><b>Strategy Lineage Invariants</b></div><dl className="kv"><dt>Lineage ID</dt><dd>LOCKED</dd><dt>Origin source</dt><dd>LOCKED</dd><dt>Fixed horizon</dt><dd>LOCKED</dd><dt>Strategy version</dt><dd>EVOLVES via Champion / Challenger</dd></dl></div></div><div className="panel danger-zone"><div className="panel-title"><b>Live Trading Safety</b><Badge tone="red">HIGH IMPACT</Badge></div><button>PAUSE NEW ORDERS</button><button>CANCEL OPEN ORDERS</button><button className="kill">EMERGENCY STOP</button></div></>}

function App() {
  const [page, setPage] = useState<PageKey>('command');
  const [collapsed, setCollapsed] = useState(false);
  const title = useMemo(() => nav.find(n => n.key === page)?.label ?? 'COMMAND CENTER', [page]);
  const content = { command:<CommandCenter setPage={setPage}/>, domains:<Domains/>, investors:<Investors/>, capital:<Capital/>, portfolio:<Portfolio/>, risk:<Risk/>, trading:<Trading/>, factory:<StrategyFactory/>, research:<Research/>, lab:<Lab/>, strategies:<Strategies/>, performance:<Performance/>, memory:<Memory/>, audit:<Audit/>, system:<System/>, settings:<Settings/> }[page];
  return <div className={`app ${collapsed ? 'collapsed' : ''}`}>
    <header className="topbar"><div className="brand"><button className="collapse" onClick={()=>setCollapsed(v=>!v)}>☰</button><span className="brand-mark">AI</span><div><b>AUTONOMOUS INVESTOR</b><small>{title}</small></div></div><div className="top-metrics"><span>Equity <b>₩1.083B</b></span><span>Today <b className="txt-green">+₩4.2M</b></span><span>DD <b className="txt-amber">-1.12%</b></span><Badge tone="green">LIVE</Badge><button className="danger">STOP ALL</button></div></header>
    <aside className="sidebar"><div className="nav-label">CONTROL</div>{nav.map(n=><button key={n.key} className={page===n.key?'active':''} onClick={()=>setPage(n.key)}><span className="nav-short">{n.short}</span><span>{n.label}</span></button>)}</aside>
    <main><div className="filterbar"><span>GLOBAL FILTERS</span><button>Domain: All</button><button>Investor: All</button><button>Source: All</button><button>Horizon: All</button><button>Mode: All</button><i>UI MOCK DATA · API-ready shell</i></div><div className="workspace">{content}</div></main>
    <aside className="events"><div className="event-head"><b>LIVE EVENTS</b><Badge tone="green">WS</Badge></div><EventLine time="11:08" tag="RISK" text="Global risk NORMAL"/><EventLine time="11:07" tag="TRADE" text="NVDA fill reconciled"/><EventLine time="11:06" tag="PRED" text="12 predictions due"/><EventLine time="11:04" tag="SOURCE" text="4 source items pending"/><div className="event-spacer"/><div className="health"><span>NAUTILUS</span><b>● HEALTHY</b><span>BROKER</span><b>● CONNECTED</b><span>MARKET DATA</span><b>● LIVE</b></div></aside>
    <footer><span>WS ● Connected</span><span>Nautilus ● Healthy</span><span>Broker ● Connected</span><span>Market Data ● Live</span><span className="spacer"/><span>Frontend v0.1 · Vite / React / TypeScript</span></footer>
  </div>;
}

export default App;
