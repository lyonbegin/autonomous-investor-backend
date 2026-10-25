import {useCallback,useEffect,useMemo,useRef,useState} from 'react';
import {
  ReactFlow,ReactFlowProvider,Background,Controls,MiniMap,Handle,Position,
  MarkerType,type Edge,type Node,type NodeProps,
} from '@xyflow/react';

type FlowNameMap=Record<string,string>;
type Step={id:string;flow:string;label:string;action:string;params:Record<string,unknown>;index:number;next:string[];state?:'waiting'|'running'|'success'|'failed'};
type Scenario={scenario_id:number;title:string;why:string;count:number;flows:string[];nodes:Step[];edges:{from:string;to:string}[]};
type Catalogue={count:number;flows:FlowNameMap;scenarios:Scenario[]};
type ScenarioEvent={seq:number;step_id:string;flow:string;flow_label:string;action:string;label:string;origin:string;input:Record<string,unknown>;output:Record<string,unknown>;at:string};
type Verification={name:string;passed:boolean};
type Agent={status:string;strategy:string|null;epoch:number;positions:number};
type ScenarioState={cash:number;reserved:number;agents:Record<string,Agent>;strategies:Record<string,{state:string;validation:string}>;jobs:Record<string,{status:string;result:string|null}>;orders:Record<string,unknown>;audits:unknown[];approved_versions:string[];live_orders_sent:number};
type Run={run_id:string;scenario_id:number;title:string;why:string;engine:'n8n'|'internal-test';status:string;progress:number;total:number;progress_pct:number;nodes:Step[];events:ScenarioEvent[];state:ScenarioState;verification:Verification[];error:string|null};
type ConsoleNodeData=Record<string,unknown>&{id:string;label:string;flow:string;flowName:string;status:string;action:string;index:number};
type ConsoleNode=Node<ConsoleNodeData,'scenario-step'>;
const BASE='/studio-api/api/v1/alpha/scenarios';
const FLOW_COLORS:Record<string,string>={F01:'#2873b3',F02:'#0c9188',F03:'#6f9b31',F04:'#de8130',F05:'#bd5562',F06:'#886cc0',F07:'#5366af',F08:'#ab7f31',F09:'#bb554e',F10:'#547c87'};
const num=(value:number)=>value.toLocaleString('ko-KR');
const getMessage=(value:unknown)=>{if(typeof value==='object'&&value!==null&&'detail' in value)return String((value as {detail:unknown}).detail);return String(value)};
async function api<T>(path:string,method='GET',body?:unknown):Promise<T>{
  const resp=await fetch(BASE+path,{method,headers:{'Content-Type':'application/json'},
    body:body===undefined?undefined:JSON.stringify(body),credentials:'same-origin'});
  const data:unknown=await resp.json().catch(()=>({detail:resp.statusText}));
  if(!resp.ok)throw new Error(getMessage(data));
  return data as T;
}
function StepCard({data,selected}:NodeProps<ConsoleNode>){
  const color=FLOW_COLORS[data.flow]||'#899a9f';
  const sym=data.status==='success'?'✓':data.status==='running'?'●':data.status==='failed'?'×':'○';
  return <div className={'sc-node sc-'+data.status+(selected?' sc-selected':'')} style={{borderLeftColor:color}}>
    <Handle type="target" position={Position.Left} isConnectable={false}/>
    <div className="sc-node-heading"><span style={{color}}>{data.flow}</span><small>#{data.index+1}</small></div>
    <strong>{data.label}</strong><div className="sc-node-detail">{data.action}</div>
    <div className="sc-node-status">{sym} {data.status==='success'?'완료':data.status==='running'?'실행 중':data.status==='failed'?'오류':'대기 중'}</div>
    <Handle type="source" position={Position.Right} isConnectable={false}/>
  </div>;
}
const NODE_TYPES={['scenario-step']:StepCard};
function graphFor(scenario:Scenario,run:Run|null,flows:FlowNameMap){
  const nodes:ConsoleNode[]=scenario.nodes.map((s,i)=>{
    let status='waiting';
    if(run&&run.scenario_id===scenario.scenario_id){
      if(i<run.progress)status='success';
      else if(i===run.progress&&run.status==='running')status='running';
      else if(i===run.progress&&run.status==='failed')status='failed';
    }
    return{id:s.id,type:'scenario-step',position:{x:(i%4)*315+75,y:Math.floor(i/4)*180+90},
      data:{id:s.id,label:s.label,flow:s.flow,flowName:flows[s.flow],status,action:s.action,index:i}};
  });
  const edges:Edge[]=scenario.edges.map((e,i)=>({
    id:'edge-'+i,source:e.from,target:e.to,type:'smoothstep',
    style:{strokeWidth:1.9,stroke:run?.events.some(v=>v.step_id===e.to)?'#2ba68a':'#b6c1c7'},
    markerEnd:{type:MarkerType.ArrowClosed,color:'#afbac0'},
    animated:Boolean(run&&run.status==='running'&&scenario.nodes[run.progress]?.id===e.to)
  }));
  return{nodes,edges};
}
function ScenarioStepDetails({step,run}:{step:Step|null;run:Run|null}){
  if(!step)return <div className="sc-placeholder"><h3>노드를 선택하세요</h3><p>진행도를 따라 이동하는 노드를 누르면 입력·출력·검증 근거를 확인할 수 있습니다.</p></div>;
  const actual=run?.events.find(e=>e.step_id===step.id);
  return <div className="sc-details">
    <small className="sc-overline">{step.flow} · {step.action}</small>
    <h3>{step.label}</h3>
    <p><strong>담당:</strong> {step.flow} / 순번 {step.index+1}</p>
    <b>정의된 입력 파라미터</b>
    <pre>{JSON.stringify(step.params,null,2)}</pre>
    {actual?<><b>실제 상태 전이 출력</b><pre>{JSON.stringify(actual.output,null,2)}</pre>
       <p className="sc-good">✓ {actual.seq}번 단계 기록 완료 · {actual.origin}</p>
       <small>검사 로그: {actual.at}</small></>:<div className="sc-pending">아직 이 단계는 실행되지 않았습니다.</div>}
    <b>다음 노드</b><p>{step.next.length?step.next.join(', '):'최종 검증·완료'}</p>
  </div>;
}
function Console(){
  const[catalog,setCatalog]=useState<Catalogue|null>(null);
  const[health,setHealth]=useState<{n8n_configured:boolean;callback_auth_configured:boolean;n8n_status:string}|null>(null);
  const[selected,setSelected]=useState(1);
  const[engine,setEngine]=useState<'n8n'|'internal-test'>('n8n');
  const[run,setRun]=useState<Run|null>(null);
  const[selectedStep,setSelectedStep]=useState<string|null>(null);
  const[error,setError]=useState('');
  const[launching,setLaunching]=useState(false);
  const[tab,setTab]=useState<'node'|'timeline'|'state'|'verify'>('timeline');
  const[runHistory,setRunHistory]=useState<Array<{run_id:string;scenario_id:number;engine:string;status:string;created_at:string}>>([]);
  const[pollError,setPollError]=useState('');
  const[verificationShown,setVerificationShown]=useState(false);
  const activeRun=useRef<string|null>(null);
  const eventBox=useRef<HTMLDivElement>(null);
  const scenario=catalog?.scenarios.find(s=>s.scenario_id===selected);
  const canStart=Boolean(catalog)&&!launching&&Boolean(health)&&
    (engine==='internal-test'||Boolean(health?.n8n_configured&&health?.callback_auth_configured));
  const refreshHistory=useCallback(async()=>{
    try{const history=await api<{runs:typeof runHistory}>('/runs?limit=20');setRunHistory(history.runs)}
    catch{/* historical list is optional while API reconnects */}
  },[]);
  useEffect(()=>{
    let active=true;
    Promise.all([api<Catalogue>('/catalog'),api<{n8n_configured:boolean;callback_auth_configured:boolean;n8n_status:string}>('/health')])
      .then(([c,h])=>{if(!active)return;setCatalog(c);setHealth(h);setError('');})
      .catch(e=>{if(active)setError('API 연결 실패: '+String(e))});
    void refreshHistory();
    return()=>{active=false};
  },[refreshHistory]);
  const follow=useCallback(async(id:string)=>{
    try{
      const updated=await api<Run>('/runs/'+id);
      if(activeRun.current===id){setRun(updated);setPollError('')}
      if(updated.status!=='running')void refreshHistory();
    }catch(e){if(activeRun.current===id)setPollError(String(e))}
  },[refreshHistory]);
  useEffect(()=>{
    if(!run||run.status!=='running')return;
    const id=run.run_id;
    const timer=window.setInterval(()=>{void follow(id)},500);
    return()=>window.clearInterval(timer);
  },[run?.run_id,run?.status,follow]);
  useEffect(()=>{
    if(tab==='timeline'&&eventBox.current)eventBox.current.scrollTop=eventBox.current.scrollHeight;
  },[run?.events.length,tab]);
  const begin=async()=>{
    if(!scenario||!canStart)return;
    setLaunching(true);setError('');setPollError('');setVerificationShown(false);
    try{
      const start=await api<{run_id:string}>('/runs','POST',{scenario_id:selected,engine});
      activeRun.current=start.run_id;setRun(null);setSelectedStep(null);setTab('timeline');
      await follow(start.run_id);
    }catch(e){setError('실행 시작 실패: '+String(e))}
    finally{setLaunching(false)}
  };
  const changeScenario=(sid:number)=>{
    activeRun.current=null;setSelected(sid);setRun(null);setSelectedStep(null);
    setError('');setPollError('');setVerificationShown(false);setTab('timeline');
  };
  const viewPast=async(id:string)=>{
    try{const value=await api<Run>('/runs/'+id);
      activeRun.current=id;setRun(value);setSelected(value.scenario_id);
      setSelectedStep(null);setTab('timeline');setError('')}
    catch(e){setError(String(e))}
  };
  const cancel=async()=>{
    if(!run)return;try{await api('/runs/'+run.run_id+'/cancel','POST');await follow(run.run_id)}
    catch(e){setError(String(e))}
  };
  const verify=async()=>{
    if(!run)return;setVerificationShown(true);
    try{await api('/runs/'+run.run_id+'/verify');setTab('verify')}
    catch(e){setError(String(e))}
  };
  const graph=useMemo(()=>scenario&&catalog?graphFor(scenario,run,catalog.flows):{nodes:[],edges:[]},
    [scenario,catalog,run]);
  const step=selectedStep?scenario?.nodes.find(x=>x.id===selectedStep)||null:null;
  const activeFlows=new Set((run?.events||[]).map(e=>e.flow));
  return <div className="sc-layout">
    <aside className="sc-sidebar">
      <header><b>운영 시나리오 10개</b><small>합성 이벤트 검증</small></header>
      <div className="sc-sidebar-list">{catalog?.scenarios.map(s=><button key={s.scenario_id}
        onClick={()=>changeScenario(s.scenario_id)} className={selected===s.scenario_id?'active':''}>
        <span className="sc-num">{String(s.scenario_id).padStart(2,'0')}</span>
        <span><strong>{s.title}</strong><small>{s.count}개 노드 · {s.flows.length}개 플로우</small></span>
      </button>)}</div>
      <div className="sc-history">
        <h4>최근 실행 이력 <button title="새로고침" onClick={()=>void refreshHistory()}>↻</button></h4>
        {runHistory.slice(0,8).map(r=><button key={r.run_id} onClick={()=>void viewPast(r.run_id)}>
          <span>시나리오 {r.scenario_id} · {r.engine==='n8n'?'n8n':'내부 시험'}</span><small>{r.status}</small>
        </button>)}
      </div>
    </aside>
    <div className="sc-center">
      <div className="sc-titlebar">
        <div><small>FLOW LAB / 구조 시나리오</small><h2>{scenario?.title||'시나리오 불러오는 중'}</h2>
        <p>{scenario?.why}</p></div>
        <div className="sc-actions">
          <select aria-label="실행 엔진 선택" value={engine} onChange={e=>setEngine(e.target.value as typeof engine)}>
            <option value="n8n">n8n 실제 워크플로</option>
            <option value="internal-test">Python 내부 시험</option>
          </select>
          <button onClick={()=>void begin()} disabled={!canStart} className="sc-start">▶ {launching?'연결 중':'시나리오 실행'}</button>
          <button onClick={()=>void cancel()} disabled={run?.status!=='running'}>중단</button>
        </div>
      </div>
      <div className="sc-mode-info">
        {engine==='n8n'
        ? health?.n8n_configured&&health?.callback_auth_configured
          ? <span>● n8n 설정 확인 · 실제 Webhook → n8n HTTP 노드 → Python 검사 API</span>
          : <span className="sc-danger">● n8n 미설정 · 내부 시험 모드를 선택하거나 Docker n8n을 실행하세요</span>
        : <span className="sc-warn">● Python 내부 시험 · n8n 노드를 실행하지 않음 (동일 상태 전이 검사만 진행)</span>}
        {run&&<b>현재 실행: {run.engine==='n8n'?'n8n':'내부 시험'} · {run.status}</b>}
      </div>
      {error&&<div className="sc-error">{error}</div>}
      {pollError&&<div className="sc-error">상태 조회 실패: {pollError}</div>}
      <div className="sc-progress"><div style={{width:(run?.progress_pct||0)+'%'}}/><span>{run?run.progress+'/'+run.total+' 단계':'실행 전'}</span></div>
      <div className="sc-graph">
        {scenario?<ReactFlow<ConsoleNode,Edge> key={selected} nodes={graph.nodes} edges={graph.edges}
          nodeTypes={NODE_TYPES} onNodeClick={(_,n)=>{setSelectedStep(n.id);setTab('node')}}
          nodesDraggable={false} nodesConnectable={false} elementsSelectable fitView fitViewOptions={{padding:.17}}
          minZoom={.15} maxZoom={1.8}>
          <Background color="#d9e0e4" size={1} gap={18}/><Controls showInteractive={false}/>
          <MiniMap nodeColor={n=>FLOW_COLORS[(n.data as ConsoleNodeData).flow]||'#aaa'} zoomable pannable/>
        </ReactFlow>:null}
      </div>
      <div className="sc-flows">{Object.entries(catalog?.flows||{}).map(([id,title])=>
        <span key={id} className={activeFlows.has(id)?'live':''}>
          <i style={{background:FLOW_COLORS[id]}}/>{id} {title}
        </span>)}</div>
    </div>
    <aside className="sc-inspector">
      <nav className="sc-tabs">
        <button className={tab==='timeline'?'active':''} onClick={()=>setTab('timeline')}>진행 로그</button>
        <button className={tab==='node'?'active':''} onClick={()=>setTab('node')}>노드 I/O</button>
        <button className={tab==='state'?'active':''} onClick={()=>setTab('state')}>상태</button>
        <button className={tab==='verify'?'active':''} onClick={()=>setTab('verify')}>검증</button>
      </nav>
      <div className="sc-inspector-scroll" ref={eventBox}>
        {tab==='timeline'&&<div className="sc-timeline">
          <div className="sc-log-header"><h3>실시간 단계 실행 기록</h3><span>{run?.events.length||0}건</span></div>
          {!run?.events.length&&<p>실행 버튼을 누르면 n8n 또는 내부 시험이 단계별로 진행됩니다.</p>}
          {run?.events.map(e=><button className="sc-event" key={e.seq} onClick={()=>{setSelectedStep(e.step_id);setTab('node')}}>
            <span className="sc-dot" style={{background:FLOW_COLORS[e.flow]}}/>
            <span><small>#{e.seq} · {e.flow} {e.flow_label}</small><strong>{e.label}</strong>
            <em>출력: {JSON.stringify(e.output).slice(0,100)}</em></span>
          </button>)}
          {run?.status==='running'&&<div className="sc-event-pending">● 다음 노드 실행 대기 중...</div>}
        </div>}
        {tab==='node'&&<ScenarioStepDetails step={step||scenario?.nodes.find(s=>s.index===run?.progress)||null} run={run}/>}
        {tab==='state'&&<div className="sc-state">
          <h3>현재 시뮬레이션 상태</h3>
          {run?<><div className="sc-finances"><span>가상 현금 <strong>{num(run.state.cash)}원</strong></span>
            <span>예약 현금 <strong>{num(run.state.reserved)}원</strong></span>
            <span>실거래 주문 <strong>{run.state.live_orders_sent}건</strong></span></div>
            <h4>에이전트</h4>{Object.entries(run.state.agents).map(([id,a])=><div className="sc-agent" key={id}>
              <b>Agent {id}</b><span>{a.status}</span><small>{a.strategy||'할당 없음'}</small><small>포지션 {a.positions}주 · epoch {a.epoch}</small></div>)}
            <h4>전략 풀</h4>{Object.entries(run.state.strategies).map(([id,s])=><div className="sc-strategy" key={id}><strong>{id}</strong><span>{s.state}</span></div>)}
            <h4>검증 Worker</h4>{Object.entries(run.state.jobs).map(([id,j])=><div className="sc-strategy" key={id}><strong>{id} · {j.kind}</strong><span>{j.status}</span></div>)}
          </>:<p>실행을 시작하면 실제 저장된 검사 상태가 표시됩니다.</p>}
        </div>}
        {tab==='verify'&&<div className="sc-verification"><h3>자동 검증 조건</h3>
          {!run?<p>실행 전입니다.</p>:run.status==='running'?<p>최종 노드가 완료된 후 검증 결과가 산출됩니다.</p>:<>
            <div className={run.status==='passed'?'sc-pass':'sc-error'}>
              {run.status==='passed'?'전체 검증 통과':run.error||run.status}</div>
            <button onClick={()=>void verify()} disabled={run.status==='cancelled'}>API로 결과 재검사</button>
            {verificationShown&&<small>서버의 /runs/{'{run_id}'}/verify 호출 완료</small>}
            {run.verification.map(x=><div className="sc-check" key={x.name}>
              <span>{x.passed?'✓':'×'}</span><strong>{x.name}</strong></div>)}
          </>}
        </div>}
      </div>
      <div className="sc-inspector-footer">
        <div><b>데이터 출처</b><span>가상 전략·주문·금액. 실제 주식 거래 아님</span></div>
        <div><b>실행 출처</b><span>{run?.engine==='n8n'?'n8n HTTP 노드 콜백':run?.engine==='internal-test'?'Python 내부 검사':'선택 전'}</span></div>
        <div><b>조회 API</b><code>GET /api/v1/alpha/scenarios/runs/{run?.run_id?.slice(0,8)||'{id}'}</code></div>
      </div>
    </aside>
  </div>;
}
export default function ScenarioConsole(){return <ReactFlowProvider><Console/></ReactFlowProvider>}
