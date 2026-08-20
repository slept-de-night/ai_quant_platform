import React, { useEffect, useRef } from 'react';
import { createChart, IChartApi, ISeriesApi, LineData, Time } from 'lightweight-charts';
import { DailyRecord } from '../../types';

interface EquityChartProps {
  daily: DailyRecord[];
  strategyName: string;
  symbol: string;
  height?: number;
}

export const EquityChart: React.FC<EquityChartProps> = ({ daily, strategyName, symbol, height = 320 }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const strategySeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const benchmarkSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: height,
      layout: {
        background: { color: '#0b1120' },
        textColor: '#94a3b8',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: '#1e293b' },
        horzLines: { color: '#1e293b' },
      },
      crosshair: {
        vertLine: { color: '#38bdf8', width: 1, style: 3 },
        horzLine: { color: '#38bdf8', width: 1, style: 3 },
      },
      timeScale: {
        borderColor: '#1e293b',
        timeVisible: true,
      },
      rightPriceScale: {
        borderColor: '#1e293b',
      },
    });

    const stratLine = chart.addLineSeries({
      color: '#10b981',
      lineWidth: 2,
      title: 'Strategy Equity',
    });

    const benchLine = chart.addLineSeries({
      color: '#64748b',
      lineWidth: 1,
      lineStyle: 2,
      title: `${symbol} Buy & Hold`,
    });

    chartRef.current = chart;
    strategySeriesRef.current = stratLine;
    benchmarkSeriesRef.current = benchLine;

    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: containerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [height, symbol]);

  useEffect(() => {
    if (!daily || daily.length === 0 || !strategySeriesRef.current || !benchmarkSeriesRef.current) return;

    const stratData: LineData<Time>[] = [];
    const benchData: LineData<Time>[] = [];

    const firstClose = daily[0]?.close || 1.0;

    daily.forEach((d) => {
      const timeStr = d.date.split('T')[0] as unknown as Time;
      stratData.push({
        time: timeStr,
        value: d.equity,
      });

      const normalizedBench = d.close / firstClose;
      benchData.push({
        time: timeStr,
        value: normalizedBench,
      });
    });

    strategySeriesRef.current.setData(stratData);
    benchmarkSeriesRef.current.setData(benchData);
    chartRef.current?.timeScale().fitContent();
  }, [daily]);

  return (
    <div className="relative w-full rounded-lg overflow-hidden border border-card-border bg-[#0b1120]">
      <div className="absolute top-2 left-3 z-10 flex items-center gap-3 bg-background/80 px-2.5 py-1 rounded border border-card-border/60 text-xs font-mono">
        <span className="font-bold text-accent-emerald">Strategy: {strategyName}</span>
        <span className="text-slate-400">vs {symbol} Benchmark (Normalized)</span>
      </div>
      <div ref={containerRef} className="w-full" style={{ height }} />
    </div>
  );
};
