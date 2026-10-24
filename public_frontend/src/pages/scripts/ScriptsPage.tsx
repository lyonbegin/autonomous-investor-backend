import {useEffect,useMemo,useState} from 'react';
import {api} from '../../api';
import type {CommunityScript} from '../../types';

const TYPES=[
  ['all','전체'],
  ['strategies','전략'],
  ['indicators','지표'],
  ['libraries','라이브러리'],
] as const;

function typeLabel(v?:string){
  const x=(v||'').toLowerCase();
  if(x.includes('strateg'))return '전략';
  if(x.includes('librar'))return '라이브러리';
  return '지표';
}

export function ScriptsPage({go}:{go:(p:string)=>void}){
  const [items,setItems]=useState<CommunityScript[]>([]);
  const [page,setPage]=useState(1);
  const [scriptType,setScriptType]=useState('all');
  const [query,setQuery]=useState('');
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState('');
  const [total,setTotal]=useState<number|undefined>(undefined);
  const [hasMore,setHasMore]=useState(false);

  useEffect(()=>{
    let alive=true;
    const t=setTimeout(async()=>{
      setLoading(true);setError('');
      try{
        const q=query.trim();
        const r=q.length>=2
          ? await api.scriptSearch(q,100)
          : await api.scripts(page,scriptType);
        if(!alive)return;
        setItems(r.items||[]);
        setTotal('total_count' in r?r.total_count:('count' in r?r.count:undefined));
        setHasMore('has_more' in r?Boolean(r.has_more):false);
      }catch(e){if(alive)setError(String(e))}
      finally{if(alive)setLoading(false)}
    },query.trim().length>=2?250:0);
    return()=>{alive=false;clearTimeout(t)};
  },[page,scriptType,query]);

  const filtered=useMemo(()=>{
    if(query.trim().length>=2&&scriptType!=='all'){
      const wants=scriptType==='strategies'?'strateg':scriptType==='indicators'?'indicator':'librar';
      return items.filter(x=>(x.script_type||'').toLowerCase().includes(wants));
    }
    return items;
  },[items,query,scriptType]);

  const open=(s:CommunityScript)=>go('/scripts/'+encodeURIComponent(s.script_id_part));

  return <main>
    <section className="hero scripts-hero">
      <p>TRADINGVIEW COMMUNITY SCRIPTS</p>
      <h1>Pine Script 전략·지표 소스</h1>
      <span>아이디어 글이 아니라 실제 Pine Script를 수집하고, 전략 후보와 Autonomous Agent로 연결합니다.</span>
    </section>

    <section className="script-toolbar">
      <div className="script-type-tabs">{TYPES.map(([v,l])=><button key={v} className={scriptType===v?'selected':''} onClick={()=>{setScriptType(v);setPage(1)}}>{l}</button>)}</div>
      <input value={query} onChange={e=>{setQuery(e.target.value);setPage(1)}} placeholder="스크립트명·작성자·종목 검색"/>
    </section>

    <div className="feed-head">
      <div><b>{scriptType==='all'?'전체 스크립트':TYPES.find(x=>x[0]===scriptType)?.[1]}</b>{typeof total==='number'&&<span className="count-note"> {total.toLocaleString()}개</span>}</div>
      <span>OPEN PINE SOURCE</span>
    </div>

    {loading?<div className="loading">TradingView 스크립트를 불러오는 중...</div>:error?<div className="empty-state">{error}</div>:
      <div className="script-grid">{filtered.map(s=><article className="script-card" key={s.script_id_part} onClick={()=>open(s)}>
        <div className="script-thumb">{s.image_url?<img src={s.image_url} alt={s.name}/>:<div className="chart-placeholder">PINE</div>}</div>
        <div className="script-body">
          <div className="script-badges">
            <span className={'type-badge '+typeLabel(s.script_type)}>{typeLabel(s.script_type)}</span>
            {s.is_picked?<span>EDITOR'S PICK</span>:null}
            {s.is_hot?<span>HOT</span>:null}
          </div>
          <h2>{s.name}</h2>
          <div className="script-author">{s.author||'TradingView author'}</div>
          <p>{s.description||'설명이 없습니다.'}</p>
          <div className="script-meta">
            <span>♥ {(s.likes_count||0).toLocaleString()}</span>
            <span>댓글 {(s.comments_count||0).toLocaleString()}</span>
            {s.symbol&&<span>{s.symbol}</span>}
            {s.interval&&<span>{s.interval}</span>}
            {s.version&&<span>v{s.version}</span>}
          </div>
          <button onClick={e=>{e.stopPropagation();open(s)}}>Pine 소스 보기 →</button>
        </div>
      </article>)}</div>}

    {query.trim().length<2&&<div className="pager">
      <button disabled={page<=1} onClick={()=>setPage(v=>Math.max(1,v-1))}>이전</button>
      <span>{page}</span>
      <button disabled={!hasMore} onClick={()=>setPage(v=>v+1)}>다음</button>
    </div>}
  </main>
}
