import {useEffect,useState} from 'react';
import {api} from '../lib/api';
import type {Idea} from '../types';

export default function IdeasPage({onStrategies}:{onStrategies:()=>void}){
  const [items,setItems]=useState<Idea[]>([]);
  const [loading,setLoading]=useState(true);
  const [page,setPage]=useState(1);

  useEffect(()=>{setLoading(true);api.ideas(page).then(x=>setItems(x.items||[])).finally(()=>setLoading(false));},[page]);

  return <main className="page">
    <section className="hero slim">
      <div><small>COMMUNITY / IDEAS</small><h1>시장 아이디어</h1><p>TradingView 공개 아이디어를 실시간 수집하고, 검증 가능한 전략 원천으로 연결합니다.</p></div>
      <button className="primary big" onClick={onStrategies}>우리 운용 전략 보기 →</button>
    </section>
    <div className="toolbar"><button className="active">최신</button><button>에디터 추천</button><button>인기</button><span/><button>전체 시장</button><button>전체 기간</button></div>
    {loading?<div className="loading">아이디어 불러오는 중…</div>:<div className="idea-grid">
      {items.map(x=><article className="idea-card" key={x.idea_id}>
        <div className="idea-image">{x.image_url?<img src={x.image_url} alt={x.title}/>:<div className="placeholder-chart"><i/><i/><i/><i/></div>}<div className="symbol">{[x.exchange,x.symbol].filter(Boolean).join(':')}</div><span className={'direction '+((x.direction||'').toLowerCase().includes('long')?'long':(x.direction||'').toLowerCase().includes('short')?'short':'')}>{x.direction||'중립'}</span></div>
        <div className="idea-content"><div className="byline"><b>{x.author||'TradingView'}</b><time>{x.created_at?new Date(x.created_at).toLocaleString('ko-KR'):''}</time></div><h2>{x.title}</h2><p>{x.description?.slice(0,360)}{x.description?.length>360?'…':''}</p><div className="idea-meta"><span>💬 {x.comments_count||0}</span><span>♥ {x.likes_count||0}</span><span>조회 {x.views_count||0}</span><span>{x.interval||''}</span></div>{x.chart_url&&<a href={x.chart_url} target="_blank" rel="noreferrer">원본 아이디어 ↗</a>}</div>
      </article>)}
    </div>}
    <div className="pager"><button disabled={page<=1} onClick={()=>setPage(p=>p-1)}>← 이전</button><b>{page}</b><button onClick={()=>setPage(p=>p+1)}>다음 →</button></div>
  </main>
}