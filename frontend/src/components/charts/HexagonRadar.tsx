import React from 'react';

export interface HexagonScores {
  profitability?: number;
  growth?: number;
  value?: number;
  valuation?: number;
  solvency?: number;
  health?: number;
  momentum?: number;
  safety?: number;
  quality?: number;
  overall?: number;
}

interface HexagonRadarProps {
  scores?: HexagonScores;
  size?: number;
}

export const HexagonRadar: React.FC<HexagonRadarProps> = ({
  scores = {
    profitability: 75,
    growth: 82,
    value: 60,
    solvency: 88,
    momentum: 79,
    safety: 70,
    overall: 76,
  },
  size = 280,
}) => {
  const center = size / 2;
  const radius = size * 0.38;

  const categories = [
    { key: 'profitability', label: 'Profitability', val: scores.profitability ?? 50 },
    { key: 'growth', label: 'Growth', val: scores.growth ?? 50 },
    { key: 'value', label: 'Value', val: scores.value ?? scores.valuation ?? 50 },
    { key: 'solvency', label: 'Solvency', val: scores.solvency ?? scores.health ?? 50 },
    { key: 'momentum', label: 'Momentum', val: scores.momentum ?? 50 },
    { key: 'safety', label: 'Safety', val: scores.safety ?? scores.quality ?? 50 },
  ];


  const numPoints = categories.length;
  const angleStep = (Math.PI * 2) / numPoints;

  // Grid levels (25%, 50%, 75%, 100%)
  const gridLevels = [0.25, 0.5, 0.75, 1.0];

  const getCoordinates = (index: number, valueRatio: number) => {
    const angle = index * angleStep - Math.PI / 2;
    const r = radius * valueRatio;
    return {
      x: center + r * Math.cos(angle),
      y: center + r * Math.sin(angle),
    };
  };

  // Build polygon path for data
  const dataPoints = categories.map((cat, idx) => {
    const ratio = Math.max(0.1, Math.min(1.0, cat.val / 100));
    return getCoordinates(idx, ratio);
  });

  const dataPath = dataPoints.map((pt, i) => `${i === 0 ? 'M' : 'L'} ${pt.x} ${pt.y}`).join(' ') + ' Z';

  return (
    <div className="flex flex-col items-center justify-center">
      <svg width={size} height={size} className="overflow-visible">
        {/* Background Grid Hexagons */}
        {gridLevels.map((lvl) => {
          const pts = Array.from({ length: numPoints }).map((_, i) => getCoordinates(i, lvl));
          const path = pts.map((pt, i) => `${i === 0 ? 'M' : 'L'} ${pt.x} ${pt.y}`).join(' ') + ' Z';
          return (
            <path
              key={lvl}
              d={path}
              fill="none"
              stroke="#1e293b"
              strokeWidth="1"
              strokeDasharray={lvl < 1 ? '3 3' : undefined}
            />
          );
        })}

        {/* Axis Lines */}
        {Array.from({ length: numPoints }).map((_, i) => {
          const outer = getCoordinates(i, 1.0);
          return (
            <line
              key={i}
              x1={center}
              y1={center}
              x2={outer.x}
              y2={outer.y}
              stroke="#1e293b"
              strokeWidth="1"
            />
          );
        })}

        {/* Data Polygon */}
        <path
          d={dataPath}
          fill="rgba(6, 182, 212, 0.25)"
          stroke="#06b6d4"
          strokeWidth="2"
          className="transition-all duration-500"
        />

        {/* Data Vertices & Tooltips */}
        {dataPoints.map((pt, i) => (
          <circle
            key={i}
            cx={pt.x}
            cy={pt.y}
            r="4"
            fill="#38bdf8"
            stroke="#0b1120"
            strokeWidth="1.5"
          />
        ))}

        {/* Category Labels */}
        {categories.map((cat, i) => {
          const labelPos = getCoordinates(i, 1.22);
          return (
            <text
              key={cat.key}
              x={labelPos.x}
              y={labelPos.y}
              textAnchor="middle"
              dominantBaseline="middle"
              className="text-[10px] font-mono fill-slate-300 font-medium"
            >
              {cat.label} ({cat.val})
            </text>
          );
        })}
      </svg>
      <div className="mt-2 text-center">
        <span className="text-xs text-slate-400">Institutional Fundamental Score: </span>
        <span className="font-mono font-bold text-accent-cyan text-sm">{scores.overall ?? 76}/100</span>
      </div>
    </div>
  );
};
