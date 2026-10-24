import {useEffect,useMemo,useState} from 'react';
import {api} from '../../api';
import type {PineSource,ScriptDetail} from '../../types';

function label(kind?:string){
  const x=(kind||'').toLowerCase();
  if(x.includes('strateg'))return '전략';
  if(x.includes('librar'))return '라이브러리';
  return '지표';
}

export function ScriptDetailPage({id,go}:{id:string;go:(p:string)=>void}){
  const [detail,setDetail]=useState<ScriptDetail|null>(null);
  const [source,setSource]=useState<PineSource|null>(null);
  const [error,setError]=useState('');
  const [copied,setCopied]=useState(false);

  useEffect(()=>{
    let alive=true;
    setError('');
    Promise.all([api.scriptDetail(id),api.scriptSource(id)])
      .then(([d,s])=>{if(alive){setDetail(d);setSource(s)}})
      .catch(e=>{if(alive)setError(String(e))});
    return()=>{alive=false};
  },[id]);

  const license=useMemo(()=>{
    const lines=(source?.source||'').split(/\r?\n/).slice(0,12).filter(x=>/license|licensed|copyright|©|mozilla|creative commons/i.test(x));
    return lines.join('\n');
  },[source]);

  const copy=async()=>{
    if(!source?.source)return;
    await navigator.clipboard.writeText(source.source);
    setCopied(true);setTimeout(()=>setCopied(false),1200);
  };

  if(error)return <main><button className="back" onClick={()=>go('/scripts')}>← 스크립트 목록</button><div className="empty-state">{error}</div></main>;
  if(!detail||!source)return <main><div className="loading">Pine Script 상세를 불러오는 중...</div></main>;

  return <main className="script-detail-page">
    <button className="back" onClick={()=>go('/scripts')}>← TradingView 스크립트 목록</button>

    <section className="panel script-detail-head">
      <div>
        <div className="script-badges">
          <span className={'type-badge '+label(source.kind)}>{label(source.kind)}</span>
          <span>Pine v{source.pine_version||'-'}</span>
          {source.version&&<span>Script {source.version}</span>}
        </div>
        <h1>{detail.title||source.script_name}</h1>
        <p>TradingView 공개 Pine Script 원문과 설명을 그대로 연결한 전략 소스입니다.</p>
      </div>
      {detail.source_url&&<a className="external-link" href={detail.source_url} target="_blank" rel="noreferrer">TradingView 원본 ↗</a>}
    </section>

    {license&&<section className="panel license-panel"><b>라이선스 / 저작권 표기</b><pre>{license}</pre></section>}

    <section className="panel pine-panel">
      <div className="pine-head">
        <div><b>Pine Script Source</b><span>{source.source_hash?.slice(0,12)}</span></div>
        <button onClick={copy}>{copied?'복사됨':'코드 복사'}</button>
      </div>
      {source.source?<pre className="pine-code"><code>{source.source}</code></pre>:<div className="empty-state">{source.reason||'Pine 소스를 사용할 수 없습니다.'}</div>}
    </section>

    <section className="panel script-description">
      <h2>TradingView 설명</h2>
      <div>{detail.full_text}</div>
    </section>
  </main>
}
