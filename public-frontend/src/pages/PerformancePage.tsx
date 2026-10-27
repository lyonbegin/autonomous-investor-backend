import {useEffect,useMemo,useState} from 'react';
import {api} from '../lib/api';
import type {Agent} from '../types';
import Metric from '../components/Metric';

export default function PerformancePage({onAgent}:{onAgent:(id:string)=>void}){
 const [agents,setAgents]=useState<Agent[]>([]);
 useEffect(()=>{api.agents(500).then(x=>setAgents(x.items||[]));},[]);
 const completed=useMemo(()=>agents.filter(a=>a.performance?.holdout_return_pct!=null),[agents]);
 const sorted=[...completed].sort((a,b)=>(b.performance?.holdout_return_pct||0)-(a.performance?.holdout_return_pct||0));
 const avg=completed.length?completed.reduce((s,a)=>s+(a.performance?.holdout_return_pct||0),0)/completed.length:0;
 return <main className="page"><section className="hero slim"><div><small>VALIDATED PERFORMANCE</small><h1>검증 성과</h1><p>실제 Quant Lab에서 Holdout 결과가 존재하는 Agent만 성과표에 포함합니다.</p></div></section>
 <div className="metrics-row"><Metric label="성과 산출 Agent" value={String(completed.length)} sub="Holdout 결과 보유"/><Metric label="평균 Holdout" value={(avg>0?'+':'')+avg.toFixed(2)+'%'} tone={avg>=0?'good':'bad'}/><Metric label="전체 Agent" value={String(agents.length)} sub="연구/차단 포함"/></div>
 <div className="performance-table"><table><thead><tr><th>Agent</th><th>전략</th><th>기간</th><th>시장</th><th>Holdout</th><th>Sharpe</th><th>MDD</th><th>승률</th><th>거래수</th><th>판정</th></tr></thead><tbody>{sorted.map(a=>{const p=a.performance!;return <tr key={a.agent_id} onClick={()=>onAgent(a.agent_id)}><td><b>{a.agent_id}</b></td><td>{a.strategy_name}</td><td>{a.fixed_horizon}</td><td>{a.universe}</td><td className={(p.holdout_return_pct||0)>=0?'good':'bad'}>{p.holdout_return_pct}%</td><td>{p.trade_sharpe}</td><td className="bad">{p.max_drawdown_pct}%</td><td>{p.win_rate_pct}%</td><td>{p.trade_count}</td><td><span className="state">{p.promotion||a.experiment_status}</span></td></tr>})}</tbody></table>{!completed.length&&<div className="empty">아직 완료된 Holdout 결과가 없습니다.</div>}</div>
 </main>
}