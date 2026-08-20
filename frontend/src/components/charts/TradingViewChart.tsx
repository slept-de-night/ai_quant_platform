import React, { useEffect, useRef } from 'react';
import { createChart, IChartApi, ISeriesApi, CandlestickData, HistogramData, Time } from 'lightweight-charts';

interface BarData {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

interface TradingViewChartProps {
  data: BarData[];
  symbol: string;
  height?: number;
}

export const TradingViewChart: React.FC<TradingViewChartProps> = ({ data, symbol, height = 380 }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Initialize Lightweight Chart
    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
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
        secondsVisible: false,
      },
      rightPriceScale: {
        borderColor: '#1e293b',
        scaleMargins: {
          top: 0.1,
          bottom: 0.2,
        },
      },
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#10b981',
      downColor: '#f43f5e',
      borderVisible: false,
      wickUpColor: '#10b981',
      wickDownColor: '#f43f5e',
    });

    const volumeSeries = chart.addHistogramSeries({
      color: '#3b82f6',
      priceFormat: {
        type: 'volume',
      },
      priceScaleId: '',
    });

    volumeSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.8,
        bottom: 0,
      },
    });

    chartRef.current = chart;
    candlestickSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    // Handle Resize
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [height]);

  useEffect(() => {
    if (!data || data.length === 0 || !candlestickSeriesRef.current || !volumeSeriesRef.current) return;

    const candleData: CandlestickData<Time>[] = [];
    const volData: HistogramData<Time>[] = [];

    // Ensure strictly ascending chronological order
    const sortedData = [...data].sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());

    sortedData.forEach((d) => {
      const timeStr = d.time.split('T')[0] as unknown as Time;
      candleData.push({
        time: timeStr,
        open: d.open,
        high: d.high,
        low: d.low,
        close: d.close,
      });

      if (d.volume !== undefined) {
        volData.push({
          time: timeStr,
          value: d.volume,
          color: d.close >= d.open ? 'rgba(16, 185, 129, 0.35)' : 'rgba(244, 63, 94, 0.35)',
        });
      }
    });

    candlestickSeriesRef.current.setData(candleData);
    volumeSeriesRef.current.setData(volData);
    chartRef.current?.timeScale().fitContent();
  }, [data]);

  return (
    <div className="relative w-full rounded-lg overflow-hidden border border-card-border bg-[#0b1120]">
      {/* Chart Title Header */}
      <div className="absolute top-2 left-3 z-10 flex items-center gap-2 bg-background/80 px-2 py-1 rounded border border-card-border/60 text-xs font-mono">
        <span className="font-bold text-accent-cyan">{symbol}</span>
        <span className="text-slate-400">1D Candlestick & Volume</span>
      </div>
      <div ref={chartContainerRef} className="w-full" style={{ height }} />
    </div>
  );
};
