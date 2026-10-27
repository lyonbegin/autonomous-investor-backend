import {useEffect,useState} from 'react';
import {api} from '../lib/api';
import type {Agent} from '../types';
import Metric from '../components/Metric';

export default function AgentDetailPage({id,onBack,onStrategy}:{id:string;onBack:()=>void;onStrategy:(id:string)=>void}){
 const [a,setA]=useState<Agent|null>(null);
 useEffect(()=>{api.agent(id).then(setA);},[id]);
 if(!a)return <main className="page"><div className="loading">Agent 상세 불러오는 중…</div></main>;
 const p=a.performance;
 return <main className="page detail-page">
  <button className="back" onClick={onBack}>← 에이전트 목록</button>
  <section className="detail-hero agent-detail-hero"><div><div className="source-line">AUTONOMOUS INVESTOR AGENT</div><h1>{a.agent_id}</h1><p>{a.strategy_name||'전략 Agent'}</p><div className="tag-row"><span>{a.fixed_horizon} 고정</span><span>{a.market}</span><span>{a.experiment_status||a.status}</span></div></div><div className="agent-lock"><small>IMMUTABLE ASSIGNMENT</small><b>{a.universe}</b><span>생성 후 기간·원본 전환 금지</span></div></section>
  <div className="metrics-row five"><Metric label="Discovery Fit" value={a.fit_score==null?'—':a.fit_score.toFixed(1)}/><Metric label="Market Score" value={a.market_score==null?'—':a.market_score.toFixed(1)}/><Metric label="Horizon Score" value={a.horizon_score==null?'—':a.horizon_score.toFixed(1)}/><Metric label="Holdout" value={p?.holdout_return_pct==null?'—':(p.holdout_return_pct>0?'+':'')+p.holdout_return_pct+'%'} tone={(p?.holdout_return_pct||0)>=0?'good':'bad'}/><Metric label="Sharpe" value={p?.trade_sharpe==null?'—':String(p.trade_sharpe)}/></div>
  <section className="detail-grid">
   <article className="detail-panel"><h2>Agent 배정</h2><dl><dt>전략</dt><dd><button className="link-btn" onClick={()=>onStrategy(a.candidate_id)}>{a.strategy_name||a.candidate_id}</button></dd><dt>고정 기간</dt><dd>{a.fixed_horizon}</dd><dt>시장</dt><dd>{a.country} · {a.market}</dd><dt>Universe</dt><dd>{a.universe}</dd><dt>상태</dt><dd>{a.status}</dd></dl></article>
   <article className="detail-panel"><h2>Quant Lab</h2><dl><dt>Experiment</dt><dd>{a.experiment_id||'아직 없음'}</dd><dt>Engine</dt><dd>{a.strategy_engine||'연결 대기'}</dd><dt>실험 상태</dt><dd>{a.experiment_status||'연구 준비'}</dd><dt>차단 사유</dt><dd>{a.blocked_reason||'없음'}</dd></dl></article>
  </section>
  <section className="detail-panel full"><h2>Discovery 판단 근거</h2><p className="long-copy">{a.rationale||'Discovery 근거가 아직 생성되지 않았습니다.'}</p></section>
  <section className="detail-panel full"><h2>검증 성과</h2>{p?.holdout_return_pct!=null?<div className="performance-cards"><div><span>Holdout Return</span><b className={p.holdout_return_pct>=0?'good':'bad'}>{p.holdout_return_pct}%</b></div><div><span>Max Drawdown</span><b className="bad">{p.max_drawdown_pct}%</b></div><div><span>Trade Sharpe</span><b>{p.trade_sharpe}</b></div><div><span>Win Rate</span><b>{p.win_rate_pct}%</b></div><div><span>Trades</span><b>{p.trade_count}</b></div><div><span>Promotion</span><b>{p.promotion||'—'}</b></div></div>:<div className="empty">이 Agent는 아직 공개 가능한 Holdout 성과가 없습니다. 연구/변환 상태를 그대로 표시합니다.</div>}</section>
 </main>
}