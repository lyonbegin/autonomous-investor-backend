import type {Agent} from '../types';

export default function AgentCard({a,onOpen}:{a:Agent;onOpen:(id:string)=>void}){
  const p=a.performance;
  return <article className="agent-card" onClick={()=>onOpen(a.agent_id)}>
    <div className="agent-title">
      <div><small>{a.agent_id}</small><h3>{a.strategy_name||'전략 Agent'}</h3></div>
      <span className={'state '+(a.experiment_status==='READY'?'ready':'research')}>{a.experiment_status||a.status}</span>
    </div>
    <div className="agent-core">
      <div><span>고정 기간</span><b>{a.fixed_horizon}</b></div>
      <div><span>시장</span><b>{a.market}</b></div>
      <div><span>Universe</span><b>{a.universe}</b></div>
      <div><span>Discovery</span><b>{a.fit_score?a.fit_score.toFixed(1):'—'}</b></div>
    </div>
    <div className="agent-performance">
      <span>Holdout <b>{p?.holdout_return_pct==null?'—':(p.holdout_return_pct>0?'+':'')+p.holdout_return_pct+'%'}</b></span>
      <span>Sharpe <b>{p?.trade_sharpe??'—'}</b></span>
      <span>MDD <b>{p?.max_drawdown_pct==null?'—':p.max_drawdown_pct+'%'}</b></span>
    </div>
  </article>
}