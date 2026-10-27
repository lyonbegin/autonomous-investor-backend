import {useEffect,useMemo,useState} from 'react';
import {api} from '../lib/api';
import type {Strategy} from '../types';
import StrategyCard from '../components/StrategyCard';

export default function StrategiesPage({onOpen,onAgent}:{onOpen:(id:string)=>void;onAgent:(id:string)=>void}){
 const [items,setItems]=useState<Strategy[]>([]),[loading,setLoading]=useState(true),[category,setCategory]=useState('전체');
 useEffect(()=>{api.strategies(200).then(x=>setItems(x.items||[])).finally(()=>setLoading(false));},[]);
 const categories=useMemo(()=>['전체',...Array.from(new Set(items.map(x=>x.category).filter(Boolean)))], [items]);
 const visible=category==='전체'?items:items.filter(x=>x.category===category);
 return <main className="page">
  <section className="hero"><div><small>STRATEGY NETWORK</small><h1>전략을 보고, 그 전략으로 움직이는 Agent를 봅니다</h1><p>TradingView 원본 전략이 우리 Quant Lab을 거쳐 어떤 고정 기간·시장 Agent로 파생됐는지 공개합니다.</p></div><div className="hero-stat"><b>{items.length}</b><span>공개 전략</span></div></section>
  <div className="toolbar categories">{categories.slice(0,9).map(c=><button className={category===c?'active':''} onClick={()=>setCategory(c)} key={c}>{c}</button>)}</div>
  {loading?<div className="loading">전략 네트워크 구성 중…</div>:<div className="strategy-feed">{visible.map(s=><StrategyCard key={s.candidate_id} s={s} onOpen={onOpen} onAgent={onAgent}/>)}</div>}
 </main>
}