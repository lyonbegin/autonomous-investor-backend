import {useEffect,useMemo,useState} from 'react';
import Header from './components/Header';
import IdeasPage from './pages/IdeasPage';
import StrategiesPage from './pages/StrategiesPage';
import StrategyDetailPage from './pages/StrategyDetailPage';
import AgentsPage from './pages/AgentsPage';
import AgentDetailPage from './pages/AgentDetailPage';
import MarketsPage from './pages/MarketsPage';
import PerformancePage from './pages/PerformancePage';

type Page='ideas'|'strategies'|'agents'|'markets'|'performance';

function readRoute(){
 const raw=(location.hash||'#/ideas').replace(/^#\/?/,'');
 const parts=raw.split('/');
 if(parts[0]==='strategy'&&parts[1]) return {page:'strategies' as Page,detail:'strategy',id:decodeURIComponent(parts.slice(1).join('/'))};
 if(parts[0]==='agent'&&parts[1]) return {page:'agents' as Page,detail:'agent',id:decodeURIComponent(parts.slice(1).join('/'))};
 const p=(['ideas','strategies','agents','markets','performance'].includes(parts[0])?parts[0]:'ideas') as Page;
 return {page:p,detail:null as string|null,id:''};
}

export default function App(){
 const [route,setRoute]=useState(readRoute());
 useEffect(()=>{const fn=()=>setRoute(readRoute());addEventListener('hashchange',fn);return()=>removeEventListener('hashchange',fn)},[]);
 const go=(p:Page)=>{location.hash='#/'+p};
 const openStrategy=(id:string)=>{location.hash='#/strategy/'+encodeURIComponent(id)};
 const openAgent=(id:string)=>{location.hash='#/agent/'+encodeURIComponent(id)};
 const body=useMemo(()=>{
  if(route.detail==='strategy')return <StrategyDetailPage id={route.id} onBack={()=>go('strategies')} onAgent={openAgent}/>;
  if(route.detail==='agent')return <AgentDetailPage id={route.id} onBack={()=>go('agents')} onStrategy={openStrategy}/>;
  if(route.page==='strategies')return <StrategiesPage onOpen={openStrategy} onAgent={openAgent}/>;
  if(route.page==='agents')return <AgentsPage onOpen={openAgent}/>;
  if(route.page==='markets')return <MarketsPage/>;
  if(route.page==='performance')return <PerformancePage onAgent={openAgent}/>;
  return <IdeasPage onStrategies={()=>go('strategies')}/>;
 },[route]);
 return <div className="app"><Header page={route.page} onGo={go}/>{body}<footer className="site-footer"><b>AUTONOMOUS INVESTOR</b><span>공개 데이터는 실제 연구·검증 상태를 그대로 반영합니다. 검증되지 않은 성과는 표시하지 않습니다.</span></footer></div>
}