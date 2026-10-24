type Props={path:string;go:(p:string)=>void};
const items=[['/strategies','전략'],['/scripts','TradingView 스크립트'],['/agents','에이전트'],['/markets','마켓'],['/performance','성과'],['/workflow','AlphaForge 노드 스튜디오']];
export function Header({path,go}:Props){
  return <>
    <header className="topbar">
      <div className="brand" onClick={()=>go('/strategies')}>AUTONOMOUS <b>INVESTOR</b></div>
      <nav>{items.map(([p,l])=><button key={p} className={path.startsWith(p)?'active':''} onClick={()=>go(p)}>{l}</button>)}</nav>
      <div className="top-actions"><span className="live-dot"/>LIVE DATA</div>
    </header>
    <div className="subbar">
      <span>TradingView Pine Source</span><span>전략 후보</span><span>고정 시간축 Agent</span><span>Walk-forward · Holdout</span><span>Paper · Live</span>
    </div>
  </>
}
