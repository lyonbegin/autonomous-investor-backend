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
     <a href="https://investment-n8n-native-editor-production.up.railway.app/" target="_blank" rel="noopener noreferrer" style={{padding:'6px 14px',borderRadius:5,background:'#d3f5df',color:'#14573d',fontWeight:750,textDecoration:'none'}}>n8n 원본 노드 플로우 ↗</a>
     <button onClick={()=>setPage('operations')} style={{padding:'6px 14px',border:0,borderRadius:5,background:page==='operations'?'#effcff':'#45616e',color:page==='operations'?'#1e5867':'white',cursor:'pointer'}}>전략 풀 · 에이전트 · 독립 감사</button>
     <button onClick={()=>setPage('scenarios')} style={{padding:'6px 14px',border:0,borderRadius:5,background:page==='scenarios'?'#effcff':'#45616e',color:page==='scenarios'?'#1e5867':'white',cursor:'pointer'}}>10개 운영 시나리오 실행</button>
     {!publicDemo&&<button onClick={()=>setPage('studio')} style={{padding:'6px 14px',border:0,borderRadius:5,background:page==='studio'?'#effcff':'#45616e',color:page==='studio'?'#1e5867':'white',cursor:'pointer'}}>12개 엔진 노드 편집</button>}
   </nav>
   {publicDemo&&<div style={{padding:'6px 14px',background:'#fff4db',color:'#704900',fontSize:12}}>공개 상태 조회 및 합성 테스트 · 실제 노드 그래프·실행 이력은 상단 n8n 원본 편집기에서 확인 (인증 필요) · 실거래/관리자 변경 금지</div>}
   <div style={{minHeight:0,flex:1}}>{page==='scenarios'?<ScenarioConsole/>:page==='operations'?<OperationsConsole/>:<InvestmentStudio/>}</div>
 </div>
}
const root=document.getElementById('root');
if(!root)throw new Error('Root missing');
createRoot(root).render(<React.StrictMode><Workspace/></React.StrictMode>);
