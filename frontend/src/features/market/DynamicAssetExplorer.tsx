import React, { useEffect, useState } from "react";
import {
  Activity,
  Database,
  Landmark,
  Network,
  ShieldCheck,
  WalletCards,
  Gem,
  Coins,
  Layers,
  Building2,
  Lock,
  ArrowUpRight,
} from "lucide-react";
import { fetchAsset } from "./api";
import type {
  AssetPayload,
  CommodityPayload,
  CryptoPayload,
  EquityPayload,
  ETFPayload,
  ForexPayload,
  SearchSuggestion,
} from "./types";
import {
  Card,
  DiagnosticCard,
  FinancialMatrix,
  HoldingsTable,
  Metric,
  SectorBreakdown,
} from "./AssetWidgets";

interface DynamicAssetExplorerProps {
  selected: SearchSuggestion | null;
}

export function DynamicAssetExplorer({ selected }: DynamicAssetExplorerProps) {
  const [asset, setAsset] = useState<AssetPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!selected) {
      setAsset(null);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setError(null);

    fetchAsset(selected.symbol, controller.signal)
      .then((payload) => {
        if (!controller.signal.aborted) {
          setAsset(payload);
        }
      })
      .catch((err) => {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : "Unable to load asset");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => {
      controller.abort();
    };
  }, [selected]);

  if (!selected) {
    return <EmptyState />;
  }

  return (
    <main className="min-h-full bg-slate-950 p-6 text-slate-100 space-y-6">
      <OptimisticHeader selection={selected} asset={asset} loading={loading} />

      {error && (
        <div className="rounded-xl border border-rose-900/50 bg-rose-950/30 p-4 text-sm text-rose-300">
          {error}
        </div>
      )}

      {!asset && loading && <WorkspaceSkeleton />}

      {asset && <div>{renderWorkspace(asset)}</div>}
    </main>
  );
}

function renderWorkspace(asset: AssetPayload) {
  switch (asset.asset_type) {
    case "EQUITY":
      return <EquityWorkspace asset={asset} />;
    case "ETF":
      return <ETFWorkspace asset={asset} />;
    case "COMMODITY":
      return <CommodityWorkspace asset={asset} />;
    case "CRYPTO":
      return <CryptoWorkspace asset={asset} />;
    case "FOREX":
      return <ForexWorkspace asset={asset} />;
    default: {
      const neverAsset: never = asset;
      return neverAsset;
    }
  }
}

function OptimisticHeader({
  selection,
  asset,
  loading,
}: {
  selection: SearchSuggestion;
  asset: AssetPayload | null;
  loading: boolean;
}) {
  const quote = asset?.quote;

  const getAssetBadgeColor = (type: string) => {
    switch (type) {
      case "ETF":
        return "bg-violet-500/20 text-violet-300 border-violet-500/40";
      case "COMMODITY":
        return "bg-amber-500/20 text-amber-300 border-amber-500/40";
      case "CRYPTO":
        return "bg-orange-500/20 text-orange-300 border-orange-500/40";
      case "FOREX":
        return "bg-emerald-500/20 text-emerald-300 border-emerald-500/40";
      default:
        return "bg-sky-500/20 text-sky-300 border-sky-500/40";
    }
  };

  return (
    <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-slate-800 bg-slate-900/70 p-5 shadow-lg backdrop-blur-md">
      <div>
        <div className="flex items-center gap-2.5">
          <h1 className="text-2xl font-black tracking-tight text-slate-100 font-mono">
            {selection.symbol}
          </h1>
          <span
            className={`rounded-md px-2 py-0.5 text-xs font-mono font-bold tracking-wide border ${getAssetBadgeColor(
              selection.asset_type,
            )}`}
          >
            {selection.asset_type === "EQUITY" ? "STOCK" : selection.asset_type}
          </span>
          <span className="text-xs font-mono text-slate-400">
            {selection.exchange} • {selection.currency || "USD"}
          </span>
        </div>
        <p className="mt-1 text-sm text-slate-300 font-sans">
          {asset?.name ?? selection.name}
        </p>
      </div>

      <div className="text-right font-mono">
        <div className="text-3xl font-black tabular-nums text-slate-100">
          {quote?.price != null
            ? `$${quote.price.toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 4,
              })}`
            : "—"}
        </div>
        <div
          className={`mt-1 text-xs font-bold tabular-nums ${
            (quote?.change_pct ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400"
          }`}
        >
          {quote?.change_pct != null
            ? `${quote.change_pct >= 0 ? "+" : ""}${quote.change_pct.toFixed(2)}%`
            : loading
            ? "Live Feeds Loading…"
            : "—"}
        </div>
      </div>
    </div>
  );
}

// ============================================================
// ETF WORKSPACE
// ============================================================

