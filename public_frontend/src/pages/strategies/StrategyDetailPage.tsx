import {useEffect,useState} from 'react';
import {api} from '../../api';
import type {Strategy} from '../../types';
import {StatusBadge} from '../../components/StatusBadge';
import {AgentCard} from '../../components/AgentCard';

const fmt=(v:number|undefined,suffix='')=>v==null?'—':Number(v).toFixed(2)+suffix;
export function StrategyDetailPage({id,go}:{id:string;go:(p:string)=>void}){
  const [s,setS]=useState<Strategy|null>(null);
  const [error,setError]=useState('');
  useEffect(()=>{api.strategy(id).then(setS).catch(e=>setError(String(e)))},[id]);
  if(error)return <main><div className="empty-state">{error}</div></main>;
  if(!s)return <main><div className="loading">전략 불러오는 중...</div></main>;
  const state=['LIVE','SMALL_LIVE','SHADOW','PAPER','BACKTEST','RESEARCH'].find(x=>(s.agents||[]).some(a=>a.status===x))||s.status;
  const p=s.best_performance;
  return <main>
    <button className="back" onClick={()=>go('/strategies')}>← 전략 목록</button>
    <section className="detail-hero strategy-detail-hero">
      <div><span className="source">{s.source_kind} · {s.source_id}</span><h1>{s.name}</h1><p>{[s.category,s.domain,s.author].filter(Boolean).join(' · ')}</p></div>
      <StatusBadge value={state}/>
    </section>
    <div className="metric-row">
      <div><b className={(p?.holdout_return_pct||0)>=0?'up':'down'}>{fmt(p?.holdout_return_pct,'%')}</b><span>Holdout 수익률</span></div>
      <div><b>{fmt(p?.trade_sharpe)}</b><span>Sharpe</span></div>
      <div><b className="down">{fmt(p?.max_drawdown_pct,'%')}</b><span>MDD</span></div>
      <div><b>{fmt(p?.win_rate_pct,'%')}</b><span>Win Rate</span></div>
    </div>
    <section className="panel detail-copy"><h2>전략 개요</h2><p>{s.logic||'설명이 없습니다.'}</p>{s.source_url&&<a href={s.source_url} target="_blank" rel="noreferrer">원본 Source 열기</a>}</section>
    <section className="panel"><div className="section-head"><h2>이 전략을 운용하는 Agent</h2><span>{s.agent_count}개</span></div><div className="agent-grid">{s.agents?.map(a=><AgentCard key={a.agent_id} a={a} onOpen={()=>go('/agents/'+encodeURIComponent(a.agent_id))}/>)}</div></section>
    <section className="panel"><h2>검증 상태</h2><div className="status-list"><div><span>실험 READY</span><b>{s.research_state?.ready||0}</b></div><div><span>성과 산출 완료</span><b>{s.research_state?.completed||0}</b></div><div><span>차단된 실험</span><b>{s.research_state?.blocked||0}</b></div></div></section>
  </main>
}
