import React from 'react';
import {
  LayoutDashboard,
  BrainCircuit,
  GitFork,
  LineChart,
  Cpu,
  ShieldCheck,
  BookOpen,
  Network
} from 'lucide-react';

export type TabKey =
  | 'dashboard'
  | 'intelligence'
  | 'runtime'
  | 'alpha'
  | 'models'
  | 'paper'
  | 'memory'
  | 'architecture';

interface TabNavigationProps {
  activeTab: TabKey;
  onSelectTab: (tab: TabKey) => void;
}

export const TabNavigation: React.FC<TabNavigationProps> = ({ activeTab, onSelectTab }) => {
  const tabs: Array<{ key: TabKey; label: string; icon: React.ReactNode; badge?: string }> = [
    { key: 'dashboard', label: 'Dashboard', icon: <LayoutDashboard className="w-4 h-4" /> },
    { key: 'intelligence', label: 'Intelligence Hub', icon: <BrainCircuit className="w-4 h-4" /> },
    { key: 'runtime', label: 'Task Runtime (DAG)', icon: <GitFork className="w-4 h-4" /> },
    { key: 'alpha', label: 'Alpha & Quant Studio', icon: <LineChart className="w-4 h-4" /> },
    { key: 'models', label: 'Model Routing & Control', icon: <Cpu className="w-4 h-4" /> },
    { key: 'paper', label: 'Paper Trading Desk', icon: <ShieldCheck className="w-4 h-4" /> },
    { key: 'memory', label: 'Memory & Audit', icon: <BookOpen className="w-4 h-4" /> },
    { key: 'architecture', label: 'System Architecture', icon: <Network className="w-4 h-4" />, badge: 'Big Fund' },
  ];

  return (
    <nav className="flex items-center px-4 bg-terminal border-b border-card-border overflow-x-auto select-none gap-1 py-1">
      {tabs.map((tab) => {
        const isActive = activeTab === tab.key;
        return (
          <button
            key={tab.key}
            onClick={() => onSelectTab(tab.key)}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-t-md text-xs font-medium transition cursor-pointer whitespace-nowrap border-b-2 ${
              isActive
                ? 'bg-card text-accent-cyan border-accent-cyan shadow-sm font-semibold'
                : 'text-slate-400 hover:text-slate-200 hover:bg-card/50 border-transparent'
            }`}
          >
            {tab.icon}
            <span>{tab.label}</span>
            {tab.badge && (
              <span className="px-1 py-0.2 text-[9px] font-mono font-bold bg-accent-purple/30 text-accent-purple border border-accent-purple/40 rounded">
                {tab.badge}
              </span>
            )}
          </button>
        );
      })}
    </nav>
  );
};
