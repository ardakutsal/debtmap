'use client';

import { ResponsiveContainer, Tooltip, Treemap } from 'recharts';
import { gradeColor } from '@/lib/utils';

type FileSummary = { path: string; score: number; loc: number };

export function FileTreemap({ files }: { files: FileSummary[] }) {
  const grouped = groupSmall(files);
  const data = grouped.map((f) => ({
    name: f.path,
    size: Math.max(5, f.loc),
    score: f.score,
  }));
  return (
    <div className="h-[420px] w-full">
      <ResponsiveContainer>
        <Treemap
          data={data}
          dataKey="size"
          nameKey="name"
          stroke="#0f1117"
          content={<Cell />}
          isAnimationActive={false}
        >
          <Tooltip
            contentStyle={{ background: '#161a22', border: '1px solid #262c3a', borderRadius: 8 }}
            formatter={(_val: unknown, _name: unknown, item: any) => [
              `score ${item?.payload?.score?.toFixed?.(1) ?? '-'} · ${item?.payload?.size} LOC`,
              item?.payload?.name ?? '',
            ]}
          />
        </Treemap>
      </ResponsiveContainer>
    </div>
  );
}

function groupSmall(files: FileSummary[]): FileSummary[] {
  const big = files.filter((f) => f.loc >= 20);
  const small = files.filter((f) => f.loc < 20);
  if (small.length === 0) return big;
  const totalLoc = small.reduce((s, f) => s + f.loc, 0);
  const avgScore = small.reduce((s, f) => s + f.score * f.loc, 0) / Math.max(1, totalLoc);
  return [...big, { path: `Other (${small.length} files)`, score: avgScore, loc: totalLoc }];
}

function Cell(props: any) {
  const { x, y, width, height, score, name } = props;
  if (width < 2 || height < 2) return null;
  const color = gradeColor(Number(score ?? 0));
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} fill={color} fillOpacity={0.75} stroke="#0f1117" />
      {width > 70 && height > 22 && (
        <text x={x + 6} y={y + 16} fontSize={11} fill="#0f1117" className="mono" style={{ fontWeight: 600 }}>
          {truncate(name, Math.floor(width / 7))}
        </text>
      )}
      {width > 70 && height > 38 && (
        <text x={x + 6} y={y + 30} fontSize={10} fill="#0f1117" opacity={0.8} className="mono">
          {Number(score).toFixed(0)}
        </text>
      )}
    </g>
  );
}

function truncate(s: string, n: number) {
  return s.length > n ? s.slice(0, n - 1) + '…' : s;
}
