import React, { useState } from 'react';
import {
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  RefreshCw,
  X,
  CheckCircle2,
  AlertCircle,
  FileCheck2,
  Lock,
} from 'lucide-react';
import { ReadinessReport } from '../../types';
import { api } from '../../services/api';

interface UnfreezeModalProps {
  isOpen: boolean;
  onClose: () => void;
  readiness: ReadinessReport | null;
  onSuccess: () => void;
}

export const UnfreezeModal: React.FC<UnfreezeModalProps> = ({
  isOpen,
  onClose,
  readiness,
  onSuccess,
}) => {
  const [reason, setReason] = useState('');
  const [operator, setOperator] = useState('lead-quant-operator');
  const [override, setOverride] = useState(false);
  const [isRunningRecon, setIsRunningRecon] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [blockingErrors, setBlockingErrors] = useState<string[]>([]);

  if (!isOpen) return null;

  const handleRunReconciliation = async () => {
    try {
      setIsRunningRecon(true);
      setErrorMessage(null);
      await api.runReconciliation();
      onSuccess();
    } catch (err: any) {
      setErrorMessage(`Reconciliation execution failed: ${err.message}`);
    } finally {
      setIsRunningRecon(false);
    }
  };

  const handleUnfreeze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reason.trim()) {
      setErrorMessage('A valid operational justification reason is strictly required by institutional compliance.');
      return;
    }

    try {
      setIsSubmitting(true);
      setErrorMessage(null);
      setBlockingErrors([]);

      await api.disengageKillSwitch(reason.trim(), operator.trim(), '', override);
      onSuccess();
      onClose();
    } catch (err: any) {
      if (err.data?.blocking_reasons) {
        setBlockingErrors(err.data.blocking_reasons);
        setErrorMessage(err.data.message || 'Execution resume blocked by safety boundary.');
      } else {
        setErrorMessage(err.message || 'Failed to disengage kill switch.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const reconStatus = readiness?.reconciliation?.status || 'UNKNOWN';
  const isReconClean = reconStatus === 'CLEAN';
  const isReconFresh = readiness?.reconciliation?.is_fresh ?? false;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="bg-terminal border border-card-border rounded-xl max-w-xl w-full shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-4 bg-card/60 border-b border-card-border flex items-center justify-between">
          <div className="flex items-center gap-2.5 text-accent-cyan">
            <div className="p-2 rounded-lg bg-accent-cyan/10 border border-accent-cyan/20">
              <Lock className="w-5 h-5 text-accent-cyan" />
            </div>
            <div>
              <h3 className="font-bold text-slate-100 text-base">Gated Execution Resume Protocol</h3>
              <p className="text-xs text-slate-400">Institutional Safety & Pre-Trade Gate Clearance</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-card-border/50 transition cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleUnfreeze} className="p-6 space-y-5 overflow-y-auto flex-1 text-sm">
          {/* Current Freeze Status */}
          <div className="p-3.5 rounded-lg bg-accent-rose/10 border border-accent-rose/30 space-y-1.5">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-accent-rose font-bold flex items-center gap-1.5">
                <ShieldAlert className="w-4 h-4" /> CURRENT STATUS: FROZEN
              </span>
              <span className="text-slate-400">
                {readiness?.frozen_at ? new Date(readiness.frozen_at).toLocaleTimeString() : 'Active'}
              </span>
            </div>
            <p className="text-xs text-slate-200">
              <span className="text-slate-400">Freeze Trigger:</span>{' '}
              <span className="font-semibold text-rose-300">
                {readiness?.freeze_reason || 'Emergency Manual Kill Switch or Reconciliation Fault'}
              </span>
            </p>
          </div>

          {/* Safety Checklist */}
          <div className="space-y-2">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Pre-Trade Clearance Prerequisites
            </h4>
            <div className="grid grid-cols-1 gap-2 text-xs font-mono">
              {/* Journal Ready */}
              <div className="flex items-center justify-between p-2.5 rounded bg-card/40 border border-card-border">
                <span className="text-slate-300 flex items-center gap-2">
                  <FileCheck2 className="w-3.5 h-3.5 text-accent-cyan" /> Event-Sourced Journal
                </span>
                {readiness?.journal_ready ? (
                  <span className="text-accent-emerald font-semibold flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" /> READY
                  </span>
                ) : (
                  <span className="text-accent-rose font-semibold flex items-center gap-1">
                    <AlertCircle className="w-3.5 h-3.5" /> FAULT
                  </span>
                )}
              </div>

              {/* Active Broker */}
              <div className="flex items-center justify-between p-2.5 rounded bg-card/40 border border-card-border">
                <span className="text-slate-300 flex items-center gap-2">
                  <ShieldCheck className="w-3.5 h-3.5 text-accent-cyan" /> Active Broker: {readiness?.active_broker || 'none'}
                </span>
                {readiness?.broker_ready ? (
                  <span className="text-accent-emerald font-semibold flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" /> CONNECTED
                  </span>
                ) : (
                  <span className="text-accent-amber font-semibold flex items-center gap-1">
                    <AlertTriangle className="w-3.5 h-3.5" /> NOT READY
                  </span>
                )}
              </div>

              {/* Reconciliation Evidence */}
              <div className="flex items-center justify-between p-2.5 rounded bg-card/40 border border-card-border">
                <div className="flex items-center gap-2">
                  <RefreshCw className={`w-3.5 h-3.5 text-accent-cyan ${isRunningRecon ? 'animate-spin' : ''}`} />
                  <div>
                    <span className="text-slate-300">Reconciliation Evidence:</span>{' '}
                    <span className="text-slate-400">
                      {reconStatus} {readiness?.reconciliation?.last_run_at ? `(${isReconFresh ? 'Fresh' : 'Stale'})` : ''}
                    </span>
                  </div>
                </div>
                {isReconClean && isReconFresh ? (
                  <span className="text-accent-emerald font-semibold flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" /> 0 MISMATCHES
                  </span>
                ) : (
                  <button
                    type="button"
                    onClick={handleRunReconciliation}
                    disabled={isRunningRecon}
                    className="px-2 py-0.5 rounded bg-accent-cyan/15 hover:bg-accent-cyan/25 border border-accent-cyan/30 text-accent-cyan text-[11px] font-semibold transition cursor-pointer"
                  >
                    {isRunningRecon ? 'Reconciling...' : 'Run Recon'}
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Blocking Errors Display */}
          {blockingErrors.length > 0 && (
            <div className="p-3 rounded bg-accent-rose/10 border border-accent-rose/40 text-accent-rose text-xs space-y-1">
              <span className="font-bold flex items-center gap-1">
                <AlertCircle className="w-3.5 h-3.5" /> Safety Gate Failures:
              </span>
              <ul className="list-disc pl-4 space-y-0.5">
                {blockingErrors.map((b, i) => (
                  <li key={i}>{b}</li>
                ))}
              </ul>
            </div>
          )}

          {errorMessage && blockingErrors.length === 0 && (
            <div className="p-3 rounded bg-accent-rose/10 border border-accent-rose/40 text-accent-rose text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Input: Operator ID */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300">Operator Sign-Off Identity</label>
            <input
              type="text"
              value={operator}
              onChange={(e) => setOperator(e.target.value)}
              className="w-full bg-card/60 border border-card-border rounded-lg px-3 py-2 text-xs font-mono text-slate-100 focus:outline-none focus:border-accent-cyan"
              placeholder="e.g. risk-officer-john"
              required
            />
          </div>

          {/* Input: Justification Reason */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300 flex items-center justify-between">
              <span>Operational Justification / Audit Reason</span>
              <span className="text-[11px] text-accent-rose font-normal">*Required by SEC / FINRA OMS Rule</span>
            </label>
            <textarea
              rows={2}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="w-full bg-card/60 border border-card-border rounded-lg px-3 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-accent-cyan resize-none"
              placeholder="e.g. Completed broker ledger audit; confirmed 0 discrepancies and approved resumption of trend trading strategy."
              required
            />
          </div>

          {/* Compliance Override Checkbox */}
          <div className="flex items-start gap-2 pt-1">
            <input
              type="checkbox"
              id="compliance-override"
              checked={override}
              onChange={(e) => setOverride(e.target.checked)}
              className="mt-0.5 rounded bg-background border-card-border text-accent-cyan focus:ring-0"
            />
            <label htmlFor="compliance-override" className="text-[11px] text-slate-400 leading-tight">
              I acknowledge that I am manually attesting to the integrity of this trading posture and assume operational responsibility for clearing this kill switch.
            </label>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-2 border-t border-card-border">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg bg-background hover:bg-card-border text-slate-300 hover:text-white text-xs font-semibold transition cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !reason.trim()}
              className="px-4 py-2 rounded-lg bg-accent-emerald hover:bg-emerald-600 disabled:opacity-50 text-slate-950 text-xs font-bold transition flex items-center gap-1.5 cursor-pointer shadow-lg shadow-emerald-500/20"
            >
              {isSubmitting ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Verifying Safety Gates...
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-3.5 h-3.5" /> Disengage Kill Switch & Resume Trading
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
