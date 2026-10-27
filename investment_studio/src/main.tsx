import React, {useState} from 'react';
import {createRoot} from 'react-dom/client';
import InvestmentStudio from './InvestmentStudio';
const publicDemo = import.meta.env.VITE_PUBLIC_DEMO === 'true';
import ScenarioConsole from './ScenarioConsole';
import OperationsConsole from './OperationsConsole';
import '@xyflow/react/dist/style.css';
import './style.css';
function Workspace(){
 const [page,setPage]=useState<'studio'|'scenarios'|'operations'>(publicDemo?'scenarios':'operations');
 return <div style={{height:'100%',display:'flex',flexDirection:'column'}}>
   <nav style={{display:'flex',gap:8,padding:'7px 12px',background:'#193b49',zIndex:20}}>
     <button onClick={()=>setPage('scenarios')} style={{padding:'6px 14px',border:0,borderRadius:5,background:page==='scenarios'?'#d3f5df':'#45616e',color:page==='scenarios'?'#14573d':'white',fontWeight:750,cursor:'pointer'}}>n8n 워크플로 실행 테스트</button>
     <button onClick={()=>setPage('operations')} style={{padding:'6px 14px',border:0,borderRadius:5,background:page==='operations'?'#effcff':'#45616e',color:page==='operations'?'#1e5867':'white',cursor:'pointer'}}>전략 풀 · 에이전트 · 독립 감사</button>
     <button onClick={()=>setPage('scenarios')} style={{padding:'6px 14px',border:0,borderRadius:5,background:page==='scenarios'?'#effcff':'#45616e',color:page==='scenarios'?'#1e5867':'white',cursor:'pointer'}}>10개 운영 시나리오 실행</button>
     {!publicDemo&&<button onClick={()=>setPage('studio')} style={{padding:'6px 14px',border:0,borderRadius:5,background:page==='studio'?'#effcff':'#45616e',color:page==='studio'?'#1e5867':'white',cursor:'pointer'}}>12개 엔진 노드 편집</button>}
   </nav>
   {publicDemo&&<div style={{padding:'6px 14px',background:'#fff4db',color:'#704900',fontSize:12}}>로그인 없는 테스트 · n8n 실제 Webhook/Worker 경유 실행 또는 Python 직접 실행 선택 · 결과는 합성 데이터이며 실제 매매는 하지 않습니다</div>}
   <div style={{minHeight:0,flex:1}}>{page==='scenarios'?<ScenarioConsole/>:page==='operations'?<OperationsConsole/>:<InvestmentStudio/>}</div>
 </div>
}
const root=document.getElementById('root');
if(!root)throw new Error('Root missing');
createRoot(root).render(<React.StrictMode><Workspace/></React.StrictMode>);
