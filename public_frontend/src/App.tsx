import {useEffect,useState} from 'react';
import {Header} from './components/Header';
import {IdeasPage} from './pages/ideas/IdeasPage';
import {IdeaDetailPage} from './pages/ideas/IdeaDetailPage';
import {StrategiesPage} from './pages/strategies/StrategiesPage';
import {MarketsPage} from './pages/markets/MarketsPage';
import {StrategyDetailPage} from './pages/strategies/StrategyDetailPage';
import {AgentsPage} from './pages/agents/AgentsPage';
import {AgentDetailPage} from './pages/agents/AgentDetailPage';
import {PerformancePage} from './pages/performance/PerformancePage';

export default function App(){
  const [path,setPath]=useState(location.pathname==='/'?'/strategies':location.pathname);
  useEffect(()=>{
    if(location.pathname==='/') history.replaceState({},'','/strategies');
    const f=()=>setPath(location.pathname);
    addEventListener('popstate',f);
    return()=>removeEventListener('popstate',f);
  },[]);
  const go=(p:string)=>{history.pushState({},'',p);setPath(new URL(p,location.origin).pathname);scrollTo(0,0)};
  let page=<StrategiesPage go={go}/>;
  if(path==='/ideas') page=<IdeasPage go={go}/>;
  else if(path.startsWith('/ideas/')) page=<IdeaDetailPage id={decodeURIComponent(path.split('/')[2]||'')} go={go}/>;
  else if(path==='/markets') page=<MarketsPage/>;
  else if(path==='/strategies') page=<StrategiesPage go={go}/>;
  else if(path.startsWith('/strategies/')) page=<StrategyDetailPage id={decodeURIComponent(path.split('/')[2]||'')} go={go}/>;
  else if(path==='/agents') page=<AgentsPage go={go}/>;
  else if(path.startsWith('/agents/')) page=<AgentDetailPage id={decodeURIComponent(path.split('/')[2]||'')} go={go}/>;
  else if(path==='/performance') page=<PerformancePage/>;
  return <div className="app"><Header path={path} go={go}/>{page}<footer>Autonomous Investor · Strategy Source × Fixed Horizon × Market Universe</footer></div>
}
