import {useCallback,useEffect,useMemo,useState} from 'react';
import {
  addEdge,Background,Controls,Handle,MarkerType,MiniMap,Position,
  ReactFlow,ReactFlowProvider,useEdgesState,useNodesState,
  type Connection,type Edge,type Node,type NodeProps,
} from '@xyflow/react';

type InputPort={name:string;annotation:string;required:boolean;default?:unknown};
type Operation={operation_id:string;engine:string;label:string;source?:string;inputs:InputPort[];output:string;execution:string;reason?:string|null};
type NodeData=Record<string,unknown>&{label:string;operation_id:string;engine:string;execution:string;ports:InputPort[];state:string};
type WorkNode=Node<NodeData,'investment'>;
type EdgeData=Record<string,unknown>&{target_input:string|null;output_path:string;on_status:'success'|'failed'|'any';optional:boolean;transform:'identity'|'int'|'float'|'str'|'length';when?:{path:string;op:string;value:unknown}};
type WorkEdge=Edge<EdgeData>;
type NodeSettings={operation_id:string;arguments:Record<string,unknown>;join:'ALL'|'ANY'|'QUORUM'|'ALL_SETTLED';quorum:number;optional:boolean;max_retries:number};
type WorkflowDef={name:string;description:string;nodes:Array<{id:string;operation_id:string;arguments:Record<string,unknown>;join:string;quorum:number;optional:boolean;max_retries:number;x:number;y:number}>;edges:Array<{id:string;source:string;target:string;target_input:string|null;output_path:string;on_status:string;optional:boolean;transform:string;when?:EdgeData['when']}>};
type NodeRun={node_id:string;operation_id:string;state:string;attempts:number;inputs?:unknown;output?:unknown;error?:unknown};
type RunData={run_id:string;workflow_id:string;version:number;state:string;mode:string;nodes:NodeRun[];events?:unknown[];error?:unknown};
type WorkflowListItem={id:string;name:string;latest_version:number;published_version:number|null};
const API='/studio-api/api/v1/alpha/investment';
const COLORS:Record<string,string>={
  nautilus:'#e37328',tradingview:'#2685bd',quantlab:'#2685bd',vectorbt:'#13a188',qlib:'#13a188',
  chronos:'#13a188',tradingagents:'#9368bc',finrobot:'#9368bc',rdagent:'#9368bc',
  sb3:'#9571c0',rllib:'#9571c0',riskfolio:'#dd5959',pypfopt:'#dd5959',
  finrl:'#dd5959',orchestration:'#e3a12d',control:'#667680'
};
async function request<T>(path:string,method='GET',data?:unknown):Promise<T>{
  const response=await fetch(API+path,{
    method,headers:{'Content-Type':'application/json'},
    body:data===undefined?undefined:JSON.stringify(data),
    credentials:'same-origin',
  });
  const payload:unknown=await response.json().catch(()=>({detail:response.statusText}));
  if(!response.ok)throw new Error(
    typeof payload==='object'&&payload!==null&&'detail' in payload
      ?JSON.stringify((payload as {detail:unknown}).detail):'API 요청 실패: '+response.status);
  return payload as T;
}
function defaultSettings(operation_id:string):NodeSettings{
  return {operation_id,arguments:{},join:'ALL',quorum:1,optional:false,max_retries:0};
}
function NodeCard({data,selected}:NodeProps<WorkNode>){
  const visible=data.ports.filter(p=>p.name!=='self'&&p.name!=='cls'&&p.name!=='kwargs'&&p.name!=='args').slice(0,6);
  return <div className={'invest-card'+(selected?' selected':'')} style={{borderLeftColor:COLORS[data.engine]||'#a1a8aa'}}>
    <div className="invest-card-header"><b>{data.label}</b><span>{data.engine}</span></div>
    <p>{data.operation_id}</p>
    <small className={'state-'+data.state}>{data.state==='waiting'?'대기':data.state==='success'?'성공':data.state==='failed'?'실패':data.state==='waiting_approval'?'승인 대기':data.execution}</small>
    {visible.length?visible.map((p,i)=><Handle key={p.name} type="target" id={p.name} position={Position.Left} style={{top:22+i*13,width:10,height:10}} title={p.name+' : '+p.annotation}/>):<Handle type="target" id="input" position={Position.Left}/>}
    <Handle type="source" id="result" position={Position.Right} title={'result : '+data.operation_id}/>
  </div>;
}
const TYPES={investment:NodeCard};
const edgeStyle={stroke:'#8598a4',strokeWidth:1.8};
const markerEnd={type:MarkerType.ArrowClosed,color:'#8598a4'};
const stringValue=(v:unknown)=>typeof v==='string'?v:JSON.stringify(v,null,2);
const parseVal=(v:string):unknown=>{try{return JSON.parse(v)}catch{return v}};
function buildNode(id:string,op:Operation,x:number,y:number,state='waiting'):WorkNode{
  return{id,type:'investment',position:{x,y},data:{label:op.label,engine:op.engine,operation_id:op.operation_id,execution:op.execution,ports:op.inputs||[],state}};
}
function makeEdge(id:string,source:string,target:string, data:EdgeData):WorkEdge{
  return{id,source,target,type:'smoothstep',style:edgeStyle,markerEnd,data,
    label:data.on_status==='success'?'':data.on_status.toUpperCase()};
}
function edgeOptions(target_input:string|null=null):EdgeData{
  return {target_input,output_path:'result',on_status:'success',optional:false,transform:'identity'};
}
function Editor(){
  const[nodes,setNodes,onNodesChange]=useNodesState<WorkNode>([]);
  const[edges,setEdges,onEdgesChange]=useEdgesState<WorkEdge>([]);
  const[ops,setOps]=useState<Operation[]>([]);
  const[settings,setSettings]=useState<Record<string,NodeSettings>>({});
  const[wfId,setWfId]=useState<string|null>(null);
  const[version,setVersion]=useState<number|null>(null);
  const[published,setPublished]=useState<number|null>(null);
  const[name,setName]=useState('새 주식 투자 워크플로');
  const[description,setDescription]=useState('NautilusTrader 중심 12개 엔진 운영 플로우');
  const[selNode,setSelNode]=useState<string|null>(null);
  const[selEdge,setSelEdge]=useState<string|null>(null);
  const[search,setSearch]=useState('');
  const[engineFilter,setEngineFilter]=useState('');
  const[workflows,setWorkflows]=useState<WorkflowListItem[]>([]);
  const[status,setStatus]=useState('API 연결 확인 중');
  const[busy,setBusy]=useState(false);
  const[run,setRun]=useState<RunData|null>(null);
  const[inspect,setInspect]=useState<'settings'|'results'|'history'>('settings');
  const[approveName,setApproveName]=useState('');
  const[listOpen,setListOpen]=useState(false);
  const catalogue=useMemo(()=>new Map(ops.map(op=>[op.operation_id,op])),[ops]);
  const active=nodes.find(n=>n.id===selNode);
  const activeEdge=edges.find(e=>e.id===selEdge);
  const inspectedRun=run?.nodes.find(r=>r.node_id===selNode);
  const filtered=useMemo(()=>ops.filter(op=>(!engineFilter||op.engine===engineFilter)&&
    (op.label+' '+op.operation_id).toLowerCase().includes(search.toLowerCase())),[ops,engineFilter,search]);
  const engineNames=useMemo(()=>Array.from(new Set(ops.map(o=>o.engine))).sort(),[ops]);
  const refresh=useCallback(async()=>{
    try{
      const[palette,list]=await Promise.all([
        request<{nodes:Operation[]}>('/node-types'),
        request<{items:WorkflowListItem[]}>('/workflows')
      ]);
      setOps(palette.nodes);
      setWorkflows(list.items);
      setStatus('실제 API 연결됨 · '+palette.nodes.length+'개 기능 노드 조회');
    }catch(error){setStatus('API 연결 실패: '+String(error))}
  },[]);
  useEffect(()=>{void refresh()},[refresh]);
  const nodeDef=useCallback((n:WorkNode)=>{
    const s=settings[n.id]||defaultSettings(n.data.operation_id);
    return {id:n.id,operation_id:n.data.operation_id,arguments:s.arguments,join:s.join,
      quorum:s.quorum,optional:s.optional,max_retries:s.max_retries,x:n.position.x,y:n.position.y};
  },[settings]);
  const definition=useCallback(():WorkflowDef=>({
    name,description,nodes:nodes.map(nodeDef),
    edges:edges.map(e=>({
      id:e.id,source:e.source,target:e.target,target_input:e.data?.target_input||null,
      output_path:e.data?.output_path||'result',on_status:e.data?.on_status||'success',
      optional:Boolean(e.data?.optional),transform:e.data?.transform||'identity',
      ...(e.data?.when?{when:e.data.when}:{})
    }))
  }),[name,description,nodes,edges,nodeDef]);
  const addNode=(op:Operation)=>{
    const id='node_'+Math.random().toString(36).slice(2,10);
    setNodes(prev=>[...prev,buildNode(id,op,100+prev.length%4*270,90+Math.floor(prev.length/4)*150)]);
    setSettings(prev=>({...prev,[id]:defaultSettings(op.operation_id)}));
    setSelNode(id);setSelEdge(null);setInspect('settings');
  };
  const onConnect=useCallback((link:Connection)=>{
    if(!link.source||!link.target||link.source===link.target)return;
    setEdges(prev=>addEdge(makeEdge('edge_'+Math.random().toString(36).slice(2),link.source,link.target,edgeOptions(link.targetHandle==='input'?null:link.targetHandle)),prev));
  },[setEdges]);
  const updateSettings=(patch:Partial<NodeSettings>)=>{
    if(!active)return;
    setSettings(prev=>({...prev,[active.id]:{...(prev[active.id]||defaultSettings(active.data.operation_id)),...patch}}));
  };
  const updateEdge=(patch:Partial<EdgeData>)=>{
    if(!activeEdge)return;
    setEdges(prev=>prev.map(e=>e.id===activeEdge.id?makeEdge(e.id,e.source,e.target,{...edgeOptions(),...e.data,...patch}):e));
  };
  const load=(data:{workflow_id:string;version:number;published_version:number|null;definition:WorkflowDef})=>{
    const newNodes=data.definition.nodes.map(n=>buildNode(n.id,catalogue.get(n.operation_id)||{
      operation_id:n.operation_id,engine:n.operation_id.split('.')[0],label:n.operation_id,
      inputs:[],output:'Any',execution:'missing'
    },n.x,n.y));
    const newEdges=data.definition.edges.map(e=>makeEdge(e.id,e.source,e.target,{
      ...edgeOptions(),target_input:e.target_input,output_path:e.output_path,
      on_status:e.on_status as EdgeData['on_status'],optional:e.optional,
      transform:e.transform as EdgeData['transform'],when:e.when
    }));
    setNodes(newNodes);setEdges(newEdges);
    setSettings(Object.fromEntries(data.definition.nodes.map(n=>[n.id,{
      operation_id:n.operation_id,arguments:n.arguments,join:n.join as NodeSettings['join'],
      quorum:n.quorum,optional:n.optional,max_retries:n.max_retries
    }])));
    setWfId(data.workflow_id);setVersion(data.version);setPublished(data.published_version);
    setName(data.definition.name);setDescription(data.definition.description);
    setRun(null);setSelNode(null);setSelEdge(null);
  };
  const chooseWorkflow=async(id:string)=>{
    try{const result=await request<{workflow_id:string;version:number;published_version:number|null;definition:WorkflowDef}>('/workflows/'+id);load(result);setStatus('저장된 버전 '+result.version+' 불러옴')}catch(error){setStatus(String(error))}
    setListOpen(false);
  };
  const newWorkflow=()=>{
    setNodes([]);setEdges([]);setSettings({});setWfId(null);setVersion(null);setPublished(null);
    setName('새 주식 투자 워크플로');setDescription('');setRun(null);setSelNode(null);setSelEdge(null);
  };
  const removeWorkflow=async()=>{
    if(!wfId||!window.confirm('워크플로 정의와 저장 버전을 삭제합니다. 기존 실행 로그는 보존됩니다. 계속하시겠습니까?'))return;
    try{await request('/workflows/'+wfId,'DELETE');newWorkflow();await refresh();setStatus('워크플로 정의 삭제 완료. 과거 실행 기록은 보존됩니다.')}
    catch(error){setStatus('워크플로 삭제 실패: '+String(error))}
  };
  const save=async():Promise<{workflow_id:string;version:number}|null>=>{
    setBusy(true);
    try{
      const d=definition();
      const validated=await request<{valid:boolean}>('/workflows/validate','POST',d);
      if(!validated.valid)throw new Error('유효하지 않은 연결');
      const updated=wfId&&version
        ?await request<{workflow_id:string;version:number}>('/workflows/'+wfId,'PUT',{expected_version:version,definition:d})
        :await request<{workflow_id:string;version:number}>('/workflows','POST',d);
      setWfId(updated.workflow_id);setVersion(updated.version);setStatus('워크플로 버전 '+updated.version+' 저장됨');
      await refresh();
      return updated;
    }catch(error){setStatus('저장 실패: '+String(error));return null}
    finally{setBusy(false)}
  };
  const validate=async()=>{
    try{const result=await request<{order:string[];parallel_roots:string[];warnings:unknown[]}>('/workflows/validate','POST',definition());
      setStatus('검증 성공 · 실행 순서 '+result.order.join(' → ')+' · 병렬 시작 '+result.parallel_roots.join(', ')+
        (result.warnings.length?' · 실행 제한 '+result.warnings.length+'개':''));
    }catch(error){setStatus('그래프 검증 실패: '+String(error))}
  };
  const publish=async()=>{
    const latest=await save();if(!latest)return;
    try{await request('/workflows/'+latest.workflow_id+'/versions/'+latest.version+'/publish','POST');
      setPublished(latest.version);setStatus('버전 '+latest.version+' 게시 완료 (실거래 승인이 아님)');
    }catch(error){setStatus('게시 실패: '+String(error))}
  };
  const execute=async(mode:'dry_run'|'research')=>{
    let id=wfId;
    if(!id||!version){const created=await save();if(!created)return;id=created.workflow_id}
    setBusy(true);setInspect('results');
    try{const payload=await request<RunData>('/workflows/'+id+'/runs','POST',{mode,background:false});
      setRun(payload);setNodes(prev=>prev.map(n=>({...n,data:{...n.data,state:payload.nodes.find(x=>x.node_id===n.id)?.state||'waiting'}})));
      setStatus('워크플로 실행 '+payload.state+' · '+payload.run_id);
    }catch(error){setStatus('실행 실패: '+String(error))}
    finally{setBusy(false)}
  };
  const approve=async(nodeId:string)=>{
    if(!run||!approveName.trim())return;
    try{const payload=await request<RunData>('/runs/'+run.run_id+'/nodes/'+nodeId+'/approve','POST',{approver:approveName,note:'내부 운영자 승인'});
      setRun(payload);setStatus('승인 처리됨. 결과 '+payload.state+' (실거래 승인이 아님)');
    }catch(error){setStatus('승인 실패: '+String(error))}
  };
  const deleteSelected=()=>{
    if(selNode){
      setNodes(prev=>prev.filter(n=>n.id!==selNode));setEdges(prev=>prev.filter(e=>e.source!==selNode&&e.target!==selNode));
      setSelNode(null);
    }else if(selEdge){setEdges(prev=>prev.filter(e=>e.id!==selEdge));setSelEdge(null)}
  };
  const changeJSON=(text:string)=>{
    if(!active)return;try{const parsed=JSON.parse(text);if(parsed===null||Array.isArray(parsed)||typeof parsed!=='object')throw new Error('객체만 가능');
      updateSettings({arguments:parsed as Record<string,unknown>});setStatus('JSON 인자 적용')}catch(error){setStatus('입력값 JSON 오류: '+String(error))}
  };
  return <div className="invest-shell">
    <header className="invest-top">
      <div className="invest-brand"><b>Autonomous Investor</b><small>12-Engine Node Studio</small></div>
      <input className="invest-title" value={name} onChange={e=>setName(e.target.value)} aria-label="워크플로 이름"/>
      <div className="invest-top-actions">
        <button onClick={()=>setListOpen(x=>!x)}>불러오기</button>
        <button onClick={newWorkflow}>새 워크플로</button>
        <button disabled={!wfId||busy} onClick={()=>void removeWorkflow()}>삭제</button>
        <button onClick={()=>void validate()}>검증</button>
        <button disabled={busy} onClick={()=>void save()}>저장</button>
        <button disabled={busy||!nodes.length} onClick={()=>void publish()}>버전 게시</button>
        <button disabled={busy||!nodes.length} onClick={()=>void execute('dry_run')}>시험 실행</button>
        <button disabled={busy||!nodes.length} className="invest-primary" onClick={()=>void execute('research')}>연구 실행</button>
      </div>
    </header>
    {listOpen&&<div className="invest-load-menu"><b>저장된 워크플로</b>{workflows.map(w=><button key={w.id} onClick={()=>void chooseWorkflow(w.id)}>{w.name} <small>v{w.latest_version} / 게시 {w.published_version||'-'}</small></button>)}</div>}
    <aside className="invest-left">
      <div className="invest-section-title"><b>실제 Python 기능 노드</b><small>{ops.length}종</small></div>
      <input value={search} onChange={e=>setSearch(e.target.value)} placeholder="함수/노드 검색"/>
      <select value={engineFilter} onChange={e=>setEngineFilter(e.target.value)} aria-label="엔진 선택"><option value="">전체 12개 엔진·서비스</option>{engineNames.map(v=><option key={v}>{v}</option>)}</select>
      <div className="invest-palette-scroll">{filtered.map(op=><button key={op.operation_id} className="invest-palette-item" onClick={()=>addNode(op)}>
        <strong style={{color:COLORS[op.engine]||'#536e83'}}>{op.engine}</strong>
        <span>{op.label.split(' · ').slice(1).join(' · ')||op.operation_id}</span>
        <small className={op.execution==='ready'?'allowed':'blocked'}>{op.execution}</small>
      </button>)}</div>
      <div className="invest-help">함수를 여러 번 배치할 수 있습니다. 연결선은 실제 입력·출력 데이터 경로를 지정합니다.</div>
    </aside>
    <main className="invest-main">
      <div className="invest-canvas-bar">
        <b>운영 워크플로</b><span>노드 {nodes.length} · 연결 {edges.length} · v{version||'-'} · 게시 {published||'-'}</span>
        <button onClick={deleteSelected}>선택 삭제</button>
      </div>
      <div className="invest-canvas">
        <ReactFlow<WorkNode,WorkEdge> nodes={nodes} edges={edges} nodeTypes={TYPES} onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange} onConnect={onConnect}
          onNodeClick={(_,node)=>{setSelNode(node.id);setSelEdge(null);setInspect('settings')}}
          onEdgeClick={(_,edge)=>{setSelEdge(edge.id);setSelNode(null);setInspect('settings')}}
          onPaneClick={()=>{setSelNode(null);setSelEdge(null)}} fitView minZoom={0.18} maxZoom={2} deleteKeyCode={['Backspace','Delete']}>
          <Background gap={18} size={1} color="#dce1e4"/><MiniMap nodeColor={n=>COLORS[(n.data as NodeData).engine]||'#a6b4bc'}/><Controls/>
        </ReactFlow>
      </div>
    </main>
    <aside className="invest-right">
      <div className="invest-right-header"><b>노드 설정 / 실제 실행 결과</b>
        <nav><button onClick={()=>setInspect('settings')} className={inspect==='settings'?'active':''}>설정</button>
          <button onClick={()=>setInspect('results')} className={inspect==='results'?'active':''}>결과</button>
          <button onClick={()=>setInspect('history')} className={inspect==='history'?'active':''}>실행 기록</button>
        </nav></div>
      <div className="invest-inspect">
        {inspect==='settings'&&active&&<section>
          <h3>{active.data.label}</h3><code>{active.data.operation_id}</code>
          <p>상태: {active.data.execution}</p>
          <label>합류 조건
            <select value={(settings[active.id]||defaultSettings(active.data.operation_id)).join}
              onChange={e=>updateSettings({join:e.target.value as NodeSettings['join']})}>
              {['ALL','ANY','QUORUM','ALL_SETTLED'].map(x=><option key={x}>{x}</option>)}
            </select>
          </label>
          <label>QUORUM 최소 성공 수
            <input type="number" min="1" max="40" value={settings[active.id]?.quorum||1}
              onChange={e=>updateSettings({quorum:Number(e.target.value)})}/>
          </label>
          <label>재시도 횟수 (최대 2)
            <input type="number" min="0" max="2" value={settings[active.id]?.max_retries||0}
              onChange={e=>updateSettings({max_retries:Number(e.target.value)})}/>
          </label>
          <label className="invest-check"><input type="checkbox" checked={Boolean(settings[active.id]?.optional)}
            onChange={e=>updateSettings({optional:e.target.checked})}/> 실패 허용(선택 노드)</label>
          <b>Python 함수 입력 파라미터</b>
          {active.data.ports.map(p=><div className="invest-port-doc" key={p.name}>
            <strong>{p.name} {p.required?'*':''}</strong><span>{p.annotation}</span>
          </div>)}
          <b>노드 인자 (JSON 객체)</b>
          <textarea key={active.id} defaultValue={JSON.stringify(settings[active.id]?.arguments||{},null,2)}
            rows={11} onBlur={e=>changeJSON(e.target.value)} spellCheck={false}/>
          <small>입력 포트를 연결하면 연결선 출력이 이 JSON 필드를 덮어씁니다.</small>
        </section>}
        {inspect==='settings'&&activeEdge&&<section>
          <h3>연결선 설정</h3><p>{activeEdge.source} → {activeEdge.target}</p>
          <label>목표 입력 포트<input value={activeEdge.data?.target_input||''} onChange={e=>updateEdge({target_input:e.target.value||null})}/></label>
          <label>상위 출력 경로<input value={activeEdge.data?.output_path||'result'} onChange={e=>updateEdge({output_path:e.target.value})}/></label>
          <label>전달할 상태<select value={activeEdge.data?.on_status||'success'} onChange={e=>updateEdge({on_status:e.target.value as EdgeData['on_status']})}>
            <option>success</option><option>failed</option><option>any</option></select></label>
          <label>데이터 변환<select value={activeEdge.data?.transform||'identity'} onChange={e=>updateEdge({transform:e.target.value as EdgeData['transform']})}>
            {['identity','str','int','float','length'].map(x=><option key={x}>{x}</option>)}</select></label>
          <label className="invest-check"><input type="checkbox" checked={Boolean(activeEdge.data?.optional)} onChange={e=>updateEdge({optional:e.target.checked})}/> 선택 연결선</label>
          <b>조건 분기 (없으면 항상 평가)</b>
          <label>조건 출력 경로<input value={activeEdge.data?.when?.path||''} onChange={e=>updateEdge(e.target.value?{when:{path:e.target.value,op:activeEdge.data?.when?.op||'eq',value:activeEdge.data?.when?.value??true}}:{when:undefined})}/></label>
          <label>비교 연산<select value={activeEdge.data?.when?.op||'eq'} onChange={e=>updateEdge({when:{path:activeEdge.data?.when?.path||'result',op:e.target.value,value:activeEdge.data?.when?.value}})}>
            {['eq','ne','gt','gte','lt','lte','in','exists'].map(x=><option key={x}>{x}</option>)}</select></label>
          <label>조건 비교값<input value={stringValue(activeEdge.data?.when?.value??true)} onChange={e=>updateEdge({when:{path:activeEdge.data?.when?.path||'result',op:activeEdge.data?.when?.op||'eq',value:parseVal(e.target.value)}})}/></label>
        </section>}
        {inspect==='settings'&&!active&&!activeEdge&&<p>왼쪽에서 실제 엔진 함수를 추가하거나 캔버스 노드·연결선을 선택하세요.</p>}
        {inspect==='results'&&<section>
          <div className="invest-notice">실행 결과는 백엔드에서 반환합니다. 가짜 시장 데이터나 가짜 수익률은 생성하지 않습니다.</div>
          {!run?<p>아직 실행 기록이 없습니다.</p>:<>
            <p>실행 ID: <code>{run.run_id}</code></p><p>상태: <strong>{run.state}</strong></p>
            {run.nodes.map(n=><button key={n.node_id} className="invest-result-row" onClick={()=>setSelNode(n.node_id)}>
              <strong>{n.node_id}</strong><span>{n.state}</span></button>)}
            {inspectedRun&&<><h4>{inspectedRun.node_id} 입력·출력</h4><pre>{JSON.stringify(inspectedRun,null,2)}</pre></>}
            {run.state==='waiting_approval'&&<div className="invest-approval">
              <p>승인 대기 — 검증용 워크플로 승인입니다. 실제 매매 승인이 아닙니다.</p>
              <input placeholder="내부 운영자 식별명" value={approveName} onChange={e=>setApproveName(e.target.value)}/>
              {run.nodes.filter(n=>n.state==='waiting_approval').map(n=><button key={n.node_id} onClick={()=>void approve(n.node_id)}>노드 {n.node_id} 승인 후 재개</button>)}
            </div>}
          </>}
        </section>}
        {inspect==='history'&&<section><h3>저장된 실행 이력</h3>
          {run?.events?.length?run.events.map((item,i)=><pre key={i}>{JSON.stringify(item,null,2)}</pre>):<p>실행 후 기록이 여기에 표시됩니다.</p>}
          <p>워크플로 버전: {version||'-'}</p><p>게시된 버전: {published||'-'}</p>
          <small>연구 실행과 실거래는 구분됩니다. 실제 브로커 주문 호출은 API에서 차단돼 있습니다.</small>
        </section>}
      </div>
    </aside>
    <footer className="invest-footer"><span>● NautilusTrader 메인 · TradingView Pine 원본</span><span className="invest-message">{status}</span><b>LIVE TRADING OFF</b></footer>
  </div>;
}
export default function InvestmentStudio(){return <ReactFlowProvider><Editor/></ReactFlowProvider>}
