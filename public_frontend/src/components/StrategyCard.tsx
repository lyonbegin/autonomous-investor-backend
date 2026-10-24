import type {Strategy} from '../types';
import {StatusBadge} from './StatusBadge';

const n=(v:number|undefined,d=2)=>v==null?'—':Number(v).toFixed(d);
export function StrategyCard({s,onOpen}:{s:Strategy;onOpen:()=>void}){
  const p=s.best_performance||null;
  const states=(s.agents||[]).reduce((m,a)=>(m[a.status]=(m[a.status]||0)+1,m),{} as Record<string,number>);
  const state=['LIVE','SMALL_LIVE','SHADOW','PAPER','BACKTEST','RESEARCH'].find(x=>states[x])||s.status||'RESEARCH';
  const horizons=[...new Set((s.agents||[]).map(a=>a.fixed_horizon).filter(Boolean))];
  const markets=[...new Set((s.agents||[]).map(a=>a.market).filter(Boolean))];
  return <article className="strategy-card tv-card" onClick={onOpen}>
    <div className="card-top">
      <div><span className="source">{s.source_kind||'STRATEGY'}</span><h3>{s.name}</h3><p>{[s.category,s.domain].filter(Boolean).join(' · ')}</p></div>
      <StatusBadge value={state}/>
    </div>
    <p className="logic">{s.logic||'전략 설명이 아직 없습니다.'}</p>
    <div className="chips">{horizons.slice(0,6).map(x=><span key={x}>{x}</span>)}{markets.slice(0,3).map(x=><span key={x}>{x}</span>)}</div>
    <div className="performance-strip">
      <div><span>Holdout</span><b className={(p?.holdout_return_pct||0)>=0?'up':'down'}>{p?.holdout_return_pct==null?'—':`${p.holdout_return_pct>0?'+':''}${n(p.holdout_return_pct)}%`}</b></div>
      <div><span>Sharpe</span><b>{n(p?.trade_sharpe)}</b></div>
      <div><span>MDD</span><b className="down">{p?.max_drawdown_pct==null?'—':`${n(p.max_drawdown_pct)}%`}</b></div>
      <div><span>승률</span><b>{p?.win_rate_pct==null?'—':`${n(p.win_rate_pct,1)}%`}</b></div>
    </div>
    <div className="card-footer-row"><span>운용 Agent <b>{s.agent_count||0}</b></span><span>검증완료 <b>{s.research_state?.completed||0}</b></span><span>{s.author||s.source_name||'원본 전략'}</span></div>
  </article>
}
