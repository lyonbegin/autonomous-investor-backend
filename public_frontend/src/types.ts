export type Performance={
  experiment_status?:string;
  strategy_engine?:string;
  blocked_reason?:string|null;
  promotion?:unknown;
  holdout_return_pct?:number;
  max_drawdown_pct?:number;
  trade_sharpe?:number;
  win_rate_pct?:number;
  trade_count?:number;
  pass_ratio?:number;
};

export type Agent={
  agent_id:string;
  candidate_id:string;
  strategy_name?:string;
  fixed_horizon:string;
  country:string;
  market:string;
  universe:string;
  status:string;
  fit_score?:number;
  market_score?:number;
  horizon_score?:number;
  source_score?:number;
  target_score?:number;
  rationale?:string;
  experiment_id?:string;
  experiment_status?:string;
  strategy_engine?:string;
  blocked_reason?:string|null;
  performance?:Performance|null;
};

export type Strategy={
  candidate_id:string;
  name:string;
  category:string;
  domain:string;
  logic:string;
  candidate_horizons:string[];
  status:string;
  created_at:string;
  source_kind:string;
  source_id:string;
  source_name?:string;
  source_url?:string;
  author?:string;
  source_symbol?:string;
  source_interval?:string;
  pine_version?:string;
  source_version?:string;
  agent_count:number;
  agents:Agent[];
  best_performance?:Performance|null;
  research_state?:{ready:number;blocked:number;completed:number;research:number};
};

export type Idea={
  idea_id:string;
  title:string;
  description:string;
  author:string;
  symbol:string;
  exchange:string;
  asset_type:string;
  direction:string;
  interval:string;
  created_at:string;
  comments_count:number;
  likes_count:number;
  views_count:number;
  chart_url?:string;
  image_url?:string;
};

export type IdeaDetail={
  source_kind:string;
  source_id:string;
  source_url:string;
  title:string;
  full_text:string;
  hero_images:string[];
  content_images:string[];
  collector?:string;
};

export type AgentPerformance={
  agent_id:string;
  available:boolean;
  experiment_id?:string|null;
  experiment_status?:string;
  performance?:Performance|null;
  stages?:Array<Record<string,unknown>>;
};

export type Summary={
  strategy_count:number;
  agent_count:number;
  ready_experiments:number;
  blocked_experiments:number;
  completed_performance:number;
  markets:string[];
  invariant:string;
};

export type CommunityScript={
  script_id_part:string;
  script_id?:string;
  name:string;
  author?:string;
  script_type?:string;
  script_access?:number;
  version?:string;
  likes_count?:number;
  comments_count?:number;
  views_count?:number;
  created_at?:string;
  updated_at?:string;
  chart_url?:string;
  image_url?:string;
  symbol?:string;
  interval?:string;
  is_picked?:number|boolean;
  is_hot?:number|boolean;
  description?:string;
  collected_at?:string;
};

export type ScriptDetail={
  source_kind:string;
  source_id:string;
  source_url:string;
  title:string;
  full_text:string;
  page_hash?:string;
  fetched_at?:string;
  hero_images?:string[];
  content_images?:string[];
  from_cache?:boolean;
};

export type PineSource={
  ok?:boolean;
  protected?:boolean;
  reason?:string;
  script_id_part:string;
  version?:string;
  script_name?:string;
  kind?:string;
  pine_version?:number;
  source_hash?:string;
  source?:string;
  fetched_at?:string;
  from_cache?:boolean;
};
