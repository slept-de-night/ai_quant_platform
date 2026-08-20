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
  Tag
} from 'lucide-react';

export const MemoryAuditView: React.FC = () => {
  const [notes, setNotes] = useState<MemoryNote[]>([]);
  const [journals, setJournals] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [newNoteContent, setNewNoteContent] = useState('');
  const [newNoteAgent, setNewNoteAgent] = useState('research_manager');
  const [isAdding, setIsAdding] = useState(false);

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
        confidence: 0.85,
        importance: 0.75,
      });
      setNewNoteContent('');
      await fetchData();
    } catch (err) {
      console.error('Failed to add note:', err);
    } finally {
      setIsAdding(false);
    }
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
            <span className="text-xs text-slate-400 font-mono">Durable Memory Store</span>
          </div>
          <h1 className="text-lg font-bold text-slate-100 mt-1">
            Agent Memory Store & WORM Audit Journals
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Non-destructive historical reasoning notes with automatic consolidation and regulatory audit trails.
          </p>
        </div>

        <button
          onClick={fetchData}
          disabled={isLoading}
          className="flex items-center gap-1.5 px-3.5 py-2 bg-background hover:bg-card-border border border-card-border text-slate-200 rounded text-xs font-semibold transition cursor-pointer"
        >
          <RotateCcw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Refresh Audit</span>
        </button>
      </div>

      {/* Add Observation Note */}
      <div className="p-5 rounded-xl bg-card border border-card-border">
        <form onSubmit={handleAddNote} className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-100 uppercase tracking-wide">
              Append Research Observation
            </span>
            <select
              value={newNoteAgent}
              onChange={(e) => setNewNoteAgent(e.target.value)}
              className="bg-background border border-card-border rounded px-2.5 py-1 text-xs font-mono text-slate-200 focus:outline-none focus:border-accent-cyan"
            >
              <option value="research_manager">research_manager</option>
              <option value="fundamental_agent">fundamental_agent</option>
              <option value="technical_agent">technical_agent</option>
              <option value="falsification_agent">falsification_agent</option>
            </select>
          </div>

          <textarea
            value={newNoteContent}
            onChange={(e) => setNewNoteContent(e.target.value)}
            placeholder="Record material research findings, hypothesis updates, or primary-source citations..."
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
              <span>{isAdding ? 'Appending...' : 'Append to Ledger'}</span>
            </button>
          </div>
        </form>
      </div>

      {/* Memory Notes Ledger */}
      <div className="p-5 rounded-xl bg-card border border-card-border">
        <div className="flex items-center justify-between pb-3 border-b border-card-border mb-4">
          <div className="flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-accent-cyan" />
            <h2 className="text-xs font-bold text-slate-100 uppercase tracking-wide">
              Active Agent Memory Entries ({notes.length})
            </h2>
          </div>
          <span className="text-[10px] font-mono text-slate-400">Cryptographically Chained</span>
        </div>

        <div className="divide-y divide-card-border/40 font-mono text-xs">
          {notes.length === 0 ? (
            <div className="py-6 text-center text-slate-500">
              No memory notes recorded. Observations will appear here as agents research symbols.
            </div>
          ) : (
            notes.map((note) => (
              <div key={note.id} className="py-3 hover:bg-background/40 px-2 rounded">
                <div className="flex items-center justify-between text-[11px] text-slate-400">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-accent-cyan">{note.agent}</span>
                    <span className="px-1.5 py-0.2 bg-background border border-card-border rounded text-[10px]">
                      {note.kind}
                    </span>
                    {note.symbol && (
                      <span className="px-1.5 py-0.2 bg-accent-blue/20 text-accent-cyan rounded text-[10px] font-bold">
                        {note.symbol}
                      </span>
                    )}
                  </div>
                  <span>{new Date(note.created_at).toLocaleString()}</span>
                </div>
                <div className="mt-1.5 text-slate-200 leading-relaxed font-sans text-xs">
                  {note.content}
                </div>
                <div className="mt-2 flex items-center gap-4 text-[10px] text-slate-400">
                  <span>Confidence: {(note.confidence * 100).toFixed(0)}%</span>
                  <span>Importance: {(note.importance * 100).toFixed(0)}%</span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
