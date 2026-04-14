'use client';

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';

const PALETTE = ['#7cffb7', '#ffd06b', '#ff6b6b', '#8fa3ff', '#c084fc', '#34d399', '#fb923c'];

const LABELS: Record<string, string> = {
  style_homogeneity: 'Style',
  duplication: 'Duplication',
  comment_patterns: 'Comments',
  error_handling: 'Errors',
  architectural_contracts: 'Contracts',
  dependency_graph: 'Imports',
  code_churn: 'Churn',
};

export function CategoryPie({ analyzers }: { analyzers: Record<string, { score: number; weight: number; skipped?: boolean }> }) {
  const data = Object.entries(analyzers)
    .filter(([, v]) => !v.skipped)
    .map(([name, v]) => ({
      name: LABELS[name] || name,
      value: Math.max(0.1, Math.round(v.score)),
    }));

  return (
    <div className="h-[280px] w-full">
      <ResponsiveContainer>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" innerRadius={50} outerRadius={95} paddingAngle={2}>
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
      </ResponsiveContainer>
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
