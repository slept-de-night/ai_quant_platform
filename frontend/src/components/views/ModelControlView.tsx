import React, { useEffect, useState } from 'react';
import { ModelDeployment, RouteRecommendation } from '../../types';
import { api } from '../../services/api';
import {
  Cpu,
  Activity,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Zap,
  DollarSign,
  Layers,
  ArrowRight,
  Key,
  ShieldCheck,
  Globe,
  Sliders
} from 'lucide-react';

export const ModelControlView: React.FC = () => {
  const [deployments, setDeployments] = useState<ModelDeployment[]>([]);
  const [recommendations, setRecommendations] = useState<RouteRecommendation[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [probeStatus, setProbeStatus] = useState<Record<number, any>>({});
  const [probingId, setProbingId] = useState<number | null>(null);

  // LLM Provider State
  const [provider, setProvider] = useState<string>('gemini');
  const [apiKey, setApiKey] = useState<string>('');
  const [baseUrl, setBaseUrl] = useState<string>('');
  const [modelFast, setModelFast] = useState<string>('gemini-2.0-flash');
  const [modelBalanced, setModelBalanced] = useState<string>('gemini-2.0-flash');
  const [modelFrontier, setModelFrontier] = useState<string>('gemini-2.5-pro');
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const [deps, recs] = await Promise.all([
        api.listDeployments(),
        api.listRecommendations(),
      ]);
      setDeployments(deps);
      setRecommendations(recs);
    } catch (err) {
      console.error('Failed to load model control data:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleProviderChange = (newProvider: string) => {
    setProvider(newProvider);
    if (newProvider === 'gemini') {
      setBaseUrl('https://generativelanguage.googleapis.com/v1beta/openai/');
      setModelFast('gemini-2.0-flash');
      setModelBalanced('gemini-2.0-flash');
      setModelFrontier('gemini-2.5-pro');
    } else if (newProvider === 'openai') {
      setBaseUrl('');
      setModelFast('gpt-4o-mini');
      setModelBalanced('gpt-4o');
      setModelFrontier('gpt-4o');
    } else if (newProvider === 'deepseek') {
      setBaseUrl('https://api.deepseek.com/v1');
      setModelFast('deepseek-chat');
      setModelBalanced('deepseek-chat');
      setModelFrontier('deepseek-reasoner');
    }
  };

  const handleSaveLLMSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setSaveStatus(null);
    try {
      await api.updateLLMSettings({
        provider,
        api_key: apiKey.trim() || undefined,
        base_url: baseUrl.trim() || undefined,
        model_fast: modelFast.trim() || undefined,
        model_balanced: modelBalanced.trim() || undefined,
        model_frontier: modelFrontier.trim() || undefined,
      });
      setSaveStatus('success');
      await fetchData();
    } catch (err: any) {
      setSaveStatus(err?.message || 'Failed to save configuration');
    } finally {
      setIsSaving(false);
    }
  };

  const handleProbe = async (id: number) => {
    setProbingId(id);
    try {
      const res = await api.probeDeployment(id, true);
      setProbeStatus((prev) => ({ ...prev, [id]: res }));
      await fetchData();
    } catch (err) {
      console.error('Probe failed:', err);
    } finally {
      setProbingId(null);
    }
  };

  const handleApproveRec = async (id: number) => {
    try {
      await api.approveRecommendation(id, false);
      await fetchData();
    } catch (err) {
      console.error('Approve failed:', err);
    }
  };

  const handleRejectRec = async (id: number) => {
    try {
      await api.rejectRecommendation(id);
      await fetchData();
    } catch (err) {
      console.error('Reject failed:', err);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-background">
      {/* Control Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between p-5 rounded-xl bg-card border border-card-border shadow-md gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 text-xs font-mono font-bold bg-accent-amber/20 text-accent-amber border border-accent-amber/40 rounded">
              CONTROL PLANE
            </span>
            <span className="text-xs text-slate-400 font-mono">Multi-Tier LLM Router & Provider Gateway</span>
          </div>
          <h1 className="text-lg font-bold text-slate-100 mt-1">
            Model Deployment Registry & Provider Settings
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Configure Google Gemini, OpenAI, or DeepSeek API keys and monitor empirical routing telemetry.
          </p>
        </div>

        <button
          onClick={fetchData}
          disabled={isLoading}
          className="flex items-center gap-1.5 px-3.5 py-2 bg-background hover:bg-card-border border border-card-border text-slate-200 rounded text-xs font-semibold transition cursor-pointer"
        >
          <RotateCcw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Refresh Telemetry</span>
        </button>
      </div>

      {/* Active LLM Provider & Key Configuration Card */}
      <div className="p-5 rounded-xl bg-card border border-card-border shadow-md">
        <div className="flex items-center justify-between pb-3 border-b border-card-border mb-4">
          <div className="flex items-center gap-2">
            <Key className="w-4 h-4 text-accent-cyan" />
            <h2 className="text-xs font-bold text-slate-100 uppercase tracking-wide">
              LLM Provider & API Key Setup
            </h2>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-accent-cyan/15 text-accent-cyan border border-accent-cyan/30">
              Active Provider: {provider.toUpperCase()}
            </span>
          </div>
        </div>

        <form onSubmit={handleSaveLLMSettings} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Provider Selection */}
            <div>
              <label className="block text-[11px] font-mono text-slate-300 mb-1.5">
                AI Provider
              </label>
              <select
                value={provider}
                onChange={(e) => handleProviderChange(e.target.value)}
                className="w-full bg-background border border-card-border rounded-lg px-3 py-2 text-xs font-mono text-slate-100 focus:outline-none focus:border-accent-cyan"
              >
                <option value="gemini">Google Gemini (Gemini 2.0 Flash / Pro)</option>
                <option value="openai">OpenAI ChatGPT (GPT-4o / GPT-5)</option>
                <option value="deepseek">DeepSeek (V3 / R1 Reasoner)</option>
                <option value="anthropic">Anthropic Claude (3.5 Sonnet)</option>
                <option value="custom">Custom / Ollama Local</option>
              </select>
            </div>

            {/* API Key */}
            <div className="md:col-span-2">
              <label className="block text-[11px] font-mono text-slate-300 mb-1.5">
                {provider === 'gemini' ? 'GEMINI_API_KEY / Google API Key' : 'API Key'}
              </label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={
                  provider === 'gemini'
                    ? 'AIzaSy...'
                    : 'sk-...'
                }
                className="w-full bg-background border border-card-border rounded-lg px-3 py-2 text-xs font-mono text-slate-100 placeholder-slate-600 focus:outline-none focus:border-accent-cyan"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 pt-2">
            <div>
              <label className="block text-[10px] font-mono text-slate-400 mb-1">Fast Tier Model</label>
              <input
                type="text"
                value={modelFast}
                onChange={(e) => setModelFast(e.target.value)}
                className="w-full bg-background border border-card-border rounded px-2.5 py-1.5 text-xs font-mono text-slate-200"
              />
            </div>
            <div>
              <label className="block text-[10px] font-mono text-slate-400 mb-1">Balanced Tier Model</label>
              <input
                type="text"
                value={modelBalanced}
                onChange={(e) => setModelBalanced(e.target.value)}
                className="w-full bg-background border border-card-border rounded px-2.5 py-1.5 text-xs font-mono text-slate-200"
              />
            </div>
            <div>
              <label className="block text-[10px] font-mono text-slate-400 mb-1">Frontier Tier Model</label>
              <input
                type="text"
                value={modelFrontier}
                onChange={(e) => setModelFrontier(e.target.value)}
                className="w-full bg-background border border-card-border rounded px-2.5 py-1.5 text-xs font-mono text-slate-200"
              />
            </div>
            <div className="flex items-end">
              <button
                type="submit"
                disabled={isSaving}
                className="w-full py-2 bg-accent-cyan hover:bg-cyan-400 text-slate-950 font-bold rounded-lg text-xs font-mono transition cursor-pointer shadow flex items-center justify-center gap-1.5"
              >
                <ShieldCheck className="w-4 h-4" />
                <span>{isSaving ? 'Connecting...' : 'Save & Activate'}</span>
              </button>
            </div>
          </div>

          {saveStatus === 'success' && (
            <div className="p-3 rounded bg-accent-emerald/15 border border-accent-emerald/30 text-accent-emerald text-xs font-mono flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4" />
              <span>Configuration activated! Multi-agent DAG is now connected to {provider.toUpperCase()}.</span>
            </div>
          )}

          {saveStatus && saveStatus !== 'success' && (
            <div className="p-3 rounded bg-accent-rose/15 border border-accent-rose/30 text-accent-rose text-xs font-mono flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" />
              <span>{saveStatus}</span>
            </div>
          )}
        </form>
      </div>

      {/* Model Deployments Tier Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {['fast', 'balanced', 'frontier'].map((tier) => {
          const tierDeps = deployments.filter((d) => d.tier === tier);
          const activeDep = tierDeps.find((d) => d.status === 'active') || tierDeps[0];

          return (
            <div key={tier} className="p-5 rounded-xl bg-card border border-card-border flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between pb-3 border-b border-card-border mb-3">
                  <div className="flex items-center gap-2">
                    <Cpu className="w-4 h-4 text-accent-cyan" />
                    <span className="text-xs font-bold uppercase text-slate-100">{tier} Tier</span>
                  </div>
                  <span className={`px-2 py-0.5 text-[10px] font-mono font-bold rounded ${
                    activeDep?.status === 'active'
                      ? 'bg-accent-emerald/20 text-accent-emerald border border-accent-emerald/40'
                      : 'bg-slate-800 text-slate-400'
                  }`}>
                    {activeDep?.status?.toUpperCase() || 'STANDBY'}
                  </span>
                </div>

                <div className="space-y-2 text-xs font-mono">
                  <div className="p-2.5 rounded bg-background border border-card-border">
                    <div className="text-[10px] text-slate-400">Deployed Model Alias</div>
                    <div className="font-bold text-slate-100 mt-0.5">{activeDep?.model || (tier === 'frontier' ? modelFrontier : modelFast)}</div>
                  </div>

                  <div className="p-2.5 rounded bg-background border border-card-border">
                    <div className="text-[10px] text-slate-400">Target Role</div>
                    <div className="text-slate-300 text-[11px] mt-0.5">
                      {tier === 'fast' && 'High-throughput extraction & classification'}
                      {tier === 'balanced' && 'Technical & fundamental structured synthesis'}
                      {tier === 'frontier' && 'Deep qualitative research & adversarial falsification'}
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-card-border/60 flex items-center justify-between">
                <span className="text-[10px] font-mono text-slate-400">
                  Latency: ~{tier === 'fast' ? '280ms' : tier === 'balanced' ? '650ms' : '1800ms'}
                </span>
                {activeDep && (
                  <button
                    onClick={() => handleProbe(activeDep.id)}
                    disabled={probingId === activeDep.id}
                    className="px-2.5 py-1 bg-accent-blue/20 hover:bg-accent-blue/30 text-accent-cyan border border-accent-blue/40 rounded text-[11px] font-mono transition cursor-pointer"
                  >
                    {probingId === activeDep.id ? 'Probing...' : 'Live Probe'}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Learned Routing Recommendations */}
      <div className="p-5 rounded-xl bg-card border border-card-border">
        <div className="flex items-center justify-between pb-3 border-b border-card-border mb-3">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-accent-cyan" />
            <h2 className="text-xs font-bold text-slate-100 uppercase tracking-wide">
              Empirical Routing Recommendations (Governance Gate)
            </h2>
          </div>
          <span className="text-[10px] font-mono text-slate-400">Human-In-The-Loop Approval</span>
        </div>

        <div className="divide-y divide-card-border/40 text-xs">
          {recommendations.length === 0 ? (
            <div className="py-6 text-center text-slate-500 font-mono">
              No pending routing recommendations. Model tiers are operating at optimal empirical thresholds.
            </div>
          ) : (
            recommendations.map((rec) => (
              <div key={rec.id} className="py-3 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 font-mono">
                    <span className="font-bold text-slate-200">{rec.task_type}</span>
                    <span className="text-slate-400">({rec.current_tier})</span>
                    <ArrowRight className="w-3.5 h-3.5 text-accent-cyan" />
                    <span className="text-accent-cyan font-bold">({rec.recommended_tier})</span>
                    <span className={`px-1.5 py-0.2 text-[9px] font-bold rounded ${
                      rec.status === 'APPROVED' ? 'bg-accent-emerald/20 text-accent-emerald' : 'bg-accent-amber/20 text-accent-amber'
                    }`}>
                      {rec.status}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400 mt-1">
                    {rec.reason}
                  </div>
                </div>

                {rec.status === 'PENDING_REVIEW' && (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleApproveRec(rec.id)}
                      className="px-3 py-1 bg-accent-emerald hover:bg-emerald-600 text-slate-950 font-bold rounded text-xs transition cursor-pointer"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => handleRejectRec(rec.id)}
                      className="px-3 py-1 bg-accent-rose/20 hover:bg-accent-rose/30 text-accent-rose rounded text-xs transition cursor-pointer"
                    >
                      Reject
                    </button>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
