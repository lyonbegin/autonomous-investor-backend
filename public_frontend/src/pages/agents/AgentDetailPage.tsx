import {useEffect,useState} from 'react';
import {api} from '../../api';
import type {Agent,AgentPerformance,Strategy} from '../../types';
import {StatusBadge} from '../../components/StatusBadge';

export function AgentDetailPage({id,go}:{id:string;go:(p:string)=>void}){
  const [a,setA]=useState<Agent|null>(null);
  const [s,setS]=useState<Strategy|null>(null);
  const [perf,setPerf]=useState<AgentPerformance|null>(null);
  const [positions,setPositions]=useState<any>(null);
  const [trades,setTrades]=useState<any>(null);
  const [decisions,setDecisions]=useState<any>(null);
  useEffect(()=>{
    api.agent(id).then(x=>{setA(x);if(x.candidate_id)api.strategy(x.candidate_id).then(setS)});
    api.performance(id).then(setPerf);
    api.positions(id).then(setPositions);
    api.trades(id).then(setTrades);
    api.decisions(id).then(setDecisions);
  },[id]);
  if(!a)return <main><div className="loading">에이전트 불러오는 중...</div></main>;
  const p=perf?.performance||a.performance;
  return <main>
    <button className="back" onClick={()=>go('/agents')}>← 에이전트 목록</button>
    <section className="detail-hero"><div><small>{a.agent_id}</small><h1>{a.strategy_name||s?.name||'Autonomous Agent'}</h1><p>{a.fixed_horizon} · {a.country} · {a.market}</p></div><StatusBadge value={a.status}/></section>
    <div className="metric-row"><div><b>{a.fixed_horizon}</b><span>고정 기간</span></div><div><b>{a.fit_score==null?'—':Number(a.fit_score).toFixed(1)}</b><span>Fit Score</span></div><div><b>{p?.trade_sharpe==null?'—':p.trade_sharpe}</b><span>Sharpe</span></div><div><b>{p?.holdout_return_pct==null?'—':p.holdout_return_pct+'%'}</b><span>Holdout</span></div></div>
    <section className="grid-2"><div className="panel"><h2>사용 전략</h2>{s?<><h3>{s.name}</h3><p>{s.logic}</p><button onClick={()=>go('/strategies/'+encodeURIComponent(s.candidate_id))}>전략 전체보기</button></>:<p>{a.strategy_name||'전략 메타데이터 불러오는 중'}</p>}</div><div className="panel"><h2>고정 투자 유니버스</h2><p>{a.universe}</p><small>이 Agent의 전략 원본과 fixed horizon은 생성 후 변경하지 않습니다.</small></div></section>
    <section className="panel"><h2>검증 성과</h2>{p?<div className="status-list"><div><span>Holdout return</span><b>{p.holdout_return_pct??'—'}%</b></div><div><span>Max drawdown</span><b>{p.max_drawdown_pct??'—'}%</b></div><div><span>Win rate</span><b>{p.win_rate_pct??'—'}%</b></div><div><span>Trade count</span><b>{p.trade_count??'—'}</b></div><div><span>Engine</span><b>{p.strategy_engine||a.strategy_engine||'—'}</b></div></div>:<div className="empty-state">아직 공개 가능한 검증 성과가 없습니다. 현재 실험 상태: {a.experiment_status||'미실행'}</div>}</section>
    <section className="grid-2"><div className="panel"><h2>현재 판단</h2>{decisions?.available?<pre className="json-view">{JSON.stringify(decisions.items,null,2)}</pre>:<div className="empty-state">현재 공개 가능한 판단 원장이 없습니다.</div>}</div><div className="panel"><h2>현재 포지션</h2>{positions?.available?<pre className="json-view">{JSON.stringify(positions.items,null,2)}</pre>:<div className="empty-state">{positions?.reason||'현재 공개 가능한 포지션이 없습니다.'}</div>}</div></section>
    <section className="panel"><h2>최근 매매</h2>{trades?.available?<pre className="json-view">{JSON.stringify(trades.items,null,2)}</pre>:<div className="empty-state">{trades?.reason||'현재 공개 가능한 매매 원장이 없습니다.'}</div>}</section>
  </main>
}
