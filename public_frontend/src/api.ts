import type {Agent,AgentPerformance,Idea,IdeaDetail,Strategy,Summary} from './types';

export const API='https://autonomous-investor-public-api-production.up.railway.app';

async function j<T>(url:string):Promise<T>{
  const r=await fetch(url,{headers:{Accept:'application/json'}});
  if(!r.ok) throw new Error(await r.text());
  return r.json();
}

export const api={
  ideas:(page=1,sort='recent')=>j<{items:Idea[];total_count:number;page_count:number}>(`${API}/api/public/ideas?page=${page}&sort=${sort}`),
  ideaDetail:(id:string)=>j<IdeaDetail>(`${API}/api/public/ideas/${encodeURIComponent(id)}`),
  strategies:(params='')=>j<{count:number;total_count:number;items:Strategy[]}>(`${API}/api/public/strategies?limit=300${params}`),
  strategy:(id:string)=>j<Strategy>(`${API}/api/public/strategies/${encodeURIComponent(id)}`),
  strategyAgents:(id:string)=>j<{strategy_id:string;count:number;items:Agent[]}>(`${API}/api/public/strategies/${encodeURIComponent(id)}/agents`),
  agents:()=>j<{count:number;items:Agent[]}>(`${API}/api/public/agents?limit=500`),
  agent:(id:string)=>j<Agent>(`${API}/api/public/agents/${encodeURIComponent(id)}`),
  performance:(id:string)=>j<AgentPerformance>(`${API}/api/public/agents/${encodeURIComponent(id)}/performance`),
  positions:(id:string)=>j<{agent_id:string;available:boolean;items:unknown[];reason?:string}>(`${API}/api/public/agents/${encodeURIComponent(id)}/positions`),
  decisions:(id:string)=>j<{agent_id:string;available:boolean;items:unknown[]}>(`${API}/api/public/agents/${encodeURIComponent(id)}/decisions`),
  trades:(id:string)=>j<{agent_id:string;available:boolean;items:unknown[];reason?:string}>(`${API}/api/public/agents/${encodeURIComponent(id)}/trades`),
  market:(market:string,sortBy='volume')=>j<{items:any[];total_count:number}>(`${API}/api/public/markets/${market}?limit=50&offset=0&sort_by=${sortBy}&sort_order=desc`),
  summary:()=>j<Summary>(`${API}/api/public/summary`)
};
