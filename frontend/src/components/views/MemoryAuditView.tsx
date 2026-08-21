import React, { useEffect, useState } from 'react';
import { MemoryNote } from '../../types';
import { api } from '../../services/api';
import {
  BookOpen,
  Plus,
  RotateCcw,
  FileText,
  Clock,
  ShieldCheck,
  Tag,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Layers,
  Database,
  Search
} from 'lucide-react';

export const MemoryAuditView: React.FC = () => {
  const [notes, setNotes] = useState<MemoryNote[]>([]);
  const [journals, setJournals] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [newNoteContent, setNewNoteContent] = useState('');
  const [newNoteAgent, setNewNoteAgent] = useState('research_manager');
  const [newNoteSymbol, setNewNoteSymbol] = useState('');
  const [isAdding, setIsAdding] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedAgentFilter, setSelectedAgentFilter] = useState('ALL');

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const [n, j] = await Promise.all([
        api.getMemoryNotes(),
        api.getJournals(),
      ]);
      setNotes(n);
      setJournals(j);
    } catch (err) {
      console.error('Failed to load memory data:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleAddNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNoteContent.trim()) return;
    setIsAdding(true);
    try {
      await api.addMemoryNote({
        agent: newNoteAgent,
        kind: 'observation',
        content: newNoteContent.trim(),
        symbol: newNoteSymbol.trim() ? newNoteSymbol.trim().toUpperCase() : undefined,
        confidence: 0.85,
        importance: 0.75,
      });
      setNewNoteContent('');
      setNewNoteSymbol('');
      await fetchData();
    } catch (err) {
      console.error('Failed to add note:', err);
    } finally {
      setIsAdding(false);
    }
  };

  const filteredNotes = notes.filter((n) => {
    if (selectedAgentFilter !== 'ALL' && n.agent !== selectedAgentFilter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchContent = n.content.toLowerCase().includes(q);
      const matchSymbol = n.symbol?.toLowerCase().includes(q);
      const matchAgent = n.agent.toLowerCase().includes(q);
      return matchContent || matchSymbol || matchAgent;
    }
    return true;
  });

  const getDirectionBadge = (dir?: string) => {
    if (dir === 'BULLISH') {
      return (
        <span className="flex items-center gap-1 px-2 py-0.5 bg-accent-emerald/20 text-accent-emerald border border-accent-emerald/30 rounded text-[10px] font-bold">
          <TrendingUp className="w-3 h-3" />
          BULLISH
        </span>
      );
    }
    if (dir === 'BEARISH') {
      return (
        <span className="flex items-center gap-1 px-2 py-0.5 bg-accent-rose/20 text-accent-rose border border-accent-rose/30 rounded text-[10px] font-bold">
          <TrendingDown className="w-3 h-3" />
          BEARISH
        </span>
      );
    }
    if (dir === 'RISK_ALERT') {
      return (
        <span className="flex items-center gap-1 px-2 py-0.5 bg-accent-amber/20 text-accent-amber border border-accent-amber/30 rounded text-[10px] font-bold">
          <AlertTriangle className="w-3 h-3" />
          RISK ALERT
        </span>
      );
    }
    return null;
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-background">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between p-5 rounded-xl bg-card border border-card-border shadow-md gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 text-xs font-mono font-bold bg-accent-blue/20 text-accent-cyan border border-accent-blue/40 rounded">
              SEC 17a-4 AUDIT
            </span>
            <span className="text-xs text-slate-400 font-mono">Durable Structured Memory Graph</span>
          </div>
          <h1 className="text-lg font-bold text-slate-100 mt-1">
            Agent Memory Store & Structured Intelligence Graph
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Non-destructive reasoning graph with entity extraction, temporal anchoring, conviction decay, and contradiction tracking.
          </p>
        </div>

        <button
          onClick={fetchData}
          disabled={isLoading}
          className="flex items-center gap-1.5 px-3.5 py-2 bg-background hover:bg-card-border border border-card-border text-slate-200 rounded text-xs font-semibold transition cursor-pointer"
        >
          <RotateCcw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Refresh Intelligence</span>
        </button>
      </div>

      {/* Add Observation Note */}
      <div className="p-5 rounded-xl bg-card border border-card-border">
        <form onSubmit={handleAddNote} className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="text-xs font-bold text-slate-100 uppercase tracking-wide">
              Append Research Observation & Hypothesis
            </span>
            <div className="flex items-center gap-3">
              <input
                type="text"
                value={newNoteSymbol}
                onChange={(e) => setNewNoteSymbol(e.target.value)}
                placeholder="Symbol (e.g. NVDA, SPY)"
                className="bg-background border border-card-border rounded px-2.5 py-1 text-xs font-mono text-slate-200 focus:outline-none focus:border-accent-cyan w-36 uppercase"
              />
              <select
                value={newNoteAgent}
                onChange={(e) => setNewNoteAgent(e.target.value)}
                className="bg-background border border-card-border rounded px-2.5 py-1 text-xs font-mono text-slate-200 focus:outline-none focus:border-accent-cyan"
              >
                <option value="research_manager">research_manager</option>
                <option value="fundamental_agent">fundamental_agent</option>
                <option value="technical_agent">technical_agent</option>
                <option value="falsification_agent">falsification_agent</option>
                <option value="macro_agent">macro_agent</option>
                <option value="risk_agent">risk_agent</option>
              </select>
            </div>
          </div>

          <textarea
            value={newNoteContent}
            onChange={(e) => setNewNoteContent(e.target.value)}
            placeholder="Record material research findings, hypothesis updates, causal claims, or primary-source citations..."
            rows={3}
            className="w-full bg-background border border-card-border rounded p-3 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-accent-cyan transition"
          />

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={isAdding || !newNoteContent.trim()}
              className="flex items-center gap-1.5 px-4 py-2 bg-accent-cyan hover:bg-cyan-500 text-slate-950 font-bold rounded text-xs transition cursor-pointer disabled:opacity-50"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>{isAdding ? 'Appending...' : 'Append to Intelligence Graph'}</span>
            </button>
          </div>
        </form>
      </div>

      {/* Memory Notes Filter & Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 p-4 rounded-xl bg-card border border-card-border">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filter memory by text, symbol, or entity..."
            className="w-full bg-background border border-card-border rounded pl-9 pr-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-accent-cyan"
          />
        </div>

        <div className="flex items-center gap-2">
          <label className="text-[11px] font-mono text-slate-400">Agent:</label>
          <select
            value={selectedAgentFilter}
            onChange={(e) => setSelectedAgentFilter(e.target.value)}
            className="bg-background border border-card-border rounded px-2.5 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-accent-cyan cursor-pointer"
          >
            <option value="ALL">ALL AGENTS</option>
            <option value="research_manager">research_manager</option>
            <option value="fundamental_agent">fundamental_agent</option>
            <option value="technical_agent">technical_agent</option>
            <option value="falsification_agent">falsification_agent</option>
            <option value="macro_agent">macro_agent</option>
            <option value="risk_agent">risk_agent</option>
          </select>
        </div>
      </div>

      {/* Memory Notes Ledger */}
      <div className="p-5 rounded-xl bg-card border border-card-border space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-card-border">
          <div className="flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-accent-cyan" />
            <h2 className="text-xs font-bold text-slate-100 uppercase tracking-wide">
              Intelligence Graph Memory Entries ({filteredNotes.length})
            </h2>
          </div>
          <span className="text-[10px] font-mono text-slate-400">Temporal Point-in-Time Indexed</span>
        </div>

        <div className="divide-y divide-card-border/40 font-mono text-xs">
          {filteredNotes.length === 0 ? (
            <div className="py-8 text-center text-slate-500">
              No memory notes matching criteria. Observations will appear here as agents research symbols.
            </div>
          ) : (
            filteredNotes.map((note) => (
              <div key={note.id} className="py-4 hover:bg-background/40 px-3 rounded space-y-2.5">
                <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-400">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-accent-cyan">{note.agent}</span>
                    <span className="px-1.5 py-0.5 bg-background border border-card-border rounded text-[10px] uppercase">
                      {note.kind}
                    </span>
                    {note.symbol && (
                      <span className="px-1.5 py-0.5 bg-accent-blue/20 text-accent-cyan rounded text-[10px] font-bold">
                        ${note.symbol}
                      </span>
                    )}
                    {getDirectionBadge(note.claim_direction)}
                    {note.decision_id && (
                      <span className="px-1.5 py-0.5 bg-slate-800 text-slate-400 rounded text-[9px]">
                        ID: {note.decision_id}
                      </span>
                    )}
                  </div>
                  <span className="text-[10px] text-slate-400">{new Date(note.created_at).toLocaleString()}</span>
                </div>

                <div className="text-slate-200 leading-relaxed font-sans text-xs">
                  {note.content}
                </div>

                {/* Entity Chips */}
                {note.entities && (
                  <div className="flex flex-wrap items-center gap-1.5 pt-1">
                    {note.entities.sectors?.map((sec, idx) => (
                      <span key={idx} className="px-1.5 py-0.5 bg-accent-emerald/10 text-accent-emerald border border-accent-emerald/20 rounded text-[9px]">
                        sector:{sec}
                      </span>
                    ))}
                    {note.entities.macro_factors?.map((macro, idx) => (
                      <span key={idx} className="px-1.5 py-0.5 bg-accent-amber/10 text-accent-amber border border-accent-amber/20 rounded text-[9px]">
                        macro:{macro}
                      </span>
                    ))}
                    {note.entities.symbols?.map((sym, idx) => (
                      <span key={idx} className="px-1.5 py-0.5 bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/20 rounded text-[9px]">
                        ${sym}
                      </span>
                    ))}
                  </div>
                )}

                {/* Confidence Bar */}
                <div className="flex items-center gap-4 text-[10px] text-slate-400 pt-1">
                  <div className="flex items-center gap-2">
                    <span>Conviction:</span>
                    <div className="w-24 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-accent-cyan rounded-full"
                        style={{ width: `${Math.round(note.confidence * 100)}%` }}
                      />
                    </div>
                    <span className="text-slate-200 font-bold">{(note.confidence * 100).toFixed(0)}%</span>
                  </div>
                  <span>Importance: {(note.importance * 100).toFixed(0)}%</span>
                  <span className="text-slate-500">Status: {note.status?.toUpperCase() || 'ACTIVE'}</span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
