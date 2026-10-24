type Page='ideas'|'strategies'|'agents'|'markets'|'performance';
export default function Header({page,onGo}:{page:Page;onGo:(p:Page)=>void}){
  const items:[Page,string][]=[['ideas','아이디어'],['strategies','전략'],['agents','에이전트'],['markets','마켓'],['performance','성과']];
  return <>
    <header className="topbar">
      <div className="brand" onClick={()=>onGo('ideas')}>AUTONOMOUS <b>INVESTOR</b></div>
      <div className="search">⌕ 전략·에이전트·종목 검색</div>
      <nav>{items.map(([k,l])=><button key={k} className={page===k?'active':''} onClick={()=>onGo(k)}>{l}</button>)}</nav>
      <div className="live">● LIVE</div>
    </header>
    <div className="subbar"><span>전략 원본 × 고정 기간 × 시장 = 독립 Agent</span><span>TradingView 원천 · Quant Lab 검증 · Nautilus 실행</span></div>
  </>
}