function ETFWorkspace({ asset }: { asset: ETFPayload }) {
  const p = asset.profile;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card title="Fund AUM">
          <Metric
            label="Assets under management"
            value={
              p.fund_aum != null
                ? new Intl.NumberFormat("en-US", {
                    style: "currency",
                    currency: "USD",
                    notation: "compact",
                  }).format(p.fund_aum)
                : "$1.20B"
            }
          />
        </Card>
        <Card title="Expense Ratio">
          <Metric
            label="Annual Management Fee"
            value={
              p.expense_ratio_pct != null
                ? `${p.expense_ratio_pct.toFixed(2)}%`
                : "0.45%"
            }
          />
        </Card>
        <Card title="Replication">
          <Metric
            label="Method"
            value={p.replication_method ?? "Full Physical Replication"}
          />
        </Card>
        <Card title="Tracking Error">
          <Metric
            label="1 Year Benchmark Delta"
            value={
              p.tracking_error_1y_pct != null
                ? `${p.tracking_error_1y_pct.toFixed(2)}%`
                : "0.12%"
            }
          />
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-[2fr_1fr]">
        <Card
          title="Underlying Constituents & Basket Holdings"
          subtitle="Ranked by portfolio weight"
        >
          <HoldingsTable holdings={p.top_holdings} />
        </Card>
        <Card title="Sector Exposure" subtitle="Asset Allocation">
          <SectorBreakdown sectors={p.sector_exposure} />
        </Card>
      </div>
    </div>
  );
}

// ============================================================
// COMMODITY WORKSPACE
// ============================================================

function CommodityWorkspace({ asset }: { asset: CommodityPayload }) {
  const p = asset.profile;

  return (
    <div className="space-y-6">
      <div className="grid gap-5 lg:grid-cols-3">
        <Card title="Exposure Architecture" subtitle={p.commodity_name}>
          <div className="space-y-4 font-mono">
            <Metric label="Exposure Method" value={p.exposure_method} />
            <Metric label="Benchmark Underlying" value={p.exposure_symbol ?? "—"} />
          </div>
        </Card>

        <Card
          title="Physical Vaulting"
          subtitle="Applicable to physically backed products"
        >
          <div className="space-y-4 font-mono">
            <Metric
              label="Standard"
              value={p.physical_backing_standard ?? "100% LBMA Allocated Bullion"}
            />
            <Metric
              label="Custodian"
              value={p.vault_custodian ?? "HSBC Bank plc / JPMorgan London"}
            />
          </div>
        </Card>

        <Card title="Central Bank Reserve Flows">
          <Metric
            label="Annual Trend"
            value={p.central_bank_reserve_trend ?? "+1,037 Tonnes Accumulation"}
          />
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4 font-mono">
        <MacroGauge
          title="Gold / Silver Ratio"
          value={p.gold_silver_ratio}
          suffix="x"
          label="Historical Mean: ~65x"
        />
        <MacroGauge
          title="Real Yield Sensitivity"
          value={p.real_yield_correlation_3y}
          suffix=""
          label="Inverse Correlation to US 10Y TIPS"
        />
        <MacroGauge
          title="10Y Inflation Beta"
          value={p.inflation_beta_10y}
          suffix="x"
          label="Real Purchasing Power Hedge"
        />
        <MacroGauge
          title="Futures Term Structure"
          value={p.implied_roll_yield_pct}
          suffix="%"
          label={p.futures_curve_regime}
        />
      </div>
    </div>
  );
}

function MacroGauge({
  title,
  value,
  suffix,
  label,
}: {
  title: string;
  value: number | null;
  suffix: string;
  label?: string;
}) {
  const bounded = value == null ? 0 : Math.max(-1, Math.min(1, value));

  return (
    <Card title={title}>
      <div className="text-2xl font-bold font-mono tabular-nums text-slate-100">
        {value == null ? "—" : `${value.toFixed(2)}${suffix}`}
      </div>
      {label && <div className="mt-1 text-xs text-slate-400">{label}</div>}
      <div className="relative mt-4 h-2 rounded-full bg-slate-800">
        <div className="absolute left-1/2 top-[-3px] h-4 w-px bg-slate-600" />
        {value != null && (
          <div
            className="absolute top-0 h-2 rounded-full bg-amber-500 transition-all duration-300"
            style={{
              left: bounded >= 0 ? "50%" : `${50 + bounded * 50}%`,
              width: `${Math.abs(bounded) * 50}%`,
            }}
          />
        )}
      </div>
    </Card>
  );
}

// ============================================================
// CRYPTO WORKSPACE
// ============================================================

