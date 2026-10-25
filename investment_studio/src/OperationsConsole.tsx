import {useCallback,useEffect,useState} from 'react';
import './operations.css';

type RegistryItem={strategy_id:string;title:string;author:string;script_type:string;script_access:string;latest_version_id:string;eligibility:string;source_available:number;source_sha256:string|null;source_version:string};
type Assignment={assignment_id:string;agent_id:string;strategy_id:string;version_id:string;epoch:number;slot_key:string;state:string;lease_expires_at:string};
type Agent={agent_id:string;status:string;execution_mode:string;market_scope:string};
type AuditFinding={finding_id:string;event_id:string;assignment_id:string|null;severity:string;code:string;details:string;created_at:string};
type BusinessEvent={seq:number;flow:string;type:string;created_at:string;payload:Record<string,unknown>};
type Overview={counts:Record<string,number>;approved_versions:number;active_assignments:number;broker_connected:boolean;n8n_workflows:string[]};
type Registry={count:number;items:RegistryItem[]};
type Assignments={agents:Agent[];active_assignments:Assignment[]};
type Findings={count:number;items:AuditFinding[]};
type Timeline={events:BusinessEvent[];last_seq:number};
const api='/studio-api/api/v1/ops';
async function request<T>(url:string,method='GET',body?:unknown):Promise<T>{
  const response=await fetch(api+url,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
  let data:unknown;
  try{data=await response.json()}catch{throw new Error('서버가 JSON을 반환하지 않았습니다')}
  if(!response.ok){const message=data&&typeof data==='object'&&'detail' in data?String((data as {detail:unknown}).detail):JSON.stringify(data);throw new Error(response.status+': '+message)}
  return data as T;
}
const format=(s:string)=>s.length>30?s.slice(0,24)+'…':s;
export default function OperationsConsole(){
  const[overview,setOverview]=useState<Overview|null>(null);
  const[registry,setRegistry]=useState<Registry>({count:0,items:[]});
  const[agents,setAgents]=useState<Assignments>({agents:[],active_assignments:[]});
  const[findings,setFindings]=useState<Findings>({count:0,items:[]});
  const[events,setEvents]=useState<Timeline>({events:[],last_seq:0});
  const[error,setError]=useState('');
  const[notice,setNotice]=useState('');
  const[busy,setBusy]=useState('');
  const[agentId,setAgentId]=useState('');
  const[versionToApprove,setVersionToApprove]=useState('');
  const[reviewer,setReviewer]=useState('');
  const[evidenceRef,setEvidenceRef]=useState('');
  const[license,setLicense]=useState(false);
  const[pine,setPine]=useState(false);
  const[backtest,setBacktest]=useState(false);
  const[autoRefresh,setAutoRefresh]=useState(true);

  const refresh=useCallback(async()=>{
    const [o,r,a,f,e]=await Promise.all([
      request<Overview>('/overview'),request<Registry>('/strategies?limit=100'),
      request<Assignments>('/agents'),request<Findings>('/audit/findings?limit=70'),
      request<Timeline>('/events?limit=150')]);
    setOverview(o);setRegistry(r);setAgents(a);setFindings(f);setEvents(e);
  },[]);
  useEffect(()=>{void refresh().catch(e=>setError(String(e)))},[refresh]);
  useEffect(()=>{
    if(!autoRefresh)return;
    const interval=setInterval(()=>void refresh().catch(e=>setError(String(e))),3000);
    return()=>clearInterval(interval);
  },[refresh,autoRefresh]);
  const action=async(title:string,fn:()=>Promise<unknown>)=>{
    setBusy(title);setError('');setNotice('');
    try{const result=await fn();setNotice(title+' 완료: '+JSON.stringify(result).slice(0,260));await refresh()}catch(e){setError(String(e))}
    finally{setBusy('')}
  };
  const sync=()=>void action('F01 TradingView 카탈로그 실제 조회',()=>request('/strategies/sync?limit=30&max_sources=5&refresh_live=true','POST'));
  const allocate=()=>void action('F03 PAPER 할당',()=>request('/assignments/allocate-one','POST'));
  const audit=()=>void action('F05 감사 재대조',()=>request('/audit/reconcile','POST'));
  const addAgent=()=>void action('PAPER 에이전트 등록',()=>request('/agents','POST',{agent_id:agentId,execution_mode:'paper',market_scope:'US'}));
  const review=()=>void action('증거 확인 전략 승인',async()=>{
    if(!license||!pine||!backtest||!evidenceRef.trim()||!reviewer.trim())throw new Error('라이선스, Pine 변환, 독립 백테스트 근거를 모두 확인해야 합니다.');
    return request('/strategies/'+versionToApprove+'/approve','POST',{
      reviewer,
      evidence:{license_reviewed:license,pine_compiler_passed:pine,
        independent_backtest_passed:backtest,evidence_refs:[evidenceRef.trim()]},
    });
  });
  const statuses=[
    {id:'F01',label:'전략 풀 최신화',description:'TradingView 서비스 실데이터 증분 수집',act:sync},
    {id:'F03',label:'원자적 에이전트 할당',description:'승인된 전략 + 유휴 PAPER 에이전트',act:allocate},
    {id:'F05',label:'독립 감사',description:'진행 중인 Lease 만료 검사 / 주문 감사 결과',act:audit},
  ];
  return <div className="ops-root">
    <header className="ops-header">
      <div><h1>실제 운영 상태 · F01 / F03 / F05</h1><p>n8n 운영 플로우가 사용하는 영속 데이터베이스 · 3초 갱신 · 모의주문도 제출하지 않습니다</p></div>
      <label><input type="checkbox" checked={autoRefresh} onChange={e=>setAutoRefresh(e.target.checked)}/> 자동 새로고침</label>
      <button disabled={!!busy} onClick={()=>void refresh().catch(e=>setError(String(e)))}>지금 새로고침</button>
    </header>
    <section className="ops-stats">
      <div><small>수집된 전략</small><strong>{overview?.counts.strategy_registry??'—'}</strong></div>
      <div><small>불변 전략 버전</small><strong>{overview?.counts.strategy_versions??'—'}</strong></div>
      <div><small>사람이 승인한 버전</small><strong>{overview?.approved_versions??'—'}</strong></div>
      <div><small>활성 PAPER 할당</small><strong>{overview?.active_assignments??'—'}</strong></div>
      <div><small>독립 감사 발견</small><strong>{overview?.counts.audit_findings??'—'}</strong></div>
    </section>
    <section className="ops-controls">
      {statuses.map(s=><div key={s.id} className="ops-task">
        <span>{s.id}</span><h3>{s.label}</h3><p>{s.description}</p>
        <button disabled={!!busy} onClick={s.act}>{busy===s.id?'실행 중…':s.id+' 실행'}</button>
      </div>)}
    </section>
    {notice&&<p className="ops-notice" role="status">{notice}</p>}
    {error&&<p className="ops-error" role="alert">{error}</p>}
    <div className="ops-grid">
      <section className="ops-panel">
        <h2>전략 마스터 풀 <span>{registry.count}개</span></h2>
        <p>TradingView 원본에서 읽어 온 실제 카탈로그 결과만 등록합니다. 새 버전은 항상 적격성 검토 대기 상태입니다.</p>
        <div className="ops-table-wrap"><table><thead><tr><th>전략·작성자</th><th>원본</th><th>버전</th><th>적격성</th></tr></thead><tbody>
          {registry.items.map(s=><tr key={s.strategy_id}><td><b>{s.title}</b><small>{s.author} · {s.strategy_id}</small></td><td>{s.source_available?'Pine 있음':'원본 없음'}</td><td>{s.source_version}</td><td><span className={'ops-status '+s.eligibility}>{s.eligibility}</span></td></tr>)}
          {registry.count===0&&<tr><td colSpan={4}>전략 없음 — F01을 실행하거나 수집 서비스 연결을 확인하세요.</td></tr>}
        </tbody></table></div>
        <div className="ops-form">
          <h3>전략 버전 수동 승인 (기본 자동 승인 금지)</h3>
          <select aria-label="승인할 전략 버전" value={versionToApprove} onChange={e=>setVersionToApprove(e.target.value)}>
            <option value="">전략 버전 선택</option>
            {registry.items.filter(s=>s.source_available&&s.eligibility==='PENDING_REVIEW').map(s=><option key={s.latest_version_id} value={s.latest_version_id}>{s.title} · {format(s.latest_version_id)}</option>)}
          </select>
          <input aria-label="검토자" placeholder="검토자 식별자" value={reviewer} onChange={e=>setReviewer(e.target.value)}/>
          <input aria-label="검증 증거 참조" placeholder="검증 보고서/백테스트 증거 ID" value={evidenceRef} onChange={e=>setEvidenceRef(e.target.value)}/>
          <label><input type="checkbox" checked={license} onChange={e=>setLicense(e.target.checked)}/> 사용 라이선스 검토 완료</label>
          <label><input type="checkbox" checked={pine} onChange={e=>setPine(e.target.checked)}/> Pine 변환·동등성 검증 완료</label>
          <label><input type="checkbox" checked={backtest} onChange={e=>setBacktest(e.target.checked)}/> 독립 백테스트 검증 완료</label>
          <button disabled={!!busy||!versionToApprove||!license||!pine||!backtest} onClick={review}>증거와 함께 승인 기록</button>
          <p>승인은 검토자의 확인 기록이며 시스템이 백테스트 통과 사실을 독립 검증한 것으로 표시하지 않습니다.</p>
        </div>
      </section>
      <section className="ops-panel">
        <h2>에이전트 할당 <span>{agents.active_assignments.length}개 활성/차단</span></h2>
        <div className="ops-inline"><input aria-label="신규 PAPER 에이전트 ID" placeholder="PAPER 에이전트 ID (예: agent-A)" value={agentId} onChange={e=>setAgentId(e.target.value)}/><button disabled={!!busy||!agentId} onClick={addAgent}>유휴 에이전트 등록</button></div>
        <div className="ops-table-wrap"><table><thead><tr><th>에이전트</th><th>상태</th><th>전략 버전·Fencing</th></tr></thead><tbody>
          {agents.agents.map(a=>{const assigned=agents.active_assignments.find(x=>x.agent_id===a.agent_id);return <tr key={a.agent_id}><td><b>{a.agent_id}</b><small>{a.execution_mode} / {a.market_scope}</small></td><td>{assigned?.state||a.status}</td><td>{assigned?<><small>{format(assigned.version_id)}</small><small>epoch {assigned.epoch}</small></>:'미할당'}</td></tr>})}
          {!agents.agents.length&&<tr><td colSpan={3}>등록된 PAPER 에이전트가 없습니다.</td></tr>}
        </tbody></table></div>
        <h2>독립 감사 결과 <span>{findings.count}건</span></h2>
        <div className="ops-table-wrap"><table><thead><tr><th>심각도</th><th>유형</th><th>할당/시각</th></tr></thead><tbody>
          {findings.items.map(f=><tr key={f.finding_id}><td><span className={'ops-status '+f.severity}>{f.severity}</span></td><td><b>{f.code}</b><small>{f.details}</small></td><td><small>{format(f.assignment_id||'미할당')}</small><small>{f.created_at}</small></td></tr>)}
          {!findings.items.length&&<tr><td colSpan={3}>현재 기록된 감사 이상이 없습니다.</td></tr>}
        </tbody></table></div>
      </section>
    </div>
    <section className="ops-events"><h2>F01/F03/F05 운영 이벤트 원장 <span>총 {overview?.counts.ops_events??0}건</span></h2>
      <div className="ops-event-list">{events.events.slice().reverse().map(e=><div key={e.seq}><time>#{e.seq} · {e.created_at}</time><b>{e.flow}</b><strong>{e.type}</strong><code>{JSON.stringify(e.payload)}</code></div>)}{!events.events.length&&<p>아직 기록된 이벤트가 없습니다.</p>}</div>
    </section>
    <footer>운영 F01/F03/F05는 실제 영속 DB를 사용합니다. 브로커 연결 없음 · 실거래 주문 없음 · 전략 승인 및 성과를 임의로 생성하지 않습니다.</footer>
  </div>;
}
