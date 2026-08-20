import {
  PlatformStatus,
  WatchlistAsset,
  StrategyItem,
  BacktestResponse,
  ValidationReport,
  AlphaSearchCandidate,
  RuntimeStatus,
  ModelDeployment,
  RouteRecommendation,
  ResearchDossier,
  MemoryNote,
  InstitutionalRiskMetrics
} from '../types';

const API_BASE = '/api';

export const api = {
  // Platform Status
  getStatus: async (): Promise<PlatformStatus> => {
    const res = await fetch(`${API_BASE}/status`);
    if (!res.ok) throw new Error(`Status API error: ${res.statusText}`);
    return res.json();
  },

  // Market & Watchlist
  getWatchlist: async (): Promise<{ items: WatchlistAsset[]; updated_at: string }> => {
    const res = await fetch(`${API_BASE}/market/watchlist`);
    if (!res.ok) throw new Error(`Watchlist API error: ${res.statusText}`);
    return res.json();
  },

  searchAssets: async (query: string, limit: number = 8) => {
    if (!query.trim()) return [];
    try {
      const res = await fetch(`${API_BASE}/market/search?q=${encodeURIComponent(query)}&limit=${limit}`);
      if (!res.ok) return [];
      return res.json();
    } catch {
      return [];
    }
  },

  getQuote: async (symbol: string) => {
    const res = await fetch(`${API_BASE}/market/quote/${symbol}`);
    if (!res.ok) throw new Error(`Quote error: ${res.statusText}`);
    return res.json();
  },

  getChartData: async (symbol: string, timeframe: string = '1Y') => {
    const res = await fetch(`${API_BASE}/market/chart/${symbol}?timeframe=${timeframe}`);
    if (!res.ok) throw new Error(`Chart API error: ${res.statusText}`);
    return res.json();
  },

  getFundamentals: async (symbol: string) => {
    const res = await fetch(`${API_BASE}/market/fundamentals/${symbol}`);
    if (!res.ok) throw new Error(`Fundamentals error: ${res.statusText}`);
    return res.json();
  },

  // Risk & Architecture
  getRiskMetrics: async (symbol: string = 'SPY', days: number = 252): Promise<InstitutionalRiskMetrics> => {
    const res = await fetch(`${API_BASE}/risk/metrics?symbol=${symbol}&days=${days}`);
    if (!res.ok) throw new Error(`Risk metrics error: ${res.statusText}`);
    return res.json();
  },

  getArchitecture: async () => {
    const res = await fetch(`${API_BASE}/architecture`);
    if (!res.ok) throw new Error(`Architecture error: ${res.statusText}`);
    return res.json();
  },

  // Interactive ChatGPT Quant Co-Pilot
  chatWithCopilot: async (messages: { role: string; content: string }[], symbol?: string, strategy?: string) => {
    const res = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages, symbol, strategy }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Chat API error: ${res.statusText}`);
    }
    return res.json();
  },

  // Strategies & Quant Studio
  listStrategies: async (): Promise<StrategyItem[]> => {
    const res = await fetch(`${API_BASE}/strategies`);
    if (!res.ok) throw new Error(`Strategies API error: ${res.statusText}`);
    return res.json();
  },

  approveStrategy: async (name: string) => {
    const res = await fetch(`${API_BASE}/strategies/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to approve strategy');
    }
    return res.json();
  },

  runBacktest: async (symbol: string, strategy: string, days: number = 1600): Promise<BacktestResponse> => {
    const res = await fetch(`${API_BASE}/quant/backtest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol, strategy, days }),
    });
    if (!res.ok) throw new Error(`Backtest error: ${res.statusText}`);
    return res.json();
  },

  runValidation: async (symbol: string, strategy: string, days: number = 1800): Promise<ValidationReport> => {
    const res = await fetch(`${API_BASE}/quant/validate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol, strategy, days }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Validation failed');
    }
    return res.json();
  },

  runAlphaSearch: async (symbol: string, count: number = 4, days: number = 1800): Promise<AlphaSearchCandidate[]> => {
    const res = await fetch(`${API_BASE}/quant/alpha-search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol, count, days }),
    });
    if (!res.ok) throw new Error(`Alpha search error: ${res.statusText}`);
    return res.json();
  },

  // Research & Intelligence
  getDossier: async (symbol: string): Promise<ResearchDossier> => {
    const res = await fetch(`${API_BASE}/research/dossier/${symbol}`);
    if (!res.ok) throw new Error(`Dossier error: ${res.statusText}`);
    return res.json();
  },

  runResearch: async (symbol: string, market: string = 'SPY', sector?: string): Promise<ResearchDossier> => {
    const res = await fetch(`${API_BASE}/research/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol, market, sector, days: 1000 }),
    });
    if (!res.ok) throw new Error(`Research error: ${res.statusText}`);
    return res.json();
  },

  // Runtime DAG
  getRuntimeStatus: async (rootId?: string): Promise<RuntimeStatus> => {
    const url = rootId ? `${API_BASE}/runtime/status?root_id=${rootId}` : `${API_BASE}/runtime/status`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Runtime status error: ${res.statusText}`);
    return res.json();
  },

  planRuntimeDAG: async (symbol: string) => {
    const res = await fetch(`${API_BASE}/runtime/plan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol }),
    });
    if (!res.ok) throw new Error(`Plan error: ${res.statusText}`);
    return res.json();
  },

  runRuntimeDAG: async (symbol: string, executeAi: boolean = false, concurrency?: number) => {
    const res = await fetch(`${API_BASE}/runtime/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol, execute_ai: executeAi, concurrency }),
    });
    if (!res.ok) throw new Error(`Runtime execution error: ${res.statusText}`);
    return res.json();
  },

  requeueTask: async (taskId: string, resetAttempts: boolean = false) => {
    const res = await fetch(`${API_BASE}/runtime/requeue`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task_id: taskId, reset_attempts: resetAttempts }),
    });
    if (!res.ok) throw new Error(`Requeue error: ${res.statusText}`);
    return res.json();
  },

  // Models & Empirical Routing
  listDeployments: async (): Promise<ModelDeployment[]> => {
    const res = await fetch(`${API_BASE}/models/deployments`);
    if (!res.ok) throw new Error(`Deployments error: ${res.statusText}`);
    return res.json();
  },

  probeDeployment: async (deploymentId: number, applyHealth: boolean = false) => {
    const res = await fetch(`${API_BASE}/models/probe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ deployment_id: deploymentId, apply_health: applyHealth }),
    });
    if (!res.ok) throw new Error(`Probe error: ${res.statusText}`);
    return res.json();
  },

  listRecommendations: async (): Promise<RouteRecommendation[]> => {
    const res = await fetch(`${API_BASE}/evaluations/recommendations`);
    if (!res.ok) throw new Error(`Recommendations error: ${res.statusText}`);
    return res.json();
  },

  approveRecommendation: async (recommendationId: number, capitalApproved: boolean = false) => {
    const res = await fetch(`${API_BASE}/evaluations/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ recommendation_id: recommendationId, capital_approved: capitalApproved }),
    });
    if (!res.ok) throw new Error(`Approve error: ${res.statusText}`);
    return res.json();
  },

  rejectRecommendation: async (recommendationId: number) => {
    const res = await fetch(`${API_BASE}/evaluations/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ recommendation_id: recommendationId }),
    });
    if (!res.ok) throw new Error(`Reject error: ${res.statusText}`);
    return res.json();
  },

  updateLLMSettings: async (payload: {
    provider: string;
    api_key?: string;
    base_url?: string;
    model_fast?: string;
    model_balanced?: string;
    model_frontier?: string;
  }) => {
    const res = await fetch(`${API_BASE}/models/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`Settings update error: ${res.statusText}`);
    return res.json();
  },


  // Paper Trading & Risk
  getPaperCycle: async (symbol: string, strategy: string) => {
    const res = await fetch(`${API_BASE}/paper/cycle?symbol=${symbol}&strategy=${strategy}`);
    if (!res.ok) throw new Error(`Paper cycle error: ${res.statusText}`);
    return res.json();
  },

  executePaperOrder: async (symbol: string, strategy: string) => {
    const res = await fetch(`${API_BASE}/paper/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol, strategy }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Paper execution failed');
    }
    return res.json();
  },

  // Memory & Journals
  getMemoryNotes: async (agent?: string, symbol?: string): Promise<MemoryNote[]> => {
    let url = `${API_BASE}/memory/notes?limit=100`;
    if (agent) url += `&agent=${agent}`;
    if (symbol) url += `&symbol=${symbol}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Memory notes error: ${res.statusText}`);
    return res.json();
  },

  addMemoryNote: async (note: { agent: string; kind: string; content: string; symbol?: string; confidence: number; importance: number }) => {
    const res = await fetch(`${API_BASE}/memory/note`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(note),
    });
    if (!res.ok) throw new Error(`Add note error: ${res.statusText}`);
    return res.json();
  },

  getJournals: async () => {
    const res = await fetch(`${API_BASE}/memory/journals`);
    if (!res.ok) throw new Error(`Journals error: ${res.statusText}`);
    return res.json();
  },

  // Firm-Wide Emergency Kill Switch & Order History
  engageKillSwitch: async () => {
    const res = await fetch(`${API_BASE}/risk/kill`, { method: 'POST' });
    if (!res.ok) throw new Error(`Kill switch error: ${res.statusText}`);
    return res.json();
  },

  disengageKillSwitch: async () => {
    const res = await fetch(`${API_BASE}/risk/unfreeze`, { method: 'POST' });
    if (!res.ok) throw new Error(`Unfreeze error: ${res.statusText}`);
    return res.json();
  },

  getOrderHistory: async () => {
    const res = await fetch(`${API_BASE}/orders/history`);
    if (!res.ok) throw new Error(`Order history error: ${res.statusText}`);
    return res.json();
  },

  runReconciliation: async () => {
    const res = await fetch(`${API_BASE}/reconciliation/run`, { method: 'POST' });
    if (!res.ok) throw new Error(`Reconciliation error: ${res.statusText}`);
    return res.json();
  },

  listBrokers: async () => {
    const res = await fetch(`${API_BASE}/brokers`);
    if (!res.ok) throw new Error(`List brokers error: ${res.statusText}`);
    return res.json();
  },

  selectBroker: async (name: string) => {
    const res = await fetch(`${API_BASE}/brokers/select`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    if (!res.ok) throw new Error(`Select broker error: ${res.statusText}`);
    return res.json();
  },
};



