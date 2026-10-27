import type {Agent,Idea,MarketItem,Strategy} from '../types';
export const API=import.meta.env.VITE_PUBLIC_API||'https://autonomous-investor-public-api-production.up.railway.app';
async function get<T>(path:string):Promise<T>{const r=await fetch(API+path); if(!r.ok) throw new Error(await r.text()); return r.json() as Promise<T>;}
export const api={
  ideas:(page=1)=>get<{count:number;total_count:number;items:Idea[]}>(`/api/public/ideas?page=${page}&sort=recent`),
  strategies:(limit=100)=>get<{count:number;items:Strategy[]}>(`/api/public/strategies?limit=${limit}`),
  strategy:(id:string)=>get<Strategy>(`/api/public/strategies/${encodeURIComponent(id)}`),
  agents:(limit=200)=>get<{count:number;items:Agent[]}>(`/api/public/agents?limit=${limit}`),
  agent:(id:string)=>get<Agent>(`/api/public/agents/${encodeURIComponent(id)}`),
  market:(m:string,sort='volume')=>get<{total_count:number;items:MarketItem[]}>(`/api/public/markets/${m}?limit=50&offset=0&sort_by=${sort}&sort_order=desc`),
  summary:()=>get<any>('/api/public/summary')
};