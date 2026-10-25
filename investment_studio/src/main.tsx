import React, {useState} from 'react';
import {createRoot} from 'react-dom/client';
import InvestmentStudio from './InvestmentStudio';
import ScenarioConsole from './ScenarioConsole';
import '@xyflow/react/dist/style.css';
import './style.css';
function Workspace(){
 const [page,setPage]=useState<'studio'|'scenarios'>('scenarios');
 return <div style={{height:'100%',display:'flex',flexDirection:'column'}}>
   <nav style={{display:'flex',gap:8,padding:'7px 12px',background:'#193b49',zIndex:20}}>
     <button onClick={()=>setPage('scenarios')} style={{padding:'6px 14px',border:0,borderRadius:5,background:page==='scenarios'?'#effcff':'#45616e',color:page==='scenarios'?'#1e5867':'white',cursor:'pointer'}}>10개 운영 시나리오 실행</button>
     <button onClick={()=>setPage('studio')} style={{padding:'6px 14px',border:0,borderRadius:5,background:page==='studio'?'#effcff':'#45616e',color:page==='studio'?'#1e5867':'white',cursor:'pointer'}}>12개 엔진 노드 편집</button>
   </nav>
   <div style={{minHeight:0,flex:1}}>{page==='scenarios'?<ScenarioConsole/>:<InvestmentStudio/>}</div>
 </div>
}
const root=document.getElementById('root');
if(!root)throw new Error('Root missing');
createRoot(root).render(<React.StrictMode><Workspace/></React.StrictMode>);
