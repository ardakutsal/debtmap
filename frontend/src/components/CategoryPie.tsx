'use client';

import { Cell, Pie, PieChart, Tooltip } from 'recharts';

const PALETTE = ['#7cffb7', '#ffd06b', '#ff6b6b', '#8fa3ff', '#c084fc', '#34d399', '#fb923c'];

const LABELS: Record<string, string> = {
  style_homogeneity: 'Style',
  duplication: 'Duplication',
  comment_patterns: 'Comments',
  error_handling: 'Errors',
  architectural_contracts: 'Contracts',
  dependency_graph: 'Imports',
  code_churn: 'Churn',
  test_coverage: 'Tests',
};

// Fixed-size chart: ResponsiveContainer mis-measured inside the CSS grid and
// rendered the pie outside its panel, so we size it deterministically.
const CHART_W = 300;
const CHART_H = 220;

export function CategoryPie({ analyzers }: { analyzers: Record<string, { score: number; weight: number; skipped?: boolean }> }) {
  const data = Object.entries(analyzers)
    .filter(([, v]) => !v.skipped)
    .map(([name, v]) => ({
      name: LABELS[name] || name,
      value: Math.max(0.1, Math.round(v.score)),
    }));

  return (
    <div className="flex flex-col items-center">
      <PieChart width={CHART_W} height={CHART_H}>
        {/* isAnimationActive=false: the mount animation freezes at frame 0 in
            production builds, leaving sliver-thin sectors — render final
            geometry directly. */}
        <Pie data={data} dataKey="value" nameKey="name" innerRadius={46} outerRadius={88} paddingAngle={2} isAnimationActive={false}>
          {data.map((_, i) => (
            <Cell key={i} fill={PALETTE[i % PALETTE.length]} stroke="#0f1117" />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{ background: '#161a22', border: '1px solid #262c3a', borderRadius: 8 }}
          labelStyle={{ color: '#e7ebf3' }}
          formatter={(val: unknown, name: unknown) => [`${val}`, `${name}`]}
        />
      </PieChart>
      <div className="mt-2 flex flex-wrap justify-center gap-x-3 gap-y-1 text-xs text-muted">
        {data.map((d, i) => (
          <span key={d.name} className="flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-full" style={{ background: PALETTE[i % PALETTE.length] }} />
            {d.name}
          </span>
        ))}
      </div>
    </div>
  );
}
