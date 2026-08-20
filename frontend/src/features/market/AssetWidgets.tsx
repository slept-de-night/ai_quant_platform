import React from "react";
import type {
  DiagnosticModel,
  ETFHolding,
  SectorWeight,
  StatementRow,
} from "./types";

export function Card({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/70 p-5 shadow-lg shadow-black/10">
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-slate-100">{title}</h3>
        {subtitle && <p className="mt-1 text-xs text-slate-500">{subtitle}</p>}
      </div>
      {children}
    </section>
  );
}

export function Metric({
  label,
  value,
  detail,
}: {
  label: string;
  value: React.ReactNode;
  detail?: string;
}) {
  return (
    <div>
      <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500">
        {label}
      </div>
      <div className="mt-1 text-xl font-semibold text-slate-100">{value}</div>
      {detail && <div className="mt-1 text-xs text-slate-500">{detail}</div>}
    </div>
  );
}

export function HoldingsTable({ holdings }: { holdings: ETFHolding[] }) {
  const max = Math.max(...holdings.map((x) => x.weight_pct), 1);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm font-mono">
        <thead>
          <tr className="border-b border-slate-800 text-left text-[11px] uppercase tracking-wide text-slate-500">
            <th className="pb-3 px-2">#</th>
            <th className="pb-3 px-2">Holding</th>
            <th className="pb-3 px-2">Sector</th>
            <th className="pb-3 px-2 text-right">Weight</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((holding, index) => (
            <tr
              key={`${holding.symbol ?? holding.name}:${index}`}
              className="border-b border-slate-800/60 last:border-0 hover:bg-slate-800/30 transition"
            >
              <td className="py-3 px-2 text-xs text-slate-600 font-bold">{index + 1}</td>
              <td className="min-w-[200px] py-3 px-2">
                <div className="flex items-center gap-2">
                  {holding.symbol && (
                    <span className="rounded-md bg-slate-800 px-2 py-0.5 text-xs font-semibold text-sky-300 border border-sky-500/20">
                      {holding.symbol}
                    </span>
                  )}
                  <span className="truncate text-slate-200 font-sans">{holding.name}</span>
                </div>
              </td>
              <td className="py-3 px-2 text-xs text-slate-400 font-sans">
                {holding.sector ?? "—"}
              </td>
              <td className="w-56 py-3 px-2">
                <div className="flex items-center justify-end gap-3">
                  <div className="h-1.5 w-28 overflow-hidden rounded-full bg-slate-800">
                    <div
                      className="h-full rounded-full bg-sky-500 transition-all duration-300"
                      style={{
                        width: `${(holding.weight_pct / max) * 100}%`,
                      }}
                    />
                  </div>
                  <span className="w-16 text-right tabular-nums text-slate-300 font-bold text-xs">
                    {holding.weight_pct.toFixed(2)}%
                  </span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function SectorBreakdown({ sectors }: { sectors: SectorWeight[] }) {
  const sorted = [...sectors].sort((a, b) => b.weight_pct - a.weight_pct);

  return (
    <div className="space-y-3 font-mono">
      {sorted.map((sector) => (
        <div key={sector.sector}>
          <div className="mb-1 flex justify-between text-xs font-sans">
            <span className="text-slate-300">{sector.sector}</span>
            <span className="tabular-nums font-mono text-slate-400 font-bold">
              {sector.weight_pct.toFixed(2)}%
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-slate-800">
            <div
              className="h-full rounded-full bg-violet-500 transition-all duration-300"
              style={{
                width: `${Math.min(sector.weight_pct, 100)}%`,
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function compactNumber(value: number | null): string {
  if (value === null) {
    return "—";
  }
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(value);
}

export function FinancialMatrix({ rows }: { rows: StatementRow[] }) {
  const years = Array.from(
    new Set(
      rows.flatMap((row) => row.values.map((value) => value.fiscal_year)),
    ),
  ).sort((a, b) => b - a);

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm font-mono">
        <thead>
          <tr className="border-b border-slate-800">
            <th className="py-2.5 pr-8 text-left text-xs font-medium text-slate-500 font-sans">
              Financial Statement Line Item
            </th>
            {years.map((year) => (
              <th
                key={year}
                className="px-4 py-2.5 text-right text-xs font-medium text-slate-400"
              >
                FY {year}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.key}
              className="border-b border-slate-800/50 hover:bg-slate-800/20 transition"
            >
              <td className="py-3 pr-8 text-slate-300 font-sans">{row.label}</td>
              {years.map((year) => {
                const point = row.values.find((x) => x.fiscal_year === year);
                return (
                  <td
                    key={year}
                    className="px-4 py-3 text-right font-mono text-xs tabular-nums text-slate-200"
                  >
                    {point?.value !== undefined && point.value !== null
                      ? `$${compactNumber(point.value)}`
                      : "—"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function DiagnosticCard({ model }: { model: DiagnosticModel }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-4 shadow-sm">
      <div className="text-xs font-bold uppercase tracking-wider text-slate-400">
        {model.name}
      </div>
      {model.available ? (
        <>
          <div className="mt-2 text-2xl font-black font-mono tabular-nums text-slate-100">
            {model.score !== null ? (typeof model.score === "number" ? model.score.toFixed(2) : model.score) : "—"}
          </div>
          <div className="mt-1 text-xs font-mono text-emerald-400 font-semibold">
            {model.zone ?? "Safe Zone"}
          </div>
        </>
      ) : (
        <div className="mt-3 text-xs leading-relaxed text-slate-500">
          {model.reason ?? "Diagnostic Unavailable"}
        </div>
      )}
    </div>
  );
}