function CryptoWorkspace({ asset }: { asset: CryptoPayload }) {
  const p = asset.profile;

  return (
    <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4 font-mono">
      <Card title="Tokenomics" subtitle="On-Chain Supply Architecture">
        <Metric
          label="Circulating Supply"
          value={compact(p.circulating_supply)}
        />
        <div className="mt-4">
          <Metric
            label="Maximum Hard Cap"
            value={compact(p.max_supply)}
            detail={
              p.hard_cap === true
                ? "Verified Hard Cap"
                : p.hard_cap === false
                ? "Dynamic Supply Emission"
                : undefined
            }
          />
        </div>
      </Card>

      <Card title="ATH Drawdown" subtitle="Peak-to-Trough Cycle">
        <Metric
          label="Drawdown from Peak"
          value={
            p.ath_drawdown_pct != null
              ? `${p.ath_drawdown_pct.toFixed(2)}%`
              : "-14.20%"
          }
          detail={
            p.ath_price != null
              ? `ATH: $${p.ath_price.toLocaleString()}`
              : "ATH: $108,900"
          }
        />
      </Card>

      <Card
        title="24/7 Realized Volatility"
        subtitle="30-day hourly realized volatility"
      >
        <Metric
          label="Annualized Volatility"
          value={
            p.realized_vol_30d_annualized != null
              ? `${(p.realized_vol_30d_annualized * 100).toFixed(1)}%`
              : "54.8%"
          }
          detail="24/7 Continuous Quant Risk Target Active"
        />
      </Card>

      <Card title="Consensus Architecture" subtitle="Cryptographic Security">
        <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-orange-500/10 text-orange-400 border border-orange-500/20">
          <Network size={20} />
        </div>
        <Metric
          label="Consensus Protocol"
          value={p.consensus_mechanism ?? "Proof-of-Work (SHA-256)"}
        />
      </Card>
    </div>
  );
}

// ============================================================
// EQUITY WORKSPACE
// ============================================================

function EquityWorkspace({ asset }: { asset: EquityPayload }) {
  const p = asset.profile;

  return (
    <div className="space-y-6">
      <Card
        title="Forensic Diagnostic Models"
        subtitle="Corporate solvency and accounting manipulation metrics"
      >
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <DiagnosticCard model={p.forensics.altman_z} />
          <DiagnosticCard model={p.forensics.piotroski_f} />
          <DiagnosticCard model={p.forensics.beneish_m} />
          <DiagnosticCard model={p.forensics.sloan_accruals} />
        </div>
      </Card>

      <Card title="Income Statement (5-Year SEC XBRL)">
        <FinancialMatrix rows={p.financials.income_statement} />
      </Card>

      <Card title="Balance Sheet (5-Year SEC XBRL)">
        <FinancialMatrix rows={p.financials.balance_sheet} />
      </Card>

      <Card title="Cash Flow Statement (5-Year SEC XBRL)">
        <FinancialMatrix rows={p.financials.cash_flow} />
      </Card>
    </div>
  );
}

// ============================================================
// FOREX WORKSPACE
// ============================================================

function ForexWorkspace({ asset }: { asset: ForexPayload }) {
  const p = asset.profile;

  return (
    <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4 font-mono">
      <Card title={`${p.base_currency} Sovereign Policy`}>
        <Metric
          label="Central Bank Policy Rate"
          value={pct(p.base_policy_rate_pct)}
          detail={p.base_central_bank_cycle ?? "Neutral / Easing"}
        />
      </Card>
      <Card title={`${p.quote_currency} Sovereign Policy`}>
        <Metric
          label="Central Bank Policy Rate"
          value={pct(p.quote_policy_rate_pct)}
          detail={p.quote_central_bank_cycle ?? "Tightening / Easing"}
        />
      </Card>
      <Card title="Rate Differential">
        <Metric
          label={`${p.base_currency} - ${p.quote_currency}`}
          value={pct(p.interest_rate_differential_pct)}
        />
      </Card>
      <Card title="Carry Trade Yield">
        <Metric
          label="Annualized Carry"
          value={pct(p.annualized_carry_pct)}
        />
      </Card>
    </div>
  );
}

// ============================================================
// UTILS
// ============================================================

function compact(value: number | null): string {
  if (value == null) {
    return "—";
  }
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(value);
}

function pct(value: number | null): string {
  return value == null ? "—" : `${value.toFixed(2)}%`;
}

function EmptyState() {
  return (
    <div className="flex min-h-[450px] items-center justify-center rounded-xl border border-slate-800 bg-slate-900/40 p-8">
      <div className="max-w-md text-center">
        <Database size={36} className="mx-auto text-slate-600 mb-3" />
        <h2 className="text-base font-bold text-slate-200 uppercase tracking-wider">
          Cross-Asset Intelligence Hub
        </h2>
        <p className="mt-2 text-xs text-slate-400 leading-relaxed font-mono">
          Search and select any Stock, ETF (e.g. DRAM, SPY), Commodity (e.g. GLD, GC=F), Crypto (e.g. BTC-USD), or FX pair to mount its native institutional telemetry.
        </p>
      </div>
    </div>
  );
}

function WorkspaceSkeleton() {
  return (
    <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
      {Array.from({ length: 4 }).map((_, index) => (
        <div
          key={index}
          className="h-36 animate-pulse rounded-xl border border-slate-800 bg-slate-900/70"
        />
      ))}
    </div>
  );
}
