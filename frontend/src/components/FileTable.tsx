'use client';

import { useState } from 'react';

type FileRow = { path: string; loc: number; score: number; breakdown: Record<string, number> };

export function FileTable({ rows }: { rows: FileRow[] }) {
  const [sort, setSort] = useState<'score' | 'loc' | 'path'>('score');
  const sorted = [...rows].sort((a, b) => {
    if (sort === 'path') return a.path.localeCompare(b.path);
    return (b[sort] as number) - (a[sort] as number);
  });
  const top = sorted.slice(0, 10);
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-panel">
      <table className="w-full text-sm">
        <thead className="bg-panel2 text-left text-xs uppercase tracking-wider text-muted">
          <tr>
            <Th label="File" active={sort === 'path'} onClick={() => setSort('path')} />
            <Th label="LOC" active={sort === 'loc'} onClick={() => setSort('loc')} align="right" />
            <Th label="Score" active={sort === 'score'} onClick={() => setSort('score')} align="right" />
          </tr>
        </thead>
        <tbody>
          {top.map((r) => (
            <tr key={r.path} className="border-t border-border/60 hover:bg-panel2/70">
              <td className="mono truncate px-4 py-2 text-xs">{r.path}</td>
              <td className="mono px-4 py-2 text-right text-xs text-muted">{r.loc}</td>
              <td className="mono px-4 py-2 text-right text-xs font-semibold">{r.score.toFixed(1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Th({ label, active, onClick, align }: { label: string; active: boolean; onClick: () => void; align?: 'right' }) {
  return (
    <th
      onClick={onClick}
      className={`cursor-pointer px-4 py-2 select-none ${align === 'right' ? 'text-right' : ''} ${active ? 'text-accent' : ''}`}
    >
      {label} {active ? '↓' : ''}
    </th>
  );
}
