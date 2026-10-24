import type {Strategy} from '../types';

function pct(v?:number){return v==null?'—':(v>0?'+':'')+v.toFixed(2)+'%';}

export default function StrategyCard({s,onOpen,onAgent}:{s:Strategy;onOpen:(id:string)=>void;onAgent:(id:string)=>void}){
  const p=s.best_performance;
  return <article className="strategy-card">
    <div className="strategy-head">
      <div>
        <div className="source-line">{s.source_kind==='TradingViewPineStrategy'?'TradingView 전략':'전략 원천'} · {s.author||'공개 전략'}</div>
        <h3 onClick={()=>onOpen(s.candidate_id)}>{s.name}</h3>
        <p>{s.category} · {s.domain}</p>
      </div>
      <span className="state research">{s.status}</span>
    </div>
    <div className="strategy-visual">
      <div className="chart-grid">
        <svg viewBox="0 0 500 150"><polyline points="0,118 35,105 75,110 110,82 145,88 180,57 220,69 255,43 295,50 340,28 380,38 420,21 500,30" fill="none" stroke="currentColor" strokeWidth="3"/></svg>
      </div>
      <div className="source-symbol">{s.source_symbol||'MULTI MARKET'}<small>{s.source_interval?s.source_interval+' 원본':''}</small></div>
    </div>
    <p className="logic">{s.logic?.slice(0,280)}{s.logic?.length>280?'…':''}</p>
    <div className="card-stats">
      <div><span>운용 Agent</span><b>{s.agent_count}</b></div>
      <div><span>검증 완료</span><b>{s.research_state.completed}</b></div>
      <div><span>Holdout 수익</span><b className={(p?.holdout_return_pct||0)>=0?'good':'bad'}>{pct(p?.holdout_return_pct)}</b></div>
      <div><span>Sharpe</span><b>{p?.trade_sharpe??'—'}</b></div>
      <div><span>MDD</span><b className="bad">{p?.max_drawdown_pct==null?'—':'-'+Math.abs(p.max_drawdown_pct).toFixed(2)+'%'}</b></div>
    </div>
    <div className="agent-strip">
      {s.agents.slice(0,4).map(a=><button key={a.agent_id} onClick={()=>onAgent(a.agent_id)}><b>{a.fixed_horizon}</b><span>{a.universe}</span><i>{a.experiment_status||a.status}</i></button>)}
      {s.agent_count>4&&<button onClick={()=>onOpen(s.candidate_id)}>+{s.agent_count-4}</button>}
    </div>
    <footer><button className="primary" onClick={()=>onOpen(s.candidate_id)}>전략 전체보기</button>{s.source_url&&<a href={s.source_url} target="_blank" rel="noreferrer">원본 출처 ↗</a>}</footer>
  </article>
}