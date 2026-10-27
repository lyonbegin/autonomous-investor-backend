import {useEffect,useMemo,useState} from 'react';
import {api} from '../../api';
import type {Strategy} from '../../types';
import {StrategyCard} from '../../components/StrategyCard';

const horizons=['ALL','10m','30m','1h','4h','1d','3d'];
const states=['ALL','LIVE','SMALL_LIVE','SHADOW','PAPER','BACKTEST','RESEARCH'];
export function StrategiesPage({go}:{go:(p:string)=>void}){
  const [items,setItems]=useState<Strategy[]>([]);
  const [q,setQ]=useState('');
  const [state,setState]=useState('ALL');
  const [horizon,setHorizon]=useState('ALL');
  const [sort,setSort]=useState('quality');
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState('');
  useEffect(()=>{setLoading(true);api.strategies().then(x=>setItems(x.items||[])).catch(e=>setError(String(e))).finally(()=>setLoading(false))},[]);
  const filtered=useMemo(()=>{
    const rows=items.filter(s=>{
      const text=[s.name,s.category,s.domain,s.source_id,s.source_name,...(s.agents||[]).map(a=>[a.market,a.country,a.universe].join(' '))].join(' ').toLowerCase();
      const hit=!q||text.includes(q.toLowerCase());
      const st=state==='ALL'||(s.agents||[]).some(a=>a.status===state);
      const hz=horizon==='ALL'||(s.agents||[]).some(a=>a.fixed_horizon===horizon);
      return hit&&st&&hz;
    });
    return [...rows].sort((a,b)=>{
      if(sort==='return') return Number(b.best_performance?.holdout_return_pct??-999)-Number(a.best_performance?.holdout_return_pct??-999);
      if(sort==='sharpe') return Number(b.best_performance?.trade_sharpe??-999)-Number(a.best_performance?.trade_sharpe??-999);
      if(sort==='agents') return (b.agent_count||0)-(a.agent_count||0);
      return Number(b.research_state?.completed||0)-Number(a.research_state?.completed||0)||Number(b.agent_count||0)-Number(a.agent_count||0);
    });
  },[items,q,state,horizon,sort]);
  return <main>
    <section className="hero strategy-hero"><p>Autonomous Strategy Ideas</p><h1>전략을 발견하고, 실제 운용 Agent까지 확인하십시오.</h1><span>TradingView Ideas형 탐색 구조 위에 백테스트·Holdout·Agent 상태와 실제 운용 계보를 함께 표시합니다.</span></section>
    <div className="topic-row"><button className="active">전체 전략</button><button>추세</button><button>모멘텀</button><button>평균회귀</button><button>브레이크아웃</button><button>변동성</button><button>멀티팩터</button></div>
    <div className="toolbar strategy-toolbar">
      <input placeholder="전략·시장·종목·원본 검색" value={q} onChange={e=>setQ(e.target.value)}/>
      <select value={horizon} onChange={e=>setHorizon(e.target.value)}>{horizons.map(x=><option key={x}>{x}</option>)}</select>
      <select value={state} onChange={e=>setState(e.target.value)}>{states.map(x=><option key={x}>{x}</option>)}</select>
      <select value={sort} onChange={e=>setSort(e.target.value)}><option value="quality">검증완료순</option><option value="return">수익률순</option><option value="sharpe">Sharpe순</option><option value="agents">Agent수</option></select>
      <b>{filtered.length} 전략</b>
    </div>
    {loading?<div className="loading">전략과 Agent 실데이터를 불러오는 중...</div>:error?<div className="empty-state">{error}</div>:<div className="strategy-grid feed-grid">{filtered.map(s=><StrategyCard key={s.candidate_id} s={s} onOpen={()=>go('/strategies/'+encodeURIComponent(s.candidate_id))}/>)}</div>}
  </main>
}
