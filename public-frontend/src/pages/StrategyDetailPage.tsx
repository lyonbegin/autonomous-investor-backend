import {useEffect,useState} from 'react';
import {api} from '../lib/api';
import type {Strategy} from '../types';
import AgentCard from '../components/AgentCard';
import Metric from '../components/Metric';

export default function StrategyDetailPage({id,onBack,onAgent}:{id:string;onBack:()=>void;onAgent:(id:string)=>void}){
 const [s,setS]=useState<Strategy|null>(null);
 useEffect(()=>{api.strategy(id).then(setS);},[id]);
 if(!s)return <main className="page"><div className="loading">전략 상세 불러오는 중…</div></main>;
 const p=s.best_performance;
 return <main className="page detail-page">
  <button className="back" onClick={onBack}>← 전략 목록</button>
  <section className="detail-hero">
   <div><div className="source-line">{s.source_kind} · {s.author||'공개 전략'}</div><h1>{s.name}</h1><p>{s.category} · {s.domain}</p><div className="tag-row">{s.candidate_horizons.map(h=><span key={h}>{h}</span>)}<span>{s.status}</span></div></div>
   <div className="detail-source"><small>원본</small><b>{s.source_symbol||'시장 자동탐색'}</b><span>Pine {s.pine_version||'—'} · v{s.source_version||'—'}</span>{s.source_url&&<a href={s.source_url} target="_blank" rel="noreferrer">TradingView 원본 ↗</a>}</div>
  </section>
  <div className="metrics-row five"><Metric label="파생 Agent" value={String(s.agent_count)} sub="기간/시장별 독립"/><Metric label="검증 완료" value={String(s.research_state.completed)}/><Metric label="READY" value={String(s.research_state.ready)}/><Metric label="Holdout" value={p?.holdout_return_pct==null?'—':(p.holdout_return_pct>0?'+':'')+p.holdout_return_pct+'%'} tone={(p?.holdout_return_pct||0)>=0?'good':'bad'}/><Metric label="Sharpe" value={p?.trade_sharpe==null?'—':String(p.trade_sharpe)}/></div>
  <section className="detail-grid"><article className="detail-panel"><h2>전략 설명</h2><p className="long-copy">{s.logic}</p></article><article className="detail-panel"><h2>연구 상태</h2><dl><dt>Research Agent</dt><dd>{s.research_state.research}</dd><dt>READY</dt><dd>{s.research_state.ready}</dd><dt>Blocked</dt><dd>{s.research_state.blocked}</dd><dt>성과 산출</dt><dd>{s.research_state.completed}</dd></dl></article></section>
  <div className="section-title"><div><small>AGENTS USING THIS STRATEGY</small><h2>이 전략으로 움직이는 Agent</h2></div><p>같은 원본이어도 기간·시장 Universe가 다르면 별도 Agent입니다.</p></div>
  <div className="agent-grid">{s.agents.map(a=><AgentCard key={a.agent_id} a={a} onOpen={onAgent}/>)}</div>
 </main>
}