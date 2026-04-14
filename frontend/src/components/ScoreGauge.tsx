'use client';

import { gradeColor } from '@/lib/utils';

export function ScoreGauge({ score, grade }: { score: number; grade: string }) {
  const radius = 90;
  const circumference = 2 * Math.PI * radius;
  const dash = (score / 100) * circumference;
  const color = gradeColor(score);

  return (
    <div className="relative flex flex-col items-center justify-center">
      <svg width="220" height="220" viewBox="0 0 220 220">
        <circle cx="110" cy="110" r={radius} fill="none" stroke="#262c3a" strokeWidth="14" />
        <circle
          cx="110"
          cy="110"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="14"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circumference}`}
          transform="rotate(-90 110 110)"
          style={{ transition: 'stroke-dasharray 1s ease-out' }}
        />
        <text x="110" y="108" textAnchor="middle" fill="#e7ebf3" fontSize="58" fontWeight="600" className="mono">
          {score.toFixed(0)}
        </text>
        <text x="110" y="140" textAnchor="middle" fill="#8b94a8" fontSize="13" className="mono">
          DebtScore
        </text>
      </svg>
      <div
        className="mono mt-2 rounded-full px-4 py-1 text-lg font-bold"
        style={{ backgroundColor: `${color}22`, color, border: `1px solid ${color}66` }}
      >
        Grade {grade}
      </div>
    </div>
  );
}
