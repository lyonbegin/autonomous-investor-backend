import type {Agent} from '../types';
import {StatusBadge} from './StatusBadge';
export function AgentCard({a,onOpen}:{a:Agent;onOpen:()=>void}){
  const p=a.performance;
  return <article className="agent-card" onClick={onOpen}>
    <div className="agent-head"><div><small>{a.agent_id}</small><h3>{a.strategy_name||a.fixed_horizon+' Agent'}</h3></div><StatusBadge value={a.status}/></div>
    <div className="chips"><span>{a.fixed_horizon}</span><span>{a.country||'GLOBAL'}</span><span>{a.market||'-'}</span></div>
    <dl><dt>유니버스</dt><dd>{a.universe||'-'}</dd><dt>적합도</dt><dd>{a.fit_score==null?'—':Number(a.fit_score).toFixed(1)}</dd><dt>실험상태</dt><dd>{a.experiment_status||'미실행'}</dd></dl>
    <div className="agent-performance"><span>Holdout {p?.holdout_return_pct==null?'—':p.holdout_return_pct+'%'}</span><span>Sharpe {p?.trade_sharpe==null?'—':p.trade_sharpe}</span></div>
  </article>
}
