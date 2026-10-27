type Props={path:string;go:(p:string)=>void};
const items=[['/strategies','전략'],['/ideas','TradingView 아이디어'],['/scripts','TradingView 스크립트'],['/agents','에이전트'],['/markets','마켓'],['/performance','성과']];
export function Header({path,go}:Props){
  return <>
    <header className="topbar">
      <div className="brand" onClick={()=>go('/strategies')}>AUTONOMOUS <b>INVESTOR</b></div>
      <nav>{items.map(([p,l])=><button key={p} className={path.startsWith(p)?'active':''} onClick={()=>go(p)}>{l}</button>)}</nav>
      <a href="https://investment-n8n-operations-ui-production.up.railway.app/" target="_blank" rel="noopener noreferrer">운영 화면</a>
      <a href="https://investment-n8n-native-editor-production.up.railway.app/" target="_blank" rel="noopener noreferrer">n8n 원본 편집기 (인증 필요)</a>
      <div className="top-actions"><span className="live-dot"/>LIVE DATA</div>
    </header>
    <div className="subbar">
      <span>TradingView Pine Source</span><span>전략 후보</span><span>고정 시간축 Agent</span><span>Walk-forward · Holdout</span><span>Paper · Live</span>
    </div>
  </>
}
