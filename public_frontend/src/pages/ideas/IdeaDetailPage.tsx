import {useEffect,useState} from 'react';
import {api} from '../../api';
import type {IdeaDetail} from '../../types';
import {TradingViewAdvancedChart} from '../../components/TradingViewAdvancedChart';

export function IdeaDetailPage({id,go}:{id:string;go:(p:string)=>void}){
  const [item,setItem]=useState<IdeaDetail|null>(null);
  const [error,setError]=useState('');
  const params=new URLSearchParams(location.search);
  const symbol=params.get('symbol')||'NASDAQ:AAPL';
  const interval=params.get('interval')||'1D';

  useEffect(()=>{setError('');api.ideaDetail(id).then(setItem).catch(e=>setError(String(e)))},[id]);

  if(error)return <main><button className="back" onClick={()=>go('/ideas')}>← 아이디어 목록</button><div className="empty-state">{error}</div></main>;
  if(!item)return <main><div className="loading">아이디어 상세 불러오는 중...</div></main>;

  return <main className="idea-detail-page">
    <button className="back" onClick={()=>go('/ideas')}>← 아이디어 목록</button>
    <article className="panel idea-detail">
      <div className="idea-detail-head">
        <span className="source">TradingView Idea · {item.source_id}</span>
        <h1>{item.title}</h1>
        <div className="idea-tags"><span>{symbol}</span><span>{interval}</span></div>
      </div>

      <section className="idea-live-chart">
        <TradingViewAdvancedChart symbol={symbol} interval={interval}/>
      </section>

      <section className="idea-analysis">
        <h2>아이디어 원문</h2>
        <div className="idea-full-text">{item.full_text||'본문이 없습니다.'}</div>
      </section>

      <div className="idea-detail-actions">
        {item.source_url&&<a className="external-link" href={item.source_url} target="_blank" rel="noreferrer">TradingView 원본 아이디어 열기 ↗</a>}
      </div>
    </article>
  </main>
}
