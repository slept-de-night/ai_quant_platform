import React, { useEffect, useState } from 'react';
import { BookOpen, Search, X, HelpCircle, AlertTriangle, ShieldCheck, Cpu, ArrowRight } from 'lucide-react';
import { FinancialMetricExplanation } from '../../types';
import { api } from '../../services/api';

interface KnowledgeBaseModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialMetricId?: string | null;
}

export const KnowledgeBaseModal: React.FC<KnowledgeBaseModalProps> = ({
  isOpen,
  onClose,
  initialMetricId,
}) => {
  const [metrics, setMetrics] = useState<FinancialMetricExplanation[]>([]);
  const [selectedMetric, setSelectedMetric] = useState<FinancialMetricExplanation | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);

  useEffect(() => {
    if (isOpen) {
      loadMetrics();
    }
  }, [isOpen, categoryFilter]);

  useEffect(() => {
    if (initialMetricId && metrics.length > 0) {
      const match = metrics.find((m) => m.id.toLowerCase() === initialMetricId.toLowerCase());
      if (match) setSelectedMetric(match);
    }
  }, [initialMetricId, metrics]);

  const loadMetrics = async () => {
    setIsLoading(true);
    try {
      const cat = categoryFilter === 'all' ? undefined : categoryFilter;
      const res = await api.getKnowledgeMetrics(cat, searchQuery || undefined);
      if (res?.metrics) {
        setMetrics(res.metrics);
        if (!selectedMetric && res.metrics.length > 0) {
          setSelectedMetric(res.metrics[0]);
        }
      }
    } catch (err) {
      console.error('Failed to load knowledge metrics:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    loadMetrics();
  };

  if (!isOpen) return null;

  const categories = [
    { id: 'all', label: 'All Domains' },
    { id: 'valuation', label: 'Valuation' },
    { id: 'forensic', label: 'Forensic Quality' },
    { id: 'risk', label: 'Risk & Validation' },
    { id: 'portfolio', label: 'Portfolio Sizing' },
    { id: 'execution', label: 'Execution & OMS' },
    { id: 'macro', label: 'Macro Matrix' },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="relative w-full max-w-5xl h-[85vh] bg-slate-900 border border-slate-700 rounded-xl shadow-2xl flex flex-col overflow-hidden text-slate-100">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/90">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-emerald-400">
              <BookOpen className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                Quantitative & Financial Knowledge Registry
              </h2>
              <p className="text-xs text-slate-400">
                Institutional metric definitions, LaTeX formulas, quant usage gates, and interpretation guides.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Filter and Search Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-3 border-b border-slate-800 bg-slate-950/60">
          {/* Category Tabs */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
            {categories.map((c) => (
              <button
                key={c.id}
                onClick={() => {
                  setCategoryFilter(c.id);
                  setSelectedMetric(null);
                }}
                className={`px-3 py-1.5 text-xs font-medium rounded-md whitespace-nowrap transition-colors ${
                  categoryFilter === c.id
                    ? 'bg-emerald-600 text-white shadow-sm'
                    : 'bg-slate-800/80 text-slate-300 hover:bg-slate-800 hover:text-white'
                }`}
              >
                {c.label}
              </button>
            ))}
          </div>

          {/* Search Input */}
          <form onSubmit={handleSearch} className="relative w-full sm:w-64">
            <Search className="absolute left-2.5 top-2.5 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search formula, metric, rule..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
            />
          </form>
        </div>

        {/* Modal Body: Left Sidebar list + Right Details Pane */}
        <div className="flex-1 flex overflow-hidden">
          {/* List Sidebar */}
          <div className="w-1/3 border-r border-slate-800 bg-slate-950/40 overflow-y-auto p-3 space-y-1.5">
            {isLoading ? (
              <div className="p-4 text-center text-xs text-slate-400 animate-pulse">Loading registry catalog...</div>
            ) : metrics.length === 0 ? (
              <div className="p-4 text-center text-xs text-slate-500">No matching metrics found.</div>
            ) : (
              metrics.map((m) => (
                <button
                  key={m.id}
                  onClick={() => setSelectedMetric(m)}
                  className={`w-full text-left p-2.5 rounded-lg text-xs transition-all border ${
                    selectedMetric?.id === m.id
                      ? 'bg-emerald-950/40 border-emerald-500/50 text-emerald-300'
                      : 'bg-slate-900/60 border-slate-800/80 text-slate-300 hover:bg-slate-800/60 hover:text-white'
                  }`}
                >
                  <div className="font-semibold text-slate-200">{m.name}</div>
                  <div className="text-[11px] text-slate-400 line-clamp-1 mt-0.5">{m.summary}</div>
                  <span className="inline-block mt-1.5 px-2 py-0.5 rounded text-[10px] uppercase font-mono bg-slate-800 text-slate-300">
                    {m.category}
                  </span>
                </button>
              ))
            )}
          </div>

          {/* Details Pane */}
          <div className="w-2/3 p-6 overflow-y-auto bg-slate-900 space-y-6">
            {selectedMetric ? (
              <div className="space-y-6">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="px-2.5 py-0.5 rounded text-xs uppercase font-mono bg-emerald-950 border border-emerald-700/50 text-emerald-400 font-semibold">
                      {selectedMetric.category}
                    </span>
                    <span className="text-xs font-mono text-slate-500">ID: {selectedMetric.id}</span>
                  </div>
                  <h3 className="text-2xl font-bold text-white tracking-tight">{selectedMetric.name}</h3>
                  <p className="text-sm text-slate-300 mt-2 leading-relaxed">{selectedMetric.summary}</p>
                </div>

                {/* Mathematical Formula */}
                {selectedMetric.formula && (
                  <div className="p-4 rounded-lg bg-slate-950 border border-slate-800 space-y-1.5">
                    <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Formula / Specification</div>
                    <div className="font-mono text-sm text-emerald-400 bg-slate-900/90 p-2.5 rounded border border-slate-800/80 overflow-x-auto">
                      {selectedMetric.formula}
                    </div>
                  </div>
                )}

                {/* Interpretation & Benchmark Ranges */}
                <div className="space-y-3">
                  <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Interpretation & Guidance</div>
                  <p className="text-xs text-slate-200 leading-relaxed bg-slate-800/40 p-3 rounded-lg border border-slate-700/50">
                    {selectedMetric.interpretation}
                  </p>

                  {selectedMetric.ranges && Object.keys(selectedMetric.ranges).length > 0 && (
                    <div className="grid grid-cols-3 gap-2 mt-2">
                      {Object.entries(selectedMetric.ranges).map(([zone, range]) => (
                        <div key={zone} className="p-2.5 rounded bg-slate-950 border border-slate-800 text-center">
                          <div className="text-[11px] font-medium text-slate-400">{zone}</div>
                          <div className="text-xs font-mono font-bold text-emerald-400 mt-0.5">{range}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Quant Engine Usage */}
                <div className="p-4 rounded-lg bg-emerald-950/20 border border-emerald-800/40 space-y-1.5">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-400 uppercase tracking-wider">
                    <Cpu className="w-4 h-4" /> Platform Quant Usage
                  </div>
                  <p className="text-xs text-slate-200 leading-relaxed">{selectedMetric.quant_usage}</p>
                </div>

                {/* Common Pitfalls & Traps */}
                <div className="p-4 rounded-lg bg-amber-950/20 border border-amber-800/40 space-y-1.5">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-amber-400 uppercase tracking-wider">
                    <AlertTriangle className="w-4 h-4" /> Common Pitfalls & Blind Spots
                  </div>
                  <p className="text-xs text-slate-200 leading-relaxed">{selectedMetric.pitfalls}</p>
                </div>

                {/* Related Metrics */}
                {selectedMetric.related_metrics && selectedMetric.related_metrics.length > 0 && (
                  <div className="pt-2 border-t border-slate-800 flex items-center gap-2">
                    <span className="text-xs text-slate-400">Related Metrics:</span>
                    <div className="flex flex-wrap gap-1.5">
                      {selectedMetric.related_metrics.map((relId) => (
                        <button
                          key={relId}
                          onClick={() => {
                            const match = metrics.find((m) => m.id === relId);
                            if (match) setSelectedMetric(match);
                          }}
                          className="px-2 py-0.5 rounded text-xs font-mono bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white transition-colors"
                        >
                          {relId}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-slate-500 text-sm">
                Select a metric from the catalog to view detailed pedagogical documentation.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
