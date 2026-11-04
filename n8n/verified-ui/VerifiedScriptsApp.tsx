import React,{useEffect,useState} from 'react';
import {api} from './api';
import type {CommunityScript,ScriptDetail,PineSource} from './types';
import {ScriptsPage} from './pages/scripts/ScriptsPage';
import {ScriptDetailPage} from './pages/scripts/ScriptDetailPage';
import {PineSideBySidePage} from './pages/scripts/PineSideBySidePage';
import './styles.css';

/* Only this subset of the existing public_frontend is mounted within the
 * operations center. All original script cards, detail views, source, Vela
 * controls and same-OHLCV Pine/Python comparison components are REUSED.
 * Other former public frontend sections are NOT mounted.
 */
type ApprovedScript=CommunityScript & {source_hash:string;python_sha256:string;
  evidence_url:string;numeric_points:number;numeric_mismatches:0};
type Catalog={items:ApprovedScript[];count:number;total_count:number;has_more:boolean;limit:number;offset:number};
const BASE='/api/investment/verified-scripts';
async function verified<T>(path:string):Promise<T>{
  const res=await fetch(BASE+path,{credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'}});
  if(!res.ok)throw Error('검증 완료 전략 조회 실패 · HTTP '+res.status);
  return res.json() as Promise<T>;
}
let catalogCache=new Map<string,ApprovedScript>();
const sourceApi=api.scriptSource;
const metaApi=api.scriptMeta;
const detailApi=api.scriptDetail;

api.scripts=async(page=1,scriptType='all')=>{
  const offset=(Math.max(1,page)-1)*50;
  const r=await verified<Catalog>('/catalog?limit=50&offset='+offset+'&type='+encodeURIComponent(scriptType));
  r.items.forEach(x=>catalogCache.set(x.script_id_part,x));
  return r;
};
api.scriptSearch=async(q:string,limit=100)=>{
  const r=await verified<Catalog>('/catalog?limit='+Math.max(1,Math.min(100,limit))+'&offset=0&q='+encodeURIComponent(q));
  r.items.forEach(x=>catalogCache.set(x.script_id_part,x));
  return {query:q,count:r.count,items:r.items};
};
api.scriptMeta=async(id:string)=>{
  const selected=catalogCache.get(id);
  if(!selected)throw Error('관리자 검증 완료 목록에 없는 전략입니다.');
  try{
    const m=await metaApi(id);
    return {...m,author:selected.author||m.author,name:selected.name||m.name,
       symbol:selected.symbol||m.symbol,interval:selected.interval||m.interval,
       script_id_part:id};
  }catch{
    return selected;
  }
};
api.scriptSource=async(id:string)=>{
  const expected=catalogCache.get(id)?.source_hash;
  if(!expected)throw Error('승인된 Pine 원본이 아닙니다.');
  const source: PineSource=await sourceApi(id);
  if(source.source_hash!==expected||!source.source)
    throw Error('공개된 Pine 원본과 승인 시점의 SHA-256이 달라 실행을 차단했습니다.');
  return source;
};
api.scriptDetail=async(id:string)=>{
  const selected=catalogCache.get(id);
  if(!selected)throw Error('승인 목록에 존재하지 않는 전략입니다.');
  try{
    return await detailApi(id);
  }catch{
    // The full-text TradingView collector can be unavailable. The approved,
    // immutable metadata gives an honest fallback, without a fake source.
    return {
      source_kind:'strategy',source_id:id,
      source_url:selected.chart_url||'',title:selected.name,
      full_text:selected.description||'WF-02 검증 완료 전략'
    } as ScriptDetail;
  }
};

type Screen={kind:'list'|'detail'|'compare';id?:string};
function fromLocation():Screen{
 const params=new URLSearchParams(location.search);
 const view=params.get('view');
 const id=params.get('id')||undefined;
 if(id&&(view==='detail'||view==='compare'))return {kind:view,id};
 return {kind:'list'};
}
export function VerifiedScriptsApp(){
 const [screen,setScreen]=useState<Screen>(fromLocation);
 const [approved,setApproved]=useState<Set<string>|null>(null);
 const [error,setError]=useState('');
 const [reload,setReload]=useState(0);
 useEffect(()=>{
   let alive=true;
   (async()=>{
     const all:ApprovedScript[]=[];
     for(let offset=0;offset<=10000;offset+=100){
       const page=await verified<Catalog>('/catalog?limit=100&offset='+offset);
       all.push(...page.items);
       if(!page.has_more)break;
     }
     return all;
   })()
     .then(items=>{
       if(!alive)return;
       catalogCache=new Map(items.map(item=>[item.script_id_part,item]));
       setApproved(new Set(items.map(x=>x.script_id_part)));
       setError('');
     }).catch(e=>{if(alive)setError(String(e))});
   return()=>{alive=false};
 },[reload]);
 useEffect(()=>{
   const listener=()=>setScreen(fromLocation());
   const refresh=(ev:MessageEvent)=>{
     if(ev.origin===location.origin&&ev.data?.type==='INVESTMENT_APPROVED_CATALOG_UPDATED')
       setReload(v=>v+1);
   };
   window.addEventListener('popstate',listener);
   window.addEventListener('message',refresh);
   return()=>{window.removeEventListener('popstate',listener);window.removeEventListener('message',refresh)};
 },[]);
 function go(target:string){
   const next=new URL(target,location.origin);
   const path=next.pathname;
   const id=decodeURIComponent(path.split('/')[2]||'');
   const kind=path.startsWith('/compare/')?'compare':path.startsWith('/scripts/')?'detail':'list';
   const params=new URLSearchParams(next.search);
   params.set('view',kind);
   if(id)params.set('id',id);else params.delete('id');
   history.pushState({},'',location.pathname+'?'+params.toString());
   setScreen({kind,id});
   window.scrollTo({top:0,behavior:'auto'});
 }
 if(error)return <main className="verified-operations-panel"><div className="empty-state">{error}</div></main>;
 if(!approved)return <main className="verified-operations-panel"><div className="loading">검증 완료 전략 기록을 확인하는 중...</div></main>;
 if(screen.kind!=='list'&&(!screen.id||!approved.has(screen.id)))
   return <main className="verified-operations-panel">
      <button className="back" onClick={()=>go('/scripts')}>← 통과 전략 목록</button>
      <div className="empty-state">관리자 검증 완료 목록에 등록되지 않은 전략은 표시하지 않습니다.</div>
   </main>;
 return <div className="verified-operations-panel" data-testid="verified-scripts-app">
   {screen.kind==='list'?<ScriptsPage go={go}/>:
    screen.kind==='detail'?<ScriptDetailPage key={screen.id} id={screen.id!} go={go}/>:
    <PineSideBySidePage key={screen.id} id={screen.id!} go={go}/>}
 </div>;
}
