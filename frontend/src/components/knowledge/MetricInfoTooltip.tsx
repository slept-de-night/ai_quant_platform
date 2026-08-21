import React, { useState } from 'react';
import { HelpCircle, Info, BookOpen } from 'lucide-react';
import { api } from '../../services/api';
import { MetricExplanationResult } from '../../types';

interface MetricInfoTooltipProps {
  metricId: string;
  value?: any;
  symbol?: string;
  assetType?: string;
  sector?: string;
  onOpenKnowledgeBase?: (metricId: string) => void;
}

export const MetricInfoTooltip: React.FC<MetricInfoTooltipProps> = ({
  metricId,
  value,
  symbol = 'AAPL',
  assetType = 'EQUITY',
  sector,
  onOpenKnowledgeBase,
}) => {
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [explanation, setExplanation] = useState<MetricExplanationResult | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const handleToggle = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!isOpen && !explanation) {
      setIsLoading(true);
      try {
        const res = await api.explainMetric({
          metric_id: metricId,
          value,
          symbol,
          asset_type: assetType,
          sector,
        });
        setExplanation(res);
      } catch (err) {
        console.error('Failed to fetch metric explanation:', err);
      } finally {
        setIsLoading(false);
      }
    }
    setIsOpen(!isOpen);
  };

  return (
    <div className="relative inline-block ml-1.5 align-middle">
      <button
        type="button"
        onClick={handleToggle}
        className="p-0.5 text-slate-400 hover:text-emerald-400 rounded transition-colors focus:outline-none"
        title="Learning Mode: Click to explain metric"
      >
        <HelpCircle className="w-3.5 h-3.5" />
      </button>

      {isOpen && (
        <div
          className="absolute z-50 left-0 bottom-full mb-2 w-72 p-3 bg-slate-900 border border-slate-700 rounded-lg shadow-xl text-left text-slate-100 text-xs animate-in fade-in duration-150"
          onClick={(e) => e.stopPropagation()}
        >
          {isLoading ? (
            <div className="text-center py-2 text-slate-400 text-[11px] animate-pulse">
              Consulting Financial Knowledge Registry...
            </div>
          ) : explanation ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between border-b border-slate-800 pb-1.5">
                <span className="font-bold text-emerald-400">{explanation.name || metricId}</span>
                {explanation.zone && (
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-slate-800 text-slate-300">
                    {explanation.zone}
                  </span>
                )}
              </div>

              {!explanation.is_applicable ? (
                <div className="p-2 rounded bg-amber-950/40 border border-amber-800/60 text-amber-300 space-y-1">
                  <div className="font-semibold text-[11px]">Asset Class Notice</div>
                  <div className="text-[10px] leading-tight">{explanation.inapplicable_reason}</div>
                  {explanation.recommended_alternative && (
                    <div className="text-[10px] text-slate-300 pt-1">
                      <span className="text-amber-400 font-medium">Alternative:</span> {explanation.recommended_alternative}
                    </div>
                  )}
                </div>
              ) : (
                <>
                  <p className="text-slate-300 text-[11px] leading-relaxed">{explanation.summary}</p>
                  {explanation.assessment && (
                    <div className="p-2 rounded bg-slate-950 border border-slate-800 text-emerald-300 font-mono text-[10px] leading-tight">
                      {explanation.assessment}
                    </div>
                  )}
                  {explanation.quant_impact && (
                    <div className="text-[10px] text-slate-400">
                      <span className="text-slate-200 font-semibold">Quant Impact:</span> {explanation.quant_impact}
                    </div>
                  )}
                </>
              )}

              {onOpenKnowledgeBase && (
                <button
                  type="button"
                  onClick={() => {
                    setIsOpen(false);
                    onOpenKnowledgeBase(metricId);
                  }}
                  className="w-full mt-1 pt-1.5 border-t border-slate-800 flex items-center justify-center gap-1 text-[11px] text-emerald-400 hover:text-emerald-300 font-medium transition-colors"
                >
                  <BookOpen className="w-3 h-3" /> View In Knowledge Base
                </button>
              )}
            </div>
          ) : (
            <div className="text-slate-400 text-[11px]">No explanation available.</div>
          )}
        </div>
      )}
    </div>
  );
};
