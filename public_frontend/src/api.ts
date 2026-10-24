import type {Agent,Idea,IdeaDetail,Strategy} from './types';
export const API='https://autonomous-investor-tradingview-production.up.railway.app';
async function j<T>(url:string):Promise<T>{const r=await fetch(url);if(!r.ok)throw new Error(await r.text());return r.json()}
export const api={
 ideas:(page=1)=>j<{items:Idea[];total_count:number;page_count:number}>(`${API}/api/v1/tradingview/ideas/live?sort=recent&page=${page}&lang=ko`),
 ideaDetail:(id:string)=>j<IdeaDetail>(`${API}/api/v1/tradingview/ideas/${encodeURIComponent(id)}/full`),
 strategies:()=>j<{count:number;items:Strategy[]}>(`${API}/api/v1/public/strategies?limit=300`),
 strategy:(id:string)=>j<Strategy>(`${API}/api/v1/public/strategies/${encodeURIComponent(id)}`),
 agents:()=>j<{count:number;items:Agent[]}>(`${API}/api/v1/public/agents?limit=1000`),
 agent:(id:string)=>j<{agent:Agent;strategy:Strategy|null}>(`${API}/api/v1/public/agents/${encodeURIComponent(id)}`),
};
