import {useEffect,useState} from 'react';
import {api} from '../../api';
import type {Idea} from '../../types';

export function IdeasPage({go}:{go:(p:string)=>void}){
  const [items,setItems]=useState<Idea[]>([]);
  const [page,setPage]=useState(1);
  const [pages,setPages]=useState(1);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState('');
  useEffect(()=>{
    setLoading(true);setError('');
    api.ideas(page).then(x=>{setItems(x.items||[]);setPages(x.page_count||1)})
      .catch(e=>setError(String(e))).finally(()=>setLoading(false));
  },[page]);

  const openIdea=(id:string)=>go('/ideas/'+encodeURIComponent(id));

  return <main>
    <section className="hero"><p>커뮤니티 원본에서 전략으로</p><h1>TradingView 아이디어</h1><span>실시간 아이디어를 읽고, 검증 가능한 전략과 고정 시간축 에이전트로 연결합니다.</span></section>
    <div className="feed-head"><div><button className="selected">최신</button><button>인기</button><button>에디터 픽</button></div><span>LIVE SOURCE</span></div>
    {loading?<div className="loading">불러오는 중...</div>:error?<div className="empty-state">{error}</div>:
      <div className="ideas-grid">{items.map(i=><article className="idea-card clickable" key={i.idea_id} onClick={()=>openIdea(i.idea_id)}>
        <div className="idea-image">{i.image_url?<img src={i.image_url} alt={i.title}/>:<div className="chart-placeholder">{i.symbol}</div>}</div>
        <div className="idea-content">
          <div className="idea-meta"><b>{i.author||'TradingView'}</b><span>{i.created_at?new Date(i.created_at).toLocaleString('ko-KR'):''}</span></div>
          <h2>{i.title}</h2><p>{i.description}</p>
          <div className="idea-tags"><span>{i.symbol||'-'}</span><span>{i.interval||'-'}</span><span>{i.direction||'중립'}</span></div>
          <button onClick={e=>{e.stopPropagation();openIdea(i.idea_id)}}>아이디어 상세보기 →</button>
        </div>
      </article>)}</div>}
    <div className="pager"><button disabled={page<=1} onClick={()=>setPage(v=>v-1)}>이전</button><span>{page} / {pages}</span><button disabled={page>=pages} onClick={()=>setPage(v=>v+1)}>다음</button></div>
  </main>
}
