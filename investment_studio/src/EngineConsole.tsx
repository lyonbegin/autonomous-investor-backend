import {useCallback,useEffect,useState} from 'react';
import './engines.css';

type Engine={key:string;name:string;repository:string;pinned_ref:string;role:string;
 state:string;installed:boolean;import_ok:boolean|null;demo_state:string;pid:number|null;
 rss_mib:number|null;checked_at:string|null;last_result:{native_call?:string;result?:unknown}|null;
 error:{type:string;message:string}|null;events:{at:string;kind:string}[]};
type Inventory={count:number;engines:Engine[];live_trading_enabled:boolean};
const labels:Record<string,string>={stopped:'정지',starting:'시작 중',ready:'준비',failed:'실패',timed_out:'시간 초과',
 unrun:'미실행',running:'검증 중',passed:'통과',cancelled:'취소'};
const roles:Record<string,string>={tradingagents:'시장·뉴스·재무·감성 연구',finrobot:'재무 분석 파이프라인',
 rdagent:'가설·실험·코드 연구',qlib:'모델·신호·백테스트',chronos:'시계열 예측',sb3:'강화학습',rllib:'분산 강화학습',
 vectorbt:'고속 전략 검증',finrl:'전략별 목표 비중',riskfolio:'위험 분석·포트폴리오 최적화',
 pyportfolioopt:'자산 배분·효율적 프런티어',nautilus:'백테스트·위험·주문 실행 계약'};
const base='/studio-api/api/v1/ops/engines';
const publicDemo=import.meta.env.VITE_PUBLIC_DEMO==='true';
async function api<T>(path='',method='GET'):Promise<T>{
 const response=await fetch(base+path,{method});
 const payload=await response.json().catch(()=>({detail:'서버 응답을 읽을 수 없습니다'}));
 if(!response.ok)throw Error(String(payload.detail||response.status));
 return payload;
}
export default function EngineConsole(){
 const [data,setData]=useState<Inventory|null>(null);
 const [error,setError]=useState('');const[busy,setBusy]=useState<Record<string,boolean>>({});
 const[selected,setSelected]=useState<string|null>(null);
 const refresh=useCallback(async()=>{setData(await api<Inventory>());setError('')},[]);
 useEffect(()=>{void refresh().catch(e=>setError(String(e)));const timer=setInterval(()=>void refresh().catch(e=>setError(String(e))),2000);return()=>clearInterval(timer)},[refresh]);
 const action=async(key:string,command:string)=>{
  setBusy(previous=>({...previous,[key]:true}));setError('');
  try{await api('/'+encodeURIComponent(key)+'/'+command,'POST');await refresh()}
  catch(e){setError(String(e))}finally{setBusy(previous=>({...previous,[key]:false}))}
 };
 const active=data?.engines.find(row=>row.key===selected);
 return <section className="engines-root">
  <header className="engines-header"><div><p>기존 원본 엔진 · 프로세스별 검증</p><h1>12개 투자 엔진</h1><span>설치·실제 import·소규모 네이티브 검증을 구분해 확인합니다.</span></div><button onClick={()=>void refresh().catch(e=>setError(String(e)))}>상태 새로고침</button></header>
  <div className="engines-scope">이 화면의 검증은 기존 네이티브 데모입니다. SB3는 CPU CartPole 16단계 학습만 수행합니다. 실제 시장 분석·LLM 연구·브로커 주문은 실행하지 않습니다.</div>
  <div className="engines-summary"><b>{data?.count??0}개 엔진</b><span>준비 {data?.engines.filter(row=>row.state==='ready').length??0}</span><span>검증 통과 {data?.engines.filter(row=>row.demo_state==='passed').length??0}</span><strong>실거래 비활성</strong></div>
  {error&&<div role="alert" className="engines-error">{error}</div>}
  <div className="engines-grid">{data?.engines.map(row=><article className="engine-card" key={row.key} data-engine={row.key}>
   <div className="engine-card-title"><h2>{row.name}</h2><span className={'engine-state '+row.state}>{labels[row.state]||row.state}</span></div>
   <p>{roles[row.key]||row.role}</p><a href={'https://github.com/'+row.repository} target="_blank" rel="noopener noreferrer">{row.repository}</a>
   <dl><div><dt>설치</dt><dd>{row.installed?'확인':'미설치'}</dd></div><div><dt>실제 import</dt><dd>{row.import_ok===null?'미검증':row.import_ok?'통과':'실패'}</dd></div><div><dt>네이티브 데모</dt><dd data-testid="demo-state">{labels[row.demo_state]||row.demo_state}</dd></div><div><dt>메모리</dt><dd>{row.rss_mib===null?'—':row.rss_mib+' MiB'}</dd></div></dl>
   <small title={row.pinned_ref}>원본 버전 {row.pinned_ref.slice(0,14)}</small>
   {!publicDemo&&<div className="engine-actions"><button disabled={busy[row.key]||['ready','starting'].includes(row.state)||!row.installed} onClick={()=>void action(row.key,'start')}>시작</button><button disabled={busy[row.key]||row.state!=='ready'} onClick={()=>void action(row.key,'verify')}>소규모 검증</button><button disabled={row.state==='stopped'} onClick={()=>void action(row.key,'stop')}>정지</button></div>}
   <button className="engine-details" onClick={()=>setSelected(row.key)}>결과·오류 이력</button>
  </article>)}</div>
  {active&&<aside className="engine-inspector"><button onClick={()=>setSelected(null)}>닫기</button><h2>{active.name} 검증 결과</h2><p>{active.checked_at?new Date(active.checked_at).toLocaleString('ko-KR'):'아직 검증하지 않았습니다'}</p><pre>{JSON.stringify({demo:active.last_result,error:active.error,events:active.events},null,2)}</pre></aside>}
 </section>
}
