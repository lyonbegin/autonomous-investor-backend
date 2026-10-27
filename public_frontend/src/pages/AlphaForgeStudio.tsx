import {useCallback,useEffect,useMemo,useRef,useState} from 'react';
import {
  ReactFlow, ReactFlowProvider, Background, Controls, MiniMap, Handle,
  Position, MarkerType, addEdge, useNodesState, useEdgesState,
  type Node, type Edge, type NodeProps, type Connection,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import './AlphaForgeStudio.css';

/** Phase 1: observable UI/editor recreation based on the supplied screenshot.
 *  All sample data and run outputs are explicitly local DEMO values.
 *  Native AlphaForge, Pine, and broker execution are NOT implied.
 */
type Group = 'source'|'screen'|'research'|'risk'|'test'|'output';
type Setting = string|number|boolean;
type NodeStatus = 'idle'|'demo'|'unavailable'|'error';
type ForgeData = Record<string,unknown> & {
  title:string; subtitle:string; operation:string; group:Group;
  settings:Record<string,Setting>; status:NodeStatus;
};
type ForgeNode = Node<ForgeData,'forge'>;
type ForgeEdge = Edge;
type Definition = {operation:string;title:string;subtitle:string;group:Group;description:string;settings:Record<string,Setting>};
type Snapshot = {nodes:ForgeNode[];edges:ForgeEdge[]};
type StepResult={nodeId:string;label:string;state:NodeStatus;result:Record<string,unknown>;startedAt:string};
type RunRecord={runId:string;startedAt:string;status:'demo_complete'|'partial'|'invalid';steps:StepResult[];errors:string[]};
const KEY='autonomous-investor-alphaforge-phase1-v1';
const GROUPS:{key:Group;title:string;accent:string}[]=[
  {key:'source',title:'① 종목 및 데이터 가져오기',accent:'#178ed0'},
  {key:'screen',title:'② 차트·종목 선별',accent:'#7b52bd'},
  {key:'research',title:'③ AI 분석·전문가 합의',accent:'#e1a12d'},
  {key:'risk',title:'④ 위험 및 자본',accent:'#e15e66'},
  {key:'test',title:'⑤ 백테스트·검증',accent:'#12a0ac'},
  {key:'output',title:'⑥ 보고서·알림',accent:'#208879'}
];
const LIBRARY:Definition[]=[
  {operation:'source.kr',title:'한국 주식 가져오기',subtitle:'data.source · korea',group:'source',description:'한국 주식 목록을 가져오는 노드. 현재 샘플 종목만 사용합니다.',settings:{limit:120,market:'KR'}},
  {operation:'source.us',title:'미국 주식 가져오기',subtitle:'data.source · america',group:'source',description:'미국 주식 수집 노드. 현재 샘플 종목만 사용합니다.',settings:{limit:120,market:'US'}},
  {operation:'source.sec',title:'SEC 원문 가져오기',subtitle:'filing.sec',group:'source',description:'미국 SEC 공시 수집. 백엔드 연결 전에는 호출하지 않습니다.',settings:{form_type:'10-K',limit:25}},
  {operation:'source.dart',title:'DART 공시 가져오기',subtitle:'filing.dart',group:'source',description:'한국 DART 공시 수집 기능.',settings:{days:30,limit:25}},
  {operation:'source.tradingview',title:'TradingView Pine 전략',subtitle:'pine · strategy catalog',group:'source',description:'공개 Pine 전략 소스 수집. 실제 수집은 2단계 백엔드 연결 대상입니다.',settings:{script_type:'strategies',limit:50}},
  {operation:'source.prices',title:'OHLCV 시장 데이터',subtitle:'data.market.history',group:'source',description:'시계열 데이터 입력 노드.',settings:{market:'KR',horizon:'1d',lookback:365}},
  {operation:'source.institutional',title:'기관·외국인 수급',subtitle:'data.flow',group:'source',description:'기관 및 외국인 수급 데이터 수집.',settings:{lookback_days:20}},
  {operation:'screen.basic',title:'기본 스크리닝',subtitle:'data.screen · price/volume',group:'screen',description:'최소 가격·거래량·시가총액·종목 상한으로 필터링합니다.',settings:{min_price:1000,min_volume:50000,min_market_cap:50000000000,universe_cap:120,top_n:15}},
  {operation:'screen.vcp',title:'차트 VCP 선별',subtitle:'tech.vcp',group:'screen',description:'VCP 변동성 수축 패턴 선별 노드. 계산 원본은 검증되지 않았습니다.',settings:{lookback:90,contraction_threshold:0.65}},
  {operation:'screen.foreign',title:'외국인 수급 선별',subtitle:'flow.foreign',group:'screen',description:'외국인 매수 흐름 기반 선별.',settings:{lookback_days:20,min_net_buy:0}},
  {operation:'screen.freshness',title:'데이터 신선도 검사',subtitle:'quality.freshness',group:'screen',description:'노드 입력 데이터의 최신 시각 검사.',settings:{max_age_minutes:60,strict:true}},
  {operation:'research.consensus',title:'대가 합의 13',subtitle:'AI 분석 · 전문가 투표',group:'research',description:'A~M 전문가를 선택해 합의값을 설정합니다. 실제 전문가 AI 호출은 연결되지 않았습니다.',settings:{gurus:'A,B,C,D,E,F,G,H,I,J,K,L,M',vote_threshold:0.75,top_n:15,min_price:1000,min_volume:50000,min_market_cap:50000000000,universe_cap:120}},
  {operation:'research.bullbear',title:'강세/약세 토론',subtitle:'AI 분석 · bull/bear',group:'research',description:'강세·약세 토론 UI; 모델 답변을 생성하지 않습니다.',settings:{rounds:2,model:'미연결'}},
  {operation:'research.finrobot',title:'FinRobot 기업분석',subtitle:'engine.finrobot',group:'research',description:'FinRobot 래퍼 연결 위치.',settings:{ticker:'',method:'research'}},
  {operation:'research.tradingagents',title:'TradingAgents 연구',subtitle:'engine.tradingagents',group:'research',description:'TradingAgents 래퍼 연결 위치.',settings:{asset_type:'equity'}},
  {operation:'research.chronos',title:'Chronos 시계열 예측',subtitle:'engine.chronos',group:'research',description:'Chronos 래퍼 연결 위치.',settings:{horizon:10}},
  {operation:'risk.allocate',title:'리스크 배정',subtitle:'portfolio.risk',group:'risk',description:'투자 규모·집중도·손실 제한을 입력하는 정책 노드.',settings:{max_weight_pct:10,max_drawdown_pct:10,cash_buffer_pct:20}},
  {operation:'risk.riskfolio',title:'Riskfolio 최적화',subtitle:'engine.riskfolio',group:'risk',description:'Riskfolio 래퍼 연결 위치.',settings:{objective:'Sharpe'}},
  {operation:'risk.pypfopt',title:'PyPortfolioOpt 비중',subtitle:'engine.pypfopt',group:'risk',description:'PyPortfolioOpt 연결 위치.',settings:{objective:'min_volatility'}},
  {operation:'test.backtest',title:'백테스트 실행',subtitle:'quant.backtest',group:'test',description:'백테스트 실행 결과 패널. 실제 매매성과를 계산하지 않습니다.',settings:{initial_capital:10000000,commission_bps:5,slippage_bps:2}},
  {operation:'test.vectorbt',title:'vectorbt 빠른 검증',subtitle:'engine.vectorbt',group:'test',description:'vectorbt 실제 래퍼 연결은 2단계 적용 대상입니다.',settings:{fees_bps:5}},
  {operation:'test.nautilus',title:'NautilusTrader 검증',subtitle:'engine.nautilus',group:'test',description:'NautilusTrader 백테스트 연결 예정. 실거래를 실행하지 않습니다.',settings:{mode:'backtest',live_enabled:false}},
  {operation:'output.table',title:'결과 표',subtitle:'report.table',group:'output',description:'노드별 결과를 표로 출력.',settings:{show_status:true}},
  {operation:'output.telegram',title:'텔레그램 알림',subtitle:'notification.telegram',group:'output',description:'외부 알림 전송은 이 단계에서 실행하지 않습니다.',settings:{enabled:false}},
  {operation:'output.export',title:'JSON 내보내기',subtitle:'report.export',group:'output',description:'그래프 정의를 JSON 파일로 저장.',settings:{format:'json'}}
];
const DEF_MAP=new Map(LIBRARY.map(d=>[d.operation,d]));
const EXPERTS=['A 오닐','B 버핏','C 그레이엄','D 린치','E 코스톨라니','F 템플턴','G 달리오','H 피셔','I 그린블라트','J 모부신','K 마크스','L 하워드','M 퀀트'];
const accent:Record<Group,string>=Object.fromEntries(GROUPS.map(g=>[g.key,g.accent])) as Record<Group,string>;
const arrow={type:MarkerType.ArrowClosed,color:'#aababc'};
function makeNode(op:string,id:string,x:number,y:number):ForgeNode{
  const d=DEF_MAP.get(op)??LIBRARY[0];
  return{id,type:'forge',position:{x,y},data:{operation:op,title:d.title,subtitle:d.subtitle,group:d.group,settings:{...d.settings},status:'idle'}};
}
function makeEdge(source:string,target:string,index:number):ForgeEdge{
  return {id:'line-'+index+'-'+source+'-'+target,source,target,type:'smoothstep',style:{stroke:'#aababc',strokeWidth:1.7},markerEnd:arrow};
}
function template(which:string):Snapshot{
  if(which==='blank')return{nodes:[],edges:[]};
  if(which==='pine'){
    const defs:[string,string,number,number][]=[
      ['source','source.tradingview',60,140],['prices','source.prices',60,330],
      ['fast','test.vectorbt',355,140],['nautilus','test.nautilus',650,140],
      ['risk','risk.allocate',950,140],['report','output.table',1250,140]];
    return {nodes:defs.map(([id,op,x,y])=>makeNode(op,id,x,y)),edges:[['source','fast'],['prices','fast'],['fast','nautilus'],['nautilus','risk'],['risk','report']].map(([a,b],i)=>makeEdge(a,b,i))};
  }
  if(which==='simple'){
    return {nodes:[makeNode('source.kr','stocks',70,175),makeNode('screen.basic','basic',390,175),makeNode('output.table','result',720,175)],edges:[makeEdge('stocks','basic',0),makeEdge('basic','result',1)]};
  }
  const defs:[string,string,number,number][]=[
    ['kr','source.kr',30,90],['us','source.us',30,290],
    ['filter','screen.basic',335,180],['experts','research.consensus',645,180],
    ['risk','risk.allocate',955,180],['debate','research.bullbear',1250,65],
    ['backtest','test.backtest',1250,295]
  ];
  return {nodes:defs.map(([id,op,x,y])=>makeNode(op,id,x,y)),
    edges:[['kr','filter'],['us','filter'],['filter','experts'],['experts','risk'],['risk','debate'],['risk','backtest']].map(([a,b],i)=>makeEdge(a,b,i))};
}
function parseSnapshot(value:unknown):Snapshot{
  if(!value||typeof value!=='object')throw new Error('그래프 JSON 형식이 잘못되었습니다.');
  const raw=value as Record<string,unknown>;
  if(!Array.isArray(raw.nodes)||!Array.isArray(raw.edges)||raw.nodes.length>120||raw.edges.length>300)throw new Error('노드/연결 개수 제한을 초과했거나 형식이 다릅니다.');
  const nodes:ForgeNode[]=raw.nodes.map((n:unknown)=>{
    const v=n as Record<string,unknown>, d=v.data as Record<string,unknown>, p=v.position as Record<string,number>;
    if(!v||typeof v.id!=='string'||!d||typeof d.operation!=='string'||!DEF_MAP.has(d.operation)||!p||!Number.isFinite(p.x)||!Number.isFinite(p.y))throw new Error('지원하지 않는 노드 정보입니다.');
    const made=makeNode(d.operation,v.id,p.x,p.y);
    const old=d.settings&&typeof d.settings==='object' ? d.settings as Record<string,unknown>:{};
    made.data.settings={...made.data.settings,...(Object.fromEntries(Object.entries(old).filter(([,s])=>typeof s==='string'||typeof s==='number'||typeof s==='boolean')) as Record<string,Setting>)};
    return made;
  });
  const ids=new Set(nodes.map(n=>n.id));if(ids.size!==nodes.length)throw new Error('중복된 노드 ID입니다.');
  const edges:ForgeEdge[]=raw.edges.map((e:unknown,i:number)=>{
    const v=e as Record<string,unknown>;
    if(!v||typeof v.source!=='string'||typeof v.target!=='string'||!ids.has(v.source)||!ids.has(v.target))throw new Error('연결된 노드가 존재하지 않습니다.');
    return makeEdge(v.source,v.target,i);
  });
  return{nodes,edges};
}
function fromStorage():Snapshot{try{const s=localStorage.getItem(KEY);return s?parseSnapshot(JSON.parse(s)):template('default')}catch{return template('default')}}
function topologicalOrder(nodes:ForgeNode[],edges:ForgeEdge[]):{order:string[];errors:string[]}{
  const ids=new Set(nodes.map(n=>n.id));const indegree=new Map(nodes.map(n=>[n.id,0])),links=new Map(nodes.map(n=>[n.id,[] as string[]]));const errors:string[]=[];const seen=new Set<string>();
  for(const e of edges){
    if(!ids.has(e.source)||!ids.has(e.target)){errors.push('존재하지 않는 노드 연결');continue}
    if(e.source===e.target){errors.push('자기 자신 연결');continue}
    const key=e.source+':'+e.target;if(seen.has(key)){errors.push('중복 연결 '+key);continue}seen.add(key);
    indegree.set(e.target,(indegree.get(e.target)??0)+1);
    links.get(e.source)?.push(e.target);
  }
  const queue=nodes.filter(n=>indegree.get(n.id)===0).map(n=>n.id),order:string[]=[];
  for(let i=0;i<queue.length;i++){const id=queue[i];order.push(id);for(const to of links.get(id)??[]){indegree.set(to,(indegree.get(to)??0)-1);if(indegree.get(to)===0)queue.push(to)}}
  if(order.length!==nodes.length)errors.push('노드 간 순환 연결');
  if(!nodes.length)errors.push('빈 그래프는 실행할 수 없습니다.');
  return{order,errors};
}
function ForgeCard({data,selected}:NodeProps<ForgeNode>){
  return <div className={'forge-node '+(selected?'chosen':'')} style={{borderLeftColor:accent[data.group]}}>
    <Handle type="target" position={Position.Left} className="forge-port"/>
    <div className="forge-card-title"><span style={{color:accent[data.group]}}>⬡</span><strong>{data.title}</strong></div>
    <div className="forge-card-sub">{data.subtitle}</div>
    <small className={'forge-card-state '+data.status}>{data.status==='demo'?'시연 실행 완료':data.status==='error'?'오류':data.status==='unavailable'?'서버 연결 전':'설정 대기'}</small>
    <Handle type="source" position={Position.Right} className="forge-port"/>
  </div>;
}
const NODE_TYPES={forge:ForgeCard};
function exampleData(group:'KR'|'US'){
  return group==='KR'?
    [{symbol:'DEMO:KR01',price:54000,volume:158000,market_cap:800000000000},{symbol:'DEMO:KR02',price:920,volume:127000,market_cap:42000000000},{symbol:'DEMO:KR03',price:33000,volume:87000,market_cap:560000000000},{symbol:'DEMO:KR04',price:7400,volume:20000,market_cap:90000000000}]:
    [{symbol:'DEMO:US01',price:180,volume:450000,market_cap:800000000000},{symbol:'DEMO:US02',price:17,volume:190000,market_cap:95000000000},{symbol:'DEMO:US03',price:12,volume:22000,market_cap:30000000000}];
}
function sampleRun(node:ForgeNode,inputs:StepResult[]):StepResult{
  const op=node.data.operation, settings=node.data.settings;
  const fromInputs=inputs.flatMap(x=>(Array.isArray(x.result.items)?x.result.items:[]) as Record<string,unknown>[]);
  let result:Record<string,unknown>={mode:'DEMO',message:'이 노드의 실제 백엔드는 아직 연결되지 않았습니다.',received:inputs.length};
  let state:NodeStatus='unavailable';
  if(op==='source.kr'||op==='source.us'){const items=exampleData(op.endsWith('kr')?'KR':'US');result={mode:'DEMO',items,count:items.length,note:'실제 시세가 아닌 합성 예시'};state='demo'}
  if(op==='screen.basic'){
    const rows=fromInputs.filter(x=>Number(x.price)>=Number(settings.min_price)&&Number(x.volume)>=Number(settings.min_volume)&&Number(x.market_cap)>=Number(settings.min_market_cap)).slice(0,Number(settings.top_n));
    result={mode:'DEMO',items:rows,count:rows.length,sourceCount:fromInputs.length,note:'합성 샘플에 대한 실제 필터 계산'};state='demo';
  }
  if(op==='research.consensus'){
    result={mode:'DEMO',chosenExperts:String(settings.gurus).split(',').filter(Boolean),threshold:settings.vote_threshold,candidates:fromInputs.length,warning:'AI 전문가 토론·투표를 수행하지 않았습니다.'};
  }
  if(op==='risk.allocate'){result={mode:'DEMO',constraints:settings,warning:'실제 계좌·포지션·주문에는 적용되지 않았습니다.'}}
  if(op==='output.table'){result={mode:'DEMO',items:fromInputs,count:fromInputs.length,note:'앞 단계 데이터 미리보기'};state='demo'}
  return{nodeId:node.id,label:node.data.title,state,result,startedAt:new Date().toISOString()};
}
function Editor({onExit}:{onExit?:()=>void}){
  const initial=useRef<Snapshot|null>(null);if(initial.current===null)initial.current=fromStorage();
  const [nodes,setNodes,onNodesChange]=useNodesState<ForgeNode>(initial.current.nodes);
  const [edges,setEdges,onEdgesChange]=useEdgesState<ForgeEdge>(initial.current.edges);
  const [selected,setSelected]=useState<string|null>('experts');
  const [panel,setPanel]=useState<'settings'|'results'|'connections'>('settings');
  const [query,setQuery]=useState('');
  const [closedGroups,setClosedGroups]=useState<Group[]>([]);
  const [message,setMessage]=useState('1단계: 화면·노드 편집기. 투자 실행은 연결하지 않았습니다.');
  const [run,setRun]=useState<RunRecord|null>(null);
  const [runBusy,setRunBusy]=useState(false);
  const [templateName,setTemplateName]=useState('default');
  const upload=useRef<HTMLInputElement>(null);
  const history=useRef<Snapshot[]>([]);
  const future=useRef<Snapshot[]>([]);
  const capture=useCallback(()=>{history.current.push({nodes:structuredClone(nodes),edges:structuredClone(edges)});if(history.current.length>30)history.current.shift();future.current=[]},[nodes,edges]);
  const active=nodes.find(n=>n.id===selected);
  const linksIn=edges.filter(e=>e.target===selected);const linksOut=edges.filter(e=>e.source===selected);
  const palette=useMemo(()=>LIBRARY.filter(d=>(d.title+' '+d.subtitle+' '+d.description).toLowerCase().includes(query.toLowerCase())),[query]);
  const addNode=useCallback((op:string)=>{capture();const id='node-'+Math.random().toString(36).slice(2,10);setNodes(prev=>[...prev,makeNode(op,id,350+Math.random()*200,230+Math.random()*130)]);setSelected(id);setPanel('settings')},[capture,setNodes]);
  const onConnect=useCallback((connection:Connection)=>{if(connection.source===connection.target)return;capture();setEdges(es=>addEdge({...connection,type:'smoothstep',markerEnd:arrow,style:{stroke:'#aababc',strokeWidth:1.8}},es))},[capture,setEdges]);
  const updateSetting=(key:string,value:Setting)=>setNodes(prev=>prev.map(n=>n.id===selected?{...n,data:{...n.data,settings:{...n.data.settings,[key]:value},status:'idle'}}:n));
  const clearSelected=()=>{if(!selected)return;capture();setNodes(ns=>ns.filter(n=>n.id!==selected));setEdges(es=>es.filter(e=>e.source!==selected&&e.target!==selected));setSelected(null)};
  const chooseTemplate=(which:string)=>{capture();const next=template(which);setNodes(next.nodes);setEdges(next.edges);setTemplateName(which);setSelected(next.nodes[0]?.id??null);setRun(null);setMessage('템플릿을 불러왔습니다. 설정을 확인하고 시연 실행을 선택하세요.')};
  const persist=()=>{localStorage.setItem(KEY,JSON.stringify({nodes,edges}));setMessage('이 브라우저에 저장했습니다. 서버/계정 동기화는 아직 없습니다.')};
  const download=()=>{const blob=new Blob([JSON.stringify({nodes,edges},null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='alphaforge-workflow.json';a.click();URL.revokeObjectURL(url)};
  const uploadFile=async(f:File)=>{try{if(f.size>2_000_000)throw new Error('2MB보다 큰 JSON은 지원하지 않습니다.');const parsed=parseSnapshot(JSON.parse(await f.text()));capture();setNodes(parsed.nodes);setEdges(parsed.edges);setRun(null);setMessage('JSON 그래프를 불러왔습니다.')}catch(err){setMessage('가져오기 실패: '+String(err))}};
  const undo=()=>{const last=history.current.pop();if(!last)return;future.current.push({nodes:structuredClone(nodes),edges:structuredClone(edges)});setNodes(last.nodes);setEdges(last.edges)};
  const redo=()=>{const last=future.current.pop();if(!last)return;history.current.push({nodes:structuredClone(nodes),edges:structuredClone(edges)});setNodes(last.nodes);setEdges(last.edges)};
  const execute=async()=>{if(runBusy)return;const {order,errors}=topologicalOrder(nodes,edges);setPanel('results');
    if(errors.length){setRun({runId:'invalid',startedAt:new Date().toISOString(),status:'invalid',steps:[],errors});setMessage(errors.join(', '));return}
    setRunBusy(true);
    const results=new Map<string,StepResult>(),steps:StepResult[]=[];
    for(const id of order){const node=nodes.find(n=>n.id===id)!;const inputs=edges.filter(e=>e.target===id).map(e=>results.get(e.source)).filter((x):x is StepResult=>Boolean(x));
      const result=sampleRun(node,inputs);steps.push(result);results.set(id,result);
    }
    setNodes(prev=>prev.map(n=>({...n,data:{...n.data,status:results.get(n.id)?.state??'idle'}})));
    const partial=steps.some(s=>s.state==='unavailable');
    setRun({runId:'demo-'+Date.now(),startedAt:new Date().toISOString(),status:partial?'partial':'demo_complete',steps,errors:[]});
    setMessage(partial?'시연 실행 완료: 외부 계산·AI·백테스트 노드는 미연결로 표시됩니다.':'합성 샘플을 사용한 시연 계산이 완료됐습니다.');
    setRunBusy(false);
  };
  const result=run?.steps.find(s=>s.nodeId===selected);
  return <div className="forge-shell">
    <header className="forge-top">
      <div className="forge-logo"><strong>AlphaForge</strong><span>워크플로 스튜디오</span></div>
      <div className="forge-breadcrumb">{onExit&&<button onClick={onExit}>← 주식 플랫폼</button>}<b>새 워크플로</b><span>● 노드 {nodes.length}개</span></div>
      <div className="forge-top-actions"><button onClick={()=>chooseTemplate('blank')}>＋ 새로</button><button onClick={persist}>▣ 저장</button><button onClick={download}>↓ 내보내기</button><button onClick={()=>upload.current?.click()}>↑ 가져오기</button><button className="forge-run" onClick={execute} disabled={runBusy}>{runBusy?'실행 중':'▶ 시연 실행'}</button></div>
      <input type="file" accept=".json,application/json" hidden ref={upload} onChange={e=>{const f=e.target.files?.[0];if(f)void uploadFile(f);e.target.value=''}}/>
    </header>
    <aside className="forge-palette">
      <div className="forge-aside-title"><b>＋ 노드 추가</b><span>{LIBRARY.length} 종류</span></div>
      <div className="forge-template"><b>워크플로 템플릿</b><select aria-label="워크플로 템플릿 선택" value={templateName} onChange={e=>chooseTemplate(e.target.value)}><option value="default">한국·미국 선별 → 전문가 합의</option><option value="simple">기본 스크리닝 3단계</option><option value="pine">Pine → 검증 → Nautilus (연결용)</option><option value="blank">빈 워크플로</option></select></div>
      <input className="forge-search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="노드 검색" aria-label="노드 검색"/>
      <div className="forge-library-list">
        {GROUPS.map(g=>{const entries=palette.filter(d=>d.group===g.key);if(!entries.length)return null;return <section key={g.key}>
          <button className="forge-group" onClick={()=>setClosedGroups(v=>v.includes(g.key)?v.filter(x=>x!==g.key):[...v,g.key])}><b style={{color:g.accent}}>{g.title}</b><span>{entries.length} {closedGroups.includes(g.key)?'+':'−'}</span></button>
          {!closedGroups.includes(g.key)&&entries.map(d=><button className="forge-library-item" key={d.operation} onClick={()=>addNode(d.operation)} title={d.description}><strong>{d.title}</strong><small>{d.subtitle}</small><span>＋</span></button>)}
        </section>})}
      </div>
      <p className="forge-library-hint">노드 버튼으로 추가하고, ● 포트를 드래그해 연결합니다.</p>
    </aside>
    <main className="forge-board">
      <div className="forge-boardbar"><div><strong>▣ 노드 캔버스</strong><span>● 노드 {nodes.length}개 · 연결 {edges.length}개</span></div><div><button onClick={undo}>↶</button><button onClick={redo}>↷</button><span>드래그 · 확대/축소 · 연결</span></div></div>
      <div className="forge-flow">
        <ReactFlow<ForgeNode,ForgeEdge> nodes={nodes} edges={edges} nodeTypes={NODE_TYPES} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect} onNodeClick={(_,node)=>{setSelected(node.id);setPanel('settings')}} onPaneClick={()=>setSelected(null)} onNodeDragStart={capture} fitView fitViewOptions={{padding:.16,minZoom:.35,maxZoom:1.1}} minZoom={.2} maxZoom={2} colorMode="light" proOptions={{hideAttribution:false}}>
          <Background color="#cdd2d4" gap={18} size={1}/><MiniMap pannable zoomable maskColor="rgba(245,245,241,.7)" nodeColor={n=>accent[(n.data as ForgeData).group]??'#aaa'}/><Controls showInteractive={false}/>
        </ReactFlow>
      </div>
    </main>
    <aside className="forge-inspector">
      {active?<><div className="forge-inspector-head"><small>설정 · 결과 · 환경 연결</small><h3>{active.data.title}</h3><p>{active.data.subtitle}</p></div>
        <nav className="forge-tabs"><button className={panel==='settings'?'active':''} onClick={()=>setPanel('settings')}>설정</button><button className={panel==='results'?'active':''} onClick={()=>setPanel('results')}>결과</button><button className={panel==='connections'?'active':''} onClick={()=>setPanel('connections')}>환경 연결</button></nav>
        <div className="forge-inspector-body">
          {panel==='settings'?<>
            <p className="forge-description">{DEF_MAP.get(active.data.operation)?.description}</p>
            {active.data.operation==='research.consensus'&&<div className="forge-experts"><strong>전문가 선택 (A~M)</strong><div>{EXPERTS.map((name,i)=>{const id=String.fromCharCode(65+i),selectedExperts=String(active.data.settings.gurus).split(',');return <button key={id} className={selectedExperts.includes(id)?'active':''} onClick={()=>{const next=new Set(selectedExperts.filter(Boolean));if(next.has(id))next.delete(id);else next.add(id);updateSetting('gurus',Array.from(next).sort().join(','))}}>{name}</button>})}</div></div>}
            {Object.entries(active.data.settings).filter(([k])=>k!=='gurus').map(([name,val])=><label className="forge-setting" key={name}><span>{name}</span>{typeof val==='boolean'?<input type="checkbox" checked={val} onChange={e=>updateSetting(name,e.target.checked)}/>:<input type={typeof val==='number'?'number':'text'} step="any" value={String(val)} onChange={e=>updateSetting(name,typeof val==='number'?Number(e.target.value):e.target.value)}/>}</label>)}
            <button className="forge-remove" onClick={clearSelected}>선택 노드 삭제</button>
          </>:panel==='results'?<>
            <div className="forge-demo-warning">실제 시장 데이터·AI 분석·실거래 결과가 아닙니다. 화면 재현용 실행입니다.</div>
            {result?<><div className="forge-result-meta"><strong>{result.label}</strong><span>{result.state==='demo'?'합성 데이터 시연 완료':'실제 엔진 미연결'}</span></div><pre>{JSON.stringify(result.result,null,2)}</pre></>:<p>상단의 「시연 실행」을 누르면 연결 순서와 단계별 입력·출력을 보여줍니다.</p>}
            {run&&<div className="forge-run-history"><strong>최근 실행 · {run.status}</strong>{run.errors.map((e,i)=><p key={i} className="forge-error">{e}</p>)}{run.steps.map(s=><button key={s.nodeId} onClick={()=>setSelected(s.nodeId)}>{s.state==='demo'?'✓':'○'} {s.label}</button>)}</div>}
          </>:<>
            <p>연결된 노드의 수신/전달 방향을 확인합니다. 아직 실제 서버 API 요청은 실행하지 않습니다.</p>
            <h4>입력 · {linksIn.length}</h4>{linksIn.map(e=><button className="forge-connected" key={e.id} onClick={()=>setSelected(e.source)}>{nodes.find(n=>n.id===e.source)?.data.title??e.source} →</button>)}
            <h4>출력 · {linksOut.length}</h4>{linksOut.map(e=><button className="forge-connected" key={e.id} onClick={()=>setSelected(e.target)}>→ {nodes.find(n=>n.id===e.target)?.data.title??e.target}</button>)}
          </>}
        </div>
      </>:<div className="forge-inspector-placeholder"><h3>노드를 선택하세요</h3><p>캔버스의 노드를 선택하면 설정, 실행 결과, 입출력 연결을 확인할 수 있습니다.</p>{run&&<button onClick={()=>{setSelected(run.steps[0]?.nodeId??null);setPanel('results')}}>최근 실행 결과</button>}</div>}
    </aside>
    <footer className="forge-footer"><span>● REA 참고 · React Flow</span><span>시연 전용 · 실제 거래 OFF</span><span className="forge-footer-message">{message}</span><span>노드 {nodes.length} / {LIBRARY.length}종</span></footer>
  </div>;
}
export default function AlphaForgeStudio({onExit}:{onExit?:()=>void}){return <ReactFlowProvider><Editor onExit={onExit}/></ReactFlowProvider>}
