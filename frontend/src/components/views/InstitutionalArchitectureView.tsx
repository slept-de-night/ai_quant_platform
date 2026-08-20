import React, { useEffect, useState } from 'react';
import { api } from '../../services/api';
import {
  Network,
  Database,
  BrainCircuit,
  LineChart,
  ShieldCheck,
  Cpu,
  Lock,
  LayoutDashboard,
  CheckCircle2,
  Layers,
  ArrowDown
} from 'lucide-react';

export const InstitutionalArchitectureView: React.FC = () => {
  const [architecture, setArchitecture] = useState<any>(null);

  useEffect(() => {
    const fetchArch = async () => {
      try {
        const res = await api.getArchitecture();
        setArchitecture(res);
      } catch (err) {
        console.error('Failed to load architecture:', err);
      }
    };
    fetchArch();
  }, []);

  const layerIcons: Record<string, React.ReactNode> = {
    layer_1: <Database className="w-5 h-5 text-accent-cyan" />,
    layer_2: <BrainCircuit className="w-5 h-5 text-accent-purple" />,
    layer_3: <LineChart className="w-5 h-5 text-accent-emerald" />,
    layer_4: <ShieldCheck className="w-5 h-5 text-accent-rose" />,
    layer_5: <Cpu className="w-5 h-5 text-accent-amber" />,
    layer_6: <Lock className="w-5 h-5 text-accent-blue" />,
    layer_7: <LayoutDashboard className="w-5 h-5 text-accent-cyan" />,
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-background">
      {/* Header */}
      <div className="p-5 rounded-xl bg-gradient-to-r from-card via-[#131d36] to-card border border-card-border shadow-lg">
        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 text-xs font-mono font-bold bg-accent-purple/20 text-accent-purple border border-accent-purple/40 rounded">
            BIG FUND BLUEPRINT
          </span>
          <span className="text-xs text-slate-400 font-mono">Institutional Enterprise Grade</span>
        </div>
        <h1 className="text-xl font-bold text-slate-100 mt-1">
          Full 7-Layer Software Architecture Specification
        </h1>
        <p className="text-xs text-slate-400 mt-0.5">
          End-to-end design for quantitative hedge funds: from nanosecond market data streaming to AI research DAGs and Go OMS/EMS execution.
        </p>
      </div>

      {/* 7 Architecture Layers Stack */}
      <div className="space-y-4">
        {(architecture?.layers || [
          {
            id: 'layer_1',
            name: 'Layer 1: Market Data Fabric & Time-Series Warehouse',
            components: ['Kafka/Redpanda Tick Ingestion', 'ClickHouse/QuestDB PIT Store', 'Feast Feature Store'],
            status: 'active',
            description: 'High-throughput streaming market data with point-in-time non-lookahead financial databases.'
          },
          {
            id: 'layer_2',
            name: 'Layer 2: AI Multi-Agent Research & Reasoning DAG',
            components: ['Fundamental XBRL Agent', 'Technical Agent', 'Macro/Cross-Asset Agent', 'Evidence Falsifier', 'Empirical Model Router'],
            status: 'active',
            description: 'Durable task scheduler orchestrating multi-LLM research with primary-source verification.'
          },
          {
            id: 'layer_3',
            name: 'Layer 3: Quantitative Alpha & Factor Risk Engine',
            components: ['Alpha Factory', 'Walk-Forward CPCV Validation', 'Barra Factor Model', 'Deflated Sharpe Overfitting Tests'],
            status: 'active',
            description: 'Rigorous quantitative research and multi-factor portfolio optimization.'
          },
          {
            id: 'layer_4',
            name: 'Layer 4: Institutional Risk & Pre-Trade Safety Engine',
            components: ['Deterministic Hard Limits', 'Parametric/Historical VaR (95%/99%)', 'Expected Shortfall (cVaR)', 'Automated Circuit Breakers'],
            status: 'active',
            description: 'Sub-millisecond risk checks and kill-switch safeguards.'
          },
          {
            id: 'layer_5',
            name: 'Layer 5: High-Performance Go OMS/EMS Core',
            components: ['Go Execution Core (aq-engine-go)', 'TWAP/VWAP/IS Slicing', 'FIX 4.4/5.0 Gateways', 'Alpaca Paper Client'],
            status: 'active',
            description: 'Low-latency order routing, execution algorithms, and broker reconciliation.'
          },
          {
            id: 'layer_6',
            name: 'Layer 6: Governance, Security & SEC Compliance',
            components: ['WORM Immutable Audit Ledger', 'Maker-Checker Authorization', 'Role-Based Access Control', 'Vault Secrets'],
            status: 'active',
            description: 'Regulatory compliance (SEC 17a-4, FINRA 4511) and cryptographically audited workflows.'
          },
          {
            id: 'layer_7',
            name: 'Layer 7: Modern Quantitative Trading Workstation',
            components: ['React 19 / TypeScript', 'Tailwind CSS', 'TradingView Lightweight Charts', 'Interactive DAG Visualizer'],
            status: 'active',
            description: 'Bloomberg-grade high-density dark terminal trading workstation.'
          }
        ]).map((layer: any, idx: number) => (
          <div key={layer.id} className="relative">
            <div className="p-5 rounded-xl bg-card border border-card-border hover:border-accent-cyan/50 transition">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pb-3 border-b border-card-border">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-lg bg-background border border-card-border">
                    {layerIcons[layer.id] || <Layers className="w-5 h-5 text-accent-cyan" />}
                  </div>
                  <div>
                    <h2 className="text-sm font-bold text-slate-100">{layer.name}</h2>
                    <p className="text-xs text-slate-400 mt-0.5">{layer.description}</p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-accent-emerald/20 text-accent-emerald text-xs font-mono font-semibold border border-accent-emerald/30">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>OPERATIONAL</span>
                  </span>
                </div>
              </div>

              {/* Components Pill List */}
              <div className="mt-4 flex flex-wrap gap-2">
                {layer.components.map((comp: string, cIdx: number) => (
                  <span
                    key={cIdx}
                    className="px-2.5 py-1 rounded bg-background border border-card-border text-xs font-mono text-slate-300"
                  >
                    {comp}
                  </span>
                ))}
              </div>
            </div>

            {idx < 6 && (
              <div className="flex justify-center my-1">
                <ArrowDown className="w-4 h-4 text-slate-600 animate-bounce" />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
