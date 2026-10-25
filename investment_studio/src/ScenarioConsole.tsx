import {useEffect,useMemo,useState} from 'react';
import './scenarios.css';
type Item={id:string;title:string;purpose:string;steps:number;flows:string[]};
type Step={flow:string;node:string;action:string;details:string;inputs:Record<string,unknown>;outputs:Record<string,unknown>;checks:string[];next_flows:string[]};
type Details={id:string;title:string;purpose:string;steps:Step[]};
type Event={sequence:number;index:number;flow:string;node:string;action:string;status:string;at:string;details:string;inputs:Record<string,unknown>;outputs:Record<string,unknown>;checks:string[];next_flows:string[]};
type Run={run_id:string;status:string;completed_steps:number;total_steps:number;progress_pct:number;events:Event[];error:string|null};
const root='/studio-api/api/v1/alpha/scenarios';
const flowIds=['F01','F02','F03','F04','F05','F06','F07','F08','F09','F10'];
const disclaimer='가상 이벤트 구조 검증 · 원본 12개 엔진/브로커를 실행하거나 가상 수익률을 생성하지 않습니다';
async function get<T>(path:string,method='GET'):Promise<T>{
  const response=await fetch(root+path,{method,headers:{'Content-Type':'application/json'}});
  const data=await response.json();
  if(!response.ok)throw Error(JSON.stringify(data));
  return data as T;
}
function finished(s:string){return s==='completed'||s==='failed'||s==='interrupted'}
export default function ScenarioConsole(){
  const[items,setItems]=useState<Item[]>([]);
  const[flows,setFlows]=useState<Record<string,string>>({});
  const[selected,setSelected]=useState('01-new-strategy');
  const[details,setDetails]=useState<Details|null>(null);
  const[run,setRun]=useState<Run|null>(null);
  const[focused,setFocused]=useState<number|null>(null);
  const[intervalMs,setIntervalMs]=useState(240);
  const[executor,setExecutor]=useState<'direct'|'n8n'>('n8n');
  const[n8nAvailable,setN8nAvailable]=useState(false);
  const[error,setError]=useState('');
  const[launching,setLaunching]=useState(false);
  useEffect(()=>{
    void Promise.all([
      get<{scenarios:Item[];flows:Record<string,string>}>(''),
      get<{configured:boolean}>('/infra')
    ]).then(([r,infra])=>{setItems(r.scenarios);setFlows(r.flows);setN8nAvailable(infra.configured);if(!infra.configured)setExecutor('direct')})
      .catch(e=>setError(String(e)));
  },[]);
  useEffect(()=>{let active=true;void get<Details>('/'+selected).then(v=>{if(active)setDetails(v)}).catch(e=>{if(active)setError(String(e))});return()=>{active=false}},[selected]);
  useEffect(()=>{
    if(!run||finished(run.status))return;
    let active=true;
    const timer=setInterval(()=>{void get<Run>('/runs/'+run.run_id).then(v=>{
      if(active){setRun(v);setFocused(v.completed_steps? v.completed_steps-1:null)}
    }).catch(e=>{if(active)setError(String(e))})},220);
    return()=>{active=false;clearInterval(timer)}
  },[run?.run_id,run?.status]);
  const play=async()=>{
    setLaunching(true);setError('');setRun(null);setFocused(null);
    try{
      const endpoint=executor==='n8n'?'/'+selected+'/dispatch?interval_ms='+intervalMs:'/'+selected+'/runs?interval_ms='+intervalMs;
      const started=await get<{run_id:string}>(endpoint,'POST');
      setRun(await get<Run>('/runs/'+started.run_id));
    }catch(e){setError(String(e))}
    finally{setLaunching(false)}
  };
  const current=useMemo(()=>new Map((run?.events||[]).map(e=>[e.index,e])),[run?.events]);
  const latestByFlow=useMemo(()=>{
    const out:Record<string,Event>={};
    for(const e of run?.events||[])out[e.flow]=e;
    return out;
  },[run?.events]);
  const activeStep=focused!==null?details?.steps[focused]:undefined;
  const activeEvent=focused!==null?current.get(focused):undefined;
  return <div className="scenario-shell">
    <header className="scenario-header"><div><strong>운영 시나리오 검사 센터</strong><small>10개 플로우 · 서버 실행 상태 · 노드 입출력</small></div><span>SYNTHETIC / LIVE OFF</span></header>
    <aside className="scenario-menu"><h3>상황 10개 선택</h3>{items.map((x,i)=><button key={x.id} className={selected===x.id?'selected':''} onClick={()=>{setSelected(x.id);setFocused(null);setRun(null);setError('')}}><b>{String(i+1).padStart(2,'0')}. {x.title}</b><small>{x.steps}단계 · {x.flows.length}개 플로우</small></button>)}</aside>
    <main className="scenario-main">
      <div className="scenario-toolbar"><div><h2>{details?.title||'선택한 시나리오'}</h2><p>{details?.purpose}</p><small>실행 경로: {executor==='n8n'?'실제 n8n Webhook → Worker → 백엔드 시뮬레이션':'Python API 직접 시뮬레이션'}</small></div><div><select aria-label="실행 엔진 선택" value={executor} onChange={e=>setExecutor(e.target.value as 'direct'|'n8n')}><option value="direct">직접 API 검사</option><option value="n8n" disabled={!n8nAvailable}>n8n Worker 경유{n8nAvailable?'':' (미연결)'}</option></select><select value={intervalMs} aria-label="실행 속도" onChange={e=>setIntervalMs(Number(e.target.value))}><option value={0}>즉시</option><option value={100}>빠르게</option><option value={240}>보통</option><option value={700}>느리게</option></select><button className="run" disabled={launching||!details||Boolean(run&&!finished(run.status))} onClick={()=>void play()}>▶ {run&&!finished(run.status)?'실행 중':'시나리오 실행'}</button></div></div>
      <div className="scenario-progress"><b>{run?run.status.toUpperCase():'READY'}</b><span>{executor==='n8n'?'n8n 실경로':'직접 API 경로'}</span><span>{run?run.completed_steps+' / '+run.total_steps+' 단계 · '+run.progress_pct+'%':'실행 전'}</span><div><i style={{width:(run?.progress_pct||0)+'%'}}/></div>{run&&<small>run_id: {run.run_id}</small>}</div>
      <div className="scenario-content"><h3>독립 플로우 가동 상태</h3><div className="scenario-flows">{flowIds.map(f=>{const e=latestByFlow[f],involved=details?.steps.some(s=>s.flow===f);return <div key={f} className={'flow '+(involved?'involved ':'')+(e?.status||'waiting')}><strong>{f}</strong><b>{flows[f]}</b><small>{e?e.action+' · '+e.status:involved?'대기':'비관련'}</small></div>})}</div>
        <h3>실행 단계 및 데이터 전달</h3><div className="scenario-steps">{details?.steps.map((s,i)=>{const ev=current.get(i),state=ev?.status||'waiting';return <button className={'step '+state+(focused===i?' active':'')} key={i} onClick={()=>setFocused(i)}><span>{i+1}</span><strong>{s.flow}</strong><div><b>{s.action}</b><small>{s.details}</small></div><em>{state==='success'?'✓ 완료':state==='running'?'● 진행 중':'대기'}</em></button>})}</div>
      </div>
    </main>
    <aside className="scenario-inspector"><h3>노드별 입력/출력</h3>{activeStep?<div><h4>{activeStep.action}</h4><p>{activeStep.details}</p><small>{activeStep.flow} / {activeStep.node} / {activeEvent?.status||'waiting'}</small><h4>입력</h4><pre>{JSON.stringify(activeStep.inputs,null,2)}</pre><h4>출력</h4><pre>{JSON.stringify(activeEvent?.status==='success'?activeStep.outputs:{pending:true},null,2)}</pre><h4>다음 전달</h4><p>{activeStep.next_flows.map(f=>f+' '+flows[f]).join(', ')||'독립 작업 종료 또는 계속'}</p><h4>검증 항목</h4><p>{activeStep.checks.join(', ')||'없음'}</p><small>{activeEvent?.at||'실행 대기 중'}</small></div>:<p>실행 단계의 노드를 클릭하면 해당 이벤트의 입력·출력·수신 플로우를 표시합니다.</p>}
      <div className="scenario-api"><h4>검사 API</h4><code>POST /api/v1/alpha/scenarios/{'{id}'}/dispatch</code><code>GET /api/v1/alpha/scenarios</code><code>POST /api/v1/alpha/scenarios/{'{id}'}/runs</code><code>GET /api/v1/alpha/scenarios/runs/{'{run_id}'}</code></div></aside>
    <footer className="scenario-footer"><span>{disclaimer}</span>{error&&<strong role="alert">{error}</strong>}</footer>
  </div>
}
