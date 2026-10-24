import {useEffect,useState} from 'react';
import {api} from '../../api';
import type {IdeaDetail} from '../../types';

export function IdeaDetailPage({id,go}:{id:string;go:(p:string)=>void}){
  const [item,setItem]=useState<IdeaDetail|null>(null);
  const [error,setError]=useState('');
  useEffect(()=>{setError('');api.ideaDetail(id).then(setItem).catch(e=>setError(String(e)))},[id]);

  if(error)return <main><button className="back" onClick={()=>go('/ideas')}>← 아이디어 목록</button><div className="empty-state">{error}</div></main>;
  if(!item)return <main><div className="loading">아이디어 상세 불러오는 중...</div></main>;

  const hero=item.hero_images?.[0];
  const content=(item.content_images||[]).filter(x=>!x.startsWith('data:image/svg+xml'));

  return <main className="idea-detail-page">
    <button className="back" onClick={()=>go('/ideas')}>← 아이디어 목록</button>
    <article className="panel idea-detail">
      <div className="idea-detail-head">
        <span className="source">TradingView Idea · {item.source_id}</span>
        <h1>{item.title}</h1>
      </div>
      {hero&&<img className="idea-detail-hero-image" src={hero} alt={item.title}/>}
      <div className="idea-full-text">{item.full_text||'본문이 없습니다.'}</div>
      {content.length>0&&<div className="idea-content-images">{content.map((src,n)=><img key={n} src={src} alt={`${item.title} ${n+1}`}/>)}</div>}
      <div className="idea-detail-actions">
        {item.source_url&&<a className="external-link" href={item.source_url} target="_blank" rel="noreferrer">TradingView 원본 열기 ↗</a>}
      </div>
    </article>
  </main>
}
