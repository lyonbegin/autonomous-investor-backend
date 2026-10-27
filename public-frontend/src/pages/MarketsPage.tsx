import {useEffect,useState} from 'react';
import {api} from '../lib/api';
import type {MarketItem} from '../types';

const TABS=[['korea','한국 주식','volume'],['america','미국 주식','volume'],['crypto-coins','크립토','market_cap_calc'],['futures','선물','volume'],['forex','외환','volume'],['etf','ETF','volume'],['indices','지수','volume']] as const;

export default function MarketsPage(){
 const [tab,setTab]=useState(0),[items,setItems]=useState<MarketItem[]>([]),[total,setTotal]=useState(0),[loading,setLoading]=useState(true);
 useEffect(()=>{const [m,,sort]=TABS[tab];setLoading(true);api.market(m,sort).then(x=>{setItems(x.items||[]);setTotal(x.total_count||0)}).finally(()=>setLoading(false));},[tab]);
 return <main className="page"><section className="hero slim"><div><small>MARKETS</small><h1>시장</h1><p>TradingView 원본 시장 Universe를 우리 전략·Agent 탐색과 같은 기준으로 표시합니다.</p></div><div className="hero-stat"><b>{total.toLocaleString()}</b><span>현재 Universe</span></div></section>
 <div className="market-tabs">{TABS.map((x,i)=><button className={i===tab?'active':''} key={x[0]} onClick={()=>setTab(i)}>{x[1]}</button>)}</div>
 <div className="market-panel">{loading?<div className="loading">시장 데이터 수집 중…</div>:<table><thead><tr><th>#</th><th>종목</th><th>이름</th><th>현재가</th><th>변동</th><th>거래량</th><th>시가총액</th><th>거래소</th></tr></thead><tbody>{items.map((x,i)=><tr key={x.ticker}><td>{x.rank||i+1}</td><td><b>{x.ticker}</b></td><td>{x.description||x.name||''}</td><td>{x.close==null?'—':x.close.toLocaleString()}</td><td className={(x.change||0)>=0?'good':'bad'}>{x.change==null?'—':(x.change>0?'+':'')+x.change.toFixed(2)+'%'}</td><td>{x.volume==null?'—':Math.round(x.volume).toLocaleString()}</td><td>{x.market_cap_calc==null?'—':Math.round(x.market_cap_calc).toLocaleString()}</td><td>{x.exchange||''}</td></tr>)}</tbody></table>}</div>
 </main>
}