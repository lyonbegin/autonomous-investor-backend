import {useState} from 'react';
import InvestmentStudio from './InvestmentStudio';
import ScenarioConsole from './ScenarioConsole';

/** Internal admin tooling. n8n drives scenario callbacks; Nautilus live orders
 * are never available through the scenario tab.
 */
export default function Workbench(){
  const[screen,setScreen]=useState<'scenarios'|'nodes'>('scenarios');
  return <div className="invest-workbench">
    <header className="invest-workbench-nav">
      <div className="invest-workbench-brand"><b>Autonomous Investor</b><small>n8n · 12-Engine Control Plane</small></div>
      <nav aria-label="화면 선택">
        <button className={screen==='scenarios'?'active':''} onClick={()=>setScreen('scenarios')}>10개 운영 시나리오 검사</button>
        <button className={screen==='nodes'?'active':''} onClick={()=>setScreen('nodes')}>140개 투자 함수 노드</button>
      </nav>
      <span>합성 검사 · 실거래 OFF</span>
    </header>
    <main className="invest-workbench-content">
      {screen==='scenarios'?<ScenarioConsole/>:<InvestmentStudio/>}
    </main>
  </div>;
}
