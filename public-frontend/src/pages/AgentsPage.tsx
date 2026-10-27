import {useEffect,useState} from 'react';
import {api} from '../lib/api';
import type {Agent} from '../types';
import AgentCard from '../components/AgentCard';

export default function AgentsPage({onOpen}:{onOpen:(id:string)=>void}){
 const [items,setItems]=useState<Agent[]>([]),[loading,setLoading]=useState(true),[state,setState]=useState('전체');
 useEffect(()=>{api.agents(400).then(x=>setItems(x.items||[])).finally(()=>setLoading(false));},[]);
 const visible=state==='전체'?items:items.filter(x=>(x.experiment_status||x.status)===state);
 const states=['전체','READY','RESEARCH','BLOCKED_STRATEGY_ENGINE','FAILED'];
 return <main className="page"><section className="hero slim"><div><small>AUTONOMOUS AGENTS</small><h1>독립 투자 에이전트</h1><p>하나의 Agent는 하나의 전략 원본과 하나의 고정 기간, 하나의 시장 Universe에 영구 귀속됩니다.</p></div><div className="hero-stat"><b>{items.length}</b><span>Agent</span></div></section>
 <div className="toolbar">{states.map(s=><button className={state===s?'active':''} onClick={()=>setState(s)} key={s}>{s}</button>)}</div>
 {loading?<div className="loading">Agent 불러오는 중…</div>:<div className="agent-grid">{visible.map(a=><AgentCard key={a.agent_id} a={a} onOpen={onOpen}/>)}</div>}</main>
